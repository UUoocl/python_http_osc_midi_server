import obspython as obs
import json
import rtmidi
import threading

class MidiDevice:
    def __init__(self, device_name):
        self.device_name = device_name
        self.port_name = None
        self.midi_in = None
        self.midi_out = None
        self.browser_source_name = ""
        self.event_name = ""

#Global variables
num_devices = None
midi_devices = []  # List to store MidiDevice objects
midi_ports_in = []
script_settings = None # a pointer to the obs settings for this script

def script_defaults(settings):
    print("script defaults")
    pass


def script_description():
    print("script description")
    return "script configure M"


def script_load(settings):
    global midi_ports_in, midi_ports_out, script_settings, midi_devices, num_devices

    script_settings = settings
    
    #get connected midi device list
    try:
        midi_in = rtmidi.MidiIn()
        midi_ports_in = midi_in.get_ports()
        del midi_in
        print(f"{len(midi_ports_in)} available MIDI input ports:", midi_ports_in)
        num_devices = len(midi_ports_in)
    except Exception as e:
        print(f"Error initializing MIDI: {e}")

    #load midi device list with saved script settings
    for i in range(obs.obs_data_get_int(settings, "number_of_devices")):
        port_name = obs.obs_data_get_string(settings, f"midi_port_name_{i}")
        print(port_name)
        if port_name in midi_ports_in: #Only create the device, if the name is found
            new_device = MidiDevice(f"MIDI Device {i + 1}")
            new_device.port_name = port_name
            new_device.browser_source_name = obs.obs_data_get_string(settings, f"browser_source_name_{i}")
            
            # Load event name, default to midiDevice_{i}
            new_device.event_name = obs.obs_data_get_string(settings, f"event_name_{i}")
            if not new_device.event_name:
                new_device.event_name = f"midiDevice_{i}"
            
            print(f"port found {new_device.port_name}")
            
            midi_devices.append(new_device)
            print(f"midi devices on load {midi_devices[i].port_name}")
        else:
            obs.obs_data_set_string(settings, f"midi_port_name_{i}", "---")

    # Register shared MIDI manager for the HTTP server
    obs.midi_manager = {
        "send": send_midi_api
    }

    #start monitoring midi messages
    stop_midi()  # Stop all MIDI devices
    start_midi()  # Start all MIDI devices


def send_midi_api(event_name, data):
    """Bridge function called by the HTTP server."""
    target_device = next((d for d in midi_devices if d.event_name == event_name), None)
    if target_device and target_device.midi_out:
        try:
            if isinstance(data, str):
                # Assume hex string
                message = bytearray.fromhex(data.replace(" ", ""))
            elif isinstance(data, list):
                # Assume list of ints
                message = bytearray(data)
            else:
                return False
            
            target_device.midi_out.send_message(message)
            return True
        except Exception as e:
            print(f"Error sending MIDI via API: {e}")
    return False


def script_properties(): #UI
    global script_settings, num_devices

    props = obs.obs_properties_create()
    print(f"script properties {obs.obs_data_get_json(script_settings)}")

    device_count = obs.obs_properties_add_int(props, "number_of_devices", "Number of Midi Devices", 0, num_devices, 1)
    #modified call back. called when users changes property
    obs.obs_property_set_modified_callback(device_count, device_count_callback)    

    for i in range(obs.obs_data_get_int(script_settings, "number_of_devices")):
        add_device_properties(props, i)
    
    return props


def device_count_callback(props, prop, settings):  # UI
    p = obs.obs_data_get_int(settings, "number_of_devices")
    remove = p
    print(f"callback {p}")

    for remove in range(num_devices):
        obs.obs_properties_remove_by_name(props,f"device_group_{remove}")

    for i in range(p):
        add_device_properties(props, i)
    
    return True


