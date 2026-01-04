import obspython as obs
import http.server
import socketserver
import threading
import json
import os
import urllib.parse
import traceback

# -------------------------------------------------------------------
# GLOBAL VARIABLES
# -------------------------------------------------------------------
WSS_DETAILS = {
    "IP": "localhost",
    "PORT": 4455,
    "PW": ""
}
HTTP_SERVER_INSTANCE = None
SERVER_THREAD = None
CURRENT_HTTP_PORT = 8080
# Set SCRIPT_DIR to the parent directory of the script's location
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -------------------------------------------------------------------
# SERVER CLASSES
# -------------------------------------------------------------------

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """
    Handle requests in separate threads and allow immediate port reuse.
    """
    allow_reuse_address = True
    daemon_threads = True

# -------------------------------------------------------------------
# CONFIG LOADING LOGIC (Adapted from 01_load_wss_config.py)
# -------------------------------------------------------------------

def update_wss_details(source_path):
    """
    Parses the selected JSON config file and updates the global WSS_DETAILS variable.
    """
    global WSS_DETAILS
    
    if not source_path or not os.path.exists(source_path):
        return False, "File not found or not selected."

    try:
        with open(source_path, "r", encoding="utf-8") as infile:
            source_data = json.load(infile)

        required_keys = ["server_password", "server_port"]
        missing = [k for k in required_keys if k not in source_data]

        if missing:
            return False, f"Missing keys: {missing}"

        # Update Global Variable
        WSS_DETAILS["PW"] = source_data.get("server_password", "")
        WSS_DETAILS["PORT"] = int(source_data.get("server_port", 4455))
        
        # IP is usually localhost for local configs, unless specified
        WSS_DETAILS["IP"] = "localhost" 

        return True, "Loaded successfully."

    except json.JSONDecodeError:
        return False, "Invalid JSON."
    except Exception as e:
        return False, f"Error: {str(e)}"

# -------------------------------------------------------------------
# HTTP SERVER LOGIC
# -------------------------------------------------------------------

