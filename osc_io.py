"""
OSC IO: Browser Source Integration (Refactored)
===============================================
This script provides an OSC interface for OBS Studio using a class-based manager
for improved efficiency and thread safety.
"""

import obspython as obs
import json
import threading

try:
    from pythonosc import udp_client, dispatcher, osc_server
except ImportError:
    obs.script_log(obs.LOG_ERROR, "python-osc not found. Please install it with 'pip install python-osc'")

# --- Constants ---
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_SERVER_PORT = 12345
MAX_CLIENTS = 10

# --- Classes ---

class OSCClient:
    """Represents a target for OSC messages and an event source for Browser Sources."""
    def __init__(self, settings, index):
        self.ip = obs.obs_data_get_string(settings, f"client_ip_{index}")
        self.port = obs.obs_data_get_int(settings, f"client_port_{index}")
        self.browser_source = obs.obs_data_get_string(settings, f"browser_source_name_{index}")
        self.osc_address = obs.obs_data_get_string(settings, f"osc_address_{index}")
        self.event_name = obs.obs_data_get_string(settings, f"event_name_{index}") or f"osc_event_{index}"
        
        # Persist UDP client to reuse the same socket
        self._udp_client = None
        if self.ip and self.port:
            try:
                self._udp_client = udp_client.SimpleUDPClient(self.ip, self.port)
            except Exception as e:
                obs.script_log(obs.LOG_WARNING, f"Could not create client for {self.ip}:{self.port} - {e}")

    def send(self, address, arguments):
        """Send an OSC message to this client."""
        if self._udp_client:
            try:
                self._udp_client.send_message(address, arguments)
            except Exception as e:
                obs.script_log(obs.LOG_ERROR, f"OSC Send Error ({self.ip}): {e}")

    def matches(self, address):
        """Check if an incoming OSC address matches this client's filter."""
        if not self.osc_address:
            return True # Match all if no filter set
        return address.startswith(self.osc_address)

    def to_dict(self):
        """Convert to dictionary for external script compatibility (bridge)."""
        return {
            "client_ip": self.ip,
            "client_port": self.port,
            "browser_source_name": self.browser_source,
            "osc_address": self.osc_address,
            "event_name": self.event_name
        }