def add_device_properties(props, index): #UI
    # Create property group
    device_group = obs.obs_properties_create()
    
    #Add group's properties
    # MIDI Device Selection
    d = obs.obs_properties_add_list(
        device_group, # Add to the inner group's properties
        f"midi_port_name_{index}",
        "MIDI Device",
        obs.OBS_COMBO_TYPE_LIST,
        obs.OBS_COMBO_FORMAT_STRING
    )
    for port_name in midi_ports_in:
        obs.obs_property_list_add_string(d, port_name, port_name)
    # Set the current value if the device already has a port_name
    if obs.obs_data_get_string(script_settings, f"midi_port_name_{index}"):
        obs.obs_property_list_add_string(d, 
            obs.obs_data_get_string(script_settings, f"midi_port_name_{index}"),
            obs.obs_data_get_string(script_settings, f"midi_port_name_{index}")) # Ensure selected value is an option

    # JS Event Name
    obs.obs_properties_add_text(device_group, f"event_name_{index}", "JS Event Name", obs.OBS_TEXT_DEFAULT)

    # Browser Source Selection (MIDI -> Browser)
    input_prop = obs.obs_properties_add_list(
        device_group,
        f"browser_source_name_{index}",
        f"Target Browser Source {index+1}",
        obs.OBS_COMBO_TYPE_LIST,
        obs.OBS_COMBO_FORMAT_STRING
    )

    # populate drop down lists
    sources = obs.obs_enum_sources()
    if sources is not None:
        for source in sources:
            source_type = obs.obs_source_get_type(source)
            if source_type == obs.OBS_SOURCE_TYPE_INPUT:
                unversioned_id = obs.obs_source_get_unversioned_id(source)
                name = obs.obs_source_get_name(source)
                
                # Add browser sources to input list
                if unversioned_id == "browser_source":
                    obs.obs_property_list_add_string(input_prop, name, name)
        obs.source_list_release(sources)

    # #Add property group to Properties list
    device_property_group = obs.obs_properties_add_group(props, f"device_group_{index}", f"Device {index+1}", obs.OBS_GROUP_NORMAL, device_group)
    obs.obs_property_set_visible(device_property_group, True)


def script_unload():
    global script_settings, midi_devices

    print(f"script unload {obs.obs_data_get_json(script_settings)}")
    stop_midi() 
    if hasattr(obs, 'midi_manager'):
        del obs.midi_manager


def script_update(settings):
    print(f"script update {obs.obs_data_get_json(settings)}")


def start_midi():
    global stop_flag

    stop_flag = False

    for device in midi_devices:
        start_midi_device(device)


def start_midi_device(device):
    if not device.port_name:
        return  # No MIDI device selected

    try:
        port_index = midi_ports_in.index(device.port_name)

        # Start MIDI Input
        device.midi_in = rtmidi.MidiIn()
        device.midi_in.open_port(port_index)
        # Use a lambda to pass the device to the callback
        device.midi_in.set_callback(lambda message, time_stamp=None: midi_input_callback(device, message, time_stamp))
        device.midi_in.ignore_types(False, False, False)  # Don't ignore anything
        print(f"Started MIDI input on port: {device.port_name}")

        # Start MIDI Output
        device.midi_out = rtmidi.MidiOut()
        device.midi_out.open_port(port_index)
        print(f"Started MIDI output on port: {device.port_name}")

    except ValueError as e:
        print(f"Error opening MIDI port: {e}")
        return  
    except Exception as e:
        print(f"Error initializing MIDI: {e}")
        return  


def midi_input_callback(device, message, time_stamp=None):
    midi_data = message[0]
    midi_status = midi_data[0]
    midi_note = midi_data[1] if len(midi_data) > 1 else 0
    midi_velocity = midi_data[2] if len(midi_data) > 2 else 0

    print(f"MIDI In: Status={midi_status}, Note={midi_note}, Vel={midi_velocity}")
    
    # Update the OBS browser source
    if device.browser_source_name:
        source = obs.obs_get_source_by_name(device.browser_source_name)
        if source:
            try:
                # Prepare JSON data
                event_data = {
                    "status": midi_status,
                    "note": midi_note,
                    "velocity": midi_velocity,
                    "data": [int(b) for b in midi_data]
                }
                json_str = json.dumps(event_data)
                
                # Inject Javascript Event
                cd = obs.calldata_create()
                obs.calldata_set_string(cd, "eventName", device.event_name)
                obs.calldata_set_string(cd, "jsonString", json_str)
                proc = obs.obs_source_get_proc_handler(source)
                obs.proc_handler_call(proc, "javascript_event", cd)
                obs.calldata_destroy(cd)
            except Exception as e:
                print(f"Error sending to browser source: {e}")
            finally:
                obs.obs_source_release(source)


def stop_midi():
    global stop_flag

    stop_flag = True

    for device in midi_devices:
        stop_midi_device(device)


def stop_midi_device(device):
    # Stop MIDI Input
    if device.midi_in:
        try:
            device.midi_in.close_port()
            del device.midi_in
            device.midi_in = None
            print("Stopped MIDI input.")
        except Exception as e:
            print(f"Error stopping MIDI input: {e}")

    # Stop MIDI Output
    if device.midi_out:
        try:
            device.midi_out.close_port()
            del device.midi_out
            device.midi_out = None
            print("Stopped MIDI output.")
        except Exception as e:
            print(f"Error stopping MIDI output: {e}")
        