class OBSServerHandler(http.server.SimpleHTTPRequestHandler):
    """
    Custom Request Handler to mimic the Fastify routes in serverLogic.ts
    """
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve static files from (Script Directory)
        # Note: 'directory' kwarg is available in Python 3.7+. 
        # We assume OBS uses a relatively modern Python.
        if SCRIPT_DIR and os.path.isdir(SCRIPT_DIR):
             super().__init__(*args, directory=SCRIPT_DIR, **kwargs)
        else:
             super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        # Suppress logging to keep OBS log clean, or uncomment to debug
        # obs.script_log(obs.LOG_INFO, format % args)
        pass

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # Enable CORS
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _send_error(self, message, code=500):
        self._send_json({"error": message}, code)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path_path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)

        # --- API: Get OBS Credentials ---
        # Route: /api/obswss
        if path_path == '/api/obswss':
            self._send_json(WSS_DETAILS)
            return

        # --- API: Generic File List ---
        # Route: /api/file/list?folder=...
        elif path_path == '/api/file/list':
            folder_list = query_params.get('folder', [None])[0]
            if not folder_list:
                self._send_error("Missing folder parameter", 400)
                return
            
            target_dir = os.path.join(SCRIPT_DIR, folder_list)
            
            # Security check: Ensure path is within SCRIPT_DIR
            if not os.path.normpath(target_dir).startswith(SCRIPT_DIR):
                self._send_error("Access denied", 403)
                return

            if not os.path.exists(target_dir):
                self._send_json([])
                return

            try:
                files = [f for f in os.listdir(target_dir) if f.endswith('.json')]
                self._send_json(files)
            except Exception as e:
                self._send_error(str(e))
            return

        # --- API: Generic File Get ---
        # Route: /api/file/get?folder=...&filename=...
        elif path_path == '/api/file/get':
            folder = query_params.get('folder', [None])[0]
            filename = query_params.get('filename', [None])[0]

            if not folder or not filename:
                self._send_error("Missing folder or filename parameter", 400)
                return

            target_dir = os.path.join(SCRIPT_DIR, folder)
            full_path = os.path.join(target_dir, filename)

            if not os.path.normpath(full_path).startswith(SCRIPT_DIR):
                self._send_error("Access denied", 403)
                return

            if not os.path.exists(full_path):
                self._send_error("File not found", 404)
                return

            try:
                # Optimized: Read bytes directly to avoid redundant JSON parsing/serialization
                with open(full_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                obs.script_log(obs.LOG_ERROR, f"Error reading file: {traceback.format_exc()}")
                self._send_error(str(e))
            return

        # Fallback to serving static files
        super().do_GET()

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # --- API: Generic File Save ---
        # Route: /api/file/save
        if parsed_path.path == '/api/file/save':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                body = json.loads(post_data.decode('utf-8'))

                folder = body.get('folder')
                filename = body.get('filename')
                data = body.get('data')

                if not folder or not filename or data is None:
                    self._send_error("Missing folder, filename, or data", 400)
                    return

                target_dir = os.path.join(SCRIPT_DIR, folder)
                
                # Append .json if missing
                if not filename.endswith('.json'):
                    filename += '.json'
                
                full_path = os.path.join(target_dir, filename)

                if not os.path.normpath(target_dir).startswith(SCRIPT_DIR):
                    self._send_error("Access denied: Path outside root", 403)
                    return

                if not os.path.exists(target_dir):
                    try:
                        os.makedirs(target_dir, exist_ok=True)
                    except Exception as e:
                        self._send_error(f"Failed to create directory: {str(e)}")
                        return

                with open(full_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

                self._send_json({"success": True, "path": full_path})
            
            except Exception as e:
                self._send_error(str(e))
            return

        # --- API: OSC Send (Communication with osc_io_browserSource.py) ---
        # Route: /api/osc/send
        if parsed_path.path == '/api/osc/send':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                body = json.loads(post_data.decode('utf-8'))

                event_name = body.get('event_name')
                address = body.get('address')
                args = body.get('args', [])

                if not address or not event_name:
                    self._send_error("Missing OSC address or event_name", 400)
                    return

                # Check for the shared OSC manager from the other script
                osc_manager = getattr(obs, 'osc_manager', None)
                if not osc_manager:
                    self._send_error("OSC Script not loaded or registered", 503)
                    return

                clients = osc_manager.get("clients", [])
                
                # Find the client by unique event_name
                target_client = next((c for c in clients if c.get("event_name") == event_name), None)
                
                if not target_client:
                    self._send_error(f"Client with event_name '{event_name}' not found", 404)
                    return

                # Execute the send via the shared manager
                osc_manager["send"](target_client, address, args)
                
                self._send_json({"success": True})

            except Exception as e:
                obs.script_log(obs.LOG_ERROR, f"OSC Send Error: {traceback.format_exc()}")
                self._send_error(str(e))
            return
        
        # Fallback
        self.send_error(404)

    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def start_server(port):
    global HTTP_SERVER_INSTANCE, SERVER_THREAD
    
    # Stop existing if any
    stop_server()

    try:
        # Using ThreadingHTTPServer for concurrency and reliable port reuse
        HTTP_SERVER_INSTANCE = ThreadingHTTPServer(("127.0.0.1", port), OBSServerHandler)
        
        SERVER_THREAD = threading.Thread(target=HTTP_SERVER_INSTANCE.serve_forever)
        SERVER_THREAD.daemon = True
        SERVER_THREAD.start()
        print(f"Server started on port {port}")
        obs.script_log(obs.LOG_INFO, f"HTTP Server started on 127.0.0.1:{port}")
    except Exception as e:
        obs.script_log(obs.LOG_ERROR, f"Failed to start server: {e}\n{traceback.format_exc()}")
        HTTP_SERVER_INSTANCE = None

def stop_server():
    global HTTP_SERVER_INSTANCE, SERVER_THREAD
    if HTTP_SERVER_INSTANCE:
        HTTP_SERVER_INSTANCE.shutdown()
        HTTP_SERVER_INSTANCE.server_close()
        HTTP_SERVER_INSTANCE = None
    if SERVER_THREAD:
        SERVER_THREAD.join(timeout=1.0)
        SERVER_THREAD = None

# -------------------------------------------------------------------
# OBS SCRIPT CALLBACKS
# -------------------------------------------------------------------

def script_description():
    return """<b>Python HTTP Server & WSS Loader</b>
    <hr>
    <p>Host local files and provide API endpoints for browser sources.</p>
    <p>Server runs on 127.0.0.1</p>
    """

def script_load(settings):
    global SCRIPT_DIR
    # Update WSS details from saved path
    wss_path = obs.obs_data_get_string(settings, "wss_config_path")
    if wss_path:
        update_wss_details(wss_path)

    # Start Server
    port = obs.obs_data_get_int(settings, "http_port")
    if port == 0:
        port = 8080 # Default
    
    global CURRENT_HTTP_PORT
    CURRENT_HTTP_PORT = port
    start_server(CURRENT_HTTP_PORT)

def script_unload():
    stop_server()

def on_wss_path_changed(props, prop, settings):
    path = obs.obs_data_get_string(settings, "wss_config_path")
    success, msg = update_wss_details(path)
    obs.obs_data_set_string(settings, "status_text", msg)
    return True

def on_port_changed(props, prop, settings):
    global CURRENT_HTTP_PORT
    new_port = obs.obs_data_get_int(settings, "http_port")
    
    if new_port != CURRENT_HTTP_PORT:
        CURRENT_HTTP_PORT = new_port
        start_server(CURRENT_HTTP_PORT)
    return False

def script_properties():
    props = obs.obs_properties_create()

    # WSS Config Selection
    obs.obs_properties_add_path(props, "wss_config_path", "WSS Config File", obs.OBS_PATH_FILE, "JSON Files (*.json);;All Files (*.*)", None)
    
    # Status display
    obs.obs_properties_add_text(props, "status_text", "Config Status", obs.OBS_TEXT_MULTILINE)

    # HTTP Port
    p_port = obs.obs_properties_add_int(props, "http_port", "HTTP Port", 1024, 65535, 1)
    
    # Callbacks
    obs.obs_property_set_modified_callback(obs.obs_properties_get(props, "wss_config_path"), on_wss_path_changed)
    obs.obs_property_set_modified_callback(p_port, on_port_changed)

    return props

def script_defaults(settings):
    obs.obs_data_set_default_int(settings, "http_port", 8080)