class OSCManager:
    """Manages the OSC UDP server and the collection of OSC clients."""
    def __init__(self):
        self.clients = []
        self.server = None
        self.server_thread = None
        self._lock = threading.Lock()
        self.is_running = False

    def update_settings(self, settings):
        """Rebuild client list from current OBS settings."""
        with self._lock:
            count = obs.obs_data_get_int(settings, "number_of_clients")
            self.clients = [OSCClient(settings, i) for i in range(count)]
            
            # Update the global bridge for the HTTP server
            obs.osc_manager = {
                "clients": [c.to_dict() for c in self.clients],
                "send": self._bridge_send
            }

    def _bridge_send(self, client_dict, address, arguments):
        """Bridge function called by other scripts via obs.osc_manager."""
        with self._lock:
            # Match by event_name which is our unique identifier
            target = next((c for c in self.clients if c.event_name == client_dict.get("event_name")), None)
            if target:
                target.send(address, arguments)

    def start_server(self, ip, port):
        """Start the background OSC UDP server."""
        self.stop_server()
        try:
            disp = dispatcher.Dispatcher()
            disp.set_default_handler(self._on_osc_received)
            self.server = osc_server.ThreadingOSCUDPServer((ip, port), disp)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.is_running = True
            obs.script_log(obs.LOG_INFO, f"OSC Server started on {ip}:{port}")
        except Exception as e:
            obs.script_log(obs.LOG_ERROR, f"Failed to start OSC server: {e}")

    def stop_server(self):
        """Stop the OSC UDP server safely."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.server_thread:
            self.server_thread.join(timeout=1.0)
            self.server_thread = None
        self.is_running = False
        obs.script_log(obs.LOG_INFO, "OSC Server stopped.")

    def _on_osc_received(self, address, *args):
        """Callback for incoming OSC messages (runs in server thread)."""
        # Note: Log level INFO shows in OBS script log window
        obs.script_log(obs.LOG_INFO, f"Received OSC: {address} {args}")
        with self._lock:
            for client in self.clients:
                if client.matches(address):
                    self._dispatch_to_obs(client, address, args)
                    break # Only first match handles it

    def _dispatch_to_obs(self, client, address, args):
        """Forward OSC data to an OBS Browser Source."""
        source = obs.obs_get_source_by_name(client.browser_source)
        if source:
            json_string = json.dumps({"address": address, "arguments": args})
            cd = obs.calldata_create()
            obs.calldata_set_string(cd, "eventName", client.event_name)
            obs.calldata_set_string(cd, "jsonString", json_string)
            
            proc_handler = obs.obs_source_get_proc_handler(source)
            obs.proc_handler_call(proc_handler, "javascript_event", cd)
            
            obs.calldata_destroy(cd)
            obs.obs_source_release(source)

# --- Global Instance ---
MANAGER = OSCManager()

# --- OBS Script Callbacks ---

def script_description():
    return "<b>OSC IO Refactored</b><br>Class-based OSC management for high performance."

def script_defaults(settings):
    obs.obs_data_set_default_string(settings, "server_ip", DEFAULT_SERVER_IP)
    obs.obs_data_set_default_int(settings, "server_port", DEFAULT_SERVER_PORT)
    obs.obs_data_set_default_int(settings, "number_of_clients", 0)

def script_load(settings):
    MANAGER.update_settings(settings)
    # Start server if IP/Port are provided
    ip = obs.obs_data_get_string(settings, "server_ip")
    port = obs.obs_data_get_int(settings, "server_port")
    if ip and port:
        MANAGER.start_server(ip, port)

def script_update(settings):
    MANAGER.update_settings(settings)

def script_unload():
    MANAGER.stop_server()
    if hasattr(obs, 'osc_manager'):
        del obs.osc_manager

# --- UI Helpers ---

def populate_list_property(list_property, allowed_ids):
    sources = obs.obs_enum_sources()
    if sources:
        for source in sources:
            unversioned_id = obs.obs_source_get_unversioned_id(source)
            if unversioned_id in allowed_ids:
                name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(list_property, name, name)
        obs.source_list_release(sources)

def client_count_callback(props, prop, settings):
    # Brute force refresh of client groups
    for i in range(MAX_CLIENTS):
        obs.obs_properties_remove_by_name(props, f"client_group_{i}")
    
    count = obs.obs_data_get_int(settings, "number_of_clients")
    for i in range(count):
        add_client_ui(props, i)
    return True

def add_client_ui(props, index):
    group = obs.obs_properties_create()
    obs.obs_properties_add_text(group, f"client_ip_{index}", "IP Address", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int(group, f"client_port_{index}", "Port", 1, 65535, 1)

    browser_prop = obs.obs_properties_add_list(group, f"browser_source_name_{index}", "Target Browser Source", 
                                             obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    populate_list_property(browser_prop, ["browser_source"])

    obs.obs_properties_add_text(group, f"osc_address_{index}", "OSC Address Filter", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(group, f"event_name_{index}", "Unique Event Name", obs.OBS_TEXT_DEFAULT)

    obs.obs_properties_add_group(props, f"client_group_{index}", f"Client {index+1}", obs.OBS_GROUP_NORMAL, group)

def script_properties(settings=None):
    props = obs.obs_properties_create()
    
    # Server Settings
    server_group = obs.obs_properties_create()
    obs.obs_properties_add_text(server_group, "server_ip", "Server IP", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int(server_group, "server_port", "Server Port", 1, 65535, 1)
    
    obs.obs_properties_add_button(server_group, "btn_start", "Restart Server", 
                                lambda p, pr: MANAGER.start_server(
                                    obs.obs_data_get_string(settings, "server_ip") if settings else DEFAULT_SERVER_IP,
                                    obs.obs_data_get_int(settings, "server_port") if settings else DEFAULT_SERVER_PORT
                                ))
    
    obs.obs_properties_add_group(props, "server_group", "Global OSC Server", obs.OBS_GROUP_NORMAL, server_group)

    # Client Count
    p_count = obs.obs_properties_add_int(props, "number_of_clients", "Number of Clients", 0, MAX_CLIENTS, 1)
    obs.obs_property_set_modified_callback(p_count, client_count_callback)

    # Initial UI Load
    if settings:
        count = obs.obs_data_get_int(settings, "number_of_clients")
        for i in range(count):
            add_client_ui(props, i)

    return props