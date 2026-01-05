# Python HTTP OSC & MIDI Server for OBS

This project provides a robust integration for OBS Studio, combining a custom HTTP server with OSC (Open Sound Control) and MIDI interfaces. It allows browser sources within OBS to interact with OSC-compatible hardware/software and MIDI devices, and enables remote control of OBS via a simple web API.

## Core Components

### 1. `osc_io.py` (OBS Script)
The heart of the OSC integration.
- **OSC UDP Server:** Listens for incoming OSC messages on a configurable IP and Port.
- **Dynamic Client Management:** Supports multiple clients, each filtering for specific OSC addresses and routing them to dedicated OBS Browser Sources.
- **Event Bridging:** Dispatches `javascript_event` to OBS sources, which can be captured using `window.onEvent` or custom listeners in HTML/JS.

### 2. `midi_io.py` (OBS Script)
Provides MIDI integration for OBS.
- **MIDI Input/Output:** Connects to MIDI devices using `rtmidi`.
- **Event Bridging:** Routes MIDI messages to and from OBS Browser Sources.

### 3. `http_server.py` (OBS Script)
A built-in web server for OBS.
- **Static File Hosting:** Serves HTML, CSS, and JS files from the **parent directory** of the script's location. This allows for a flexible structure where assets can be organized in neighboring folders.
- **WSS Config Loader:** Automatically loads OBS WebSocket credentials for easy integration with other tools.
- **OSC API:** Provides a `/api/osc/send` endpoint, allowing web-based tools to send OSC messages through the established manager.

### 4. Frontend Utilities
- **`osc_monitor.html`:** A visual overlay to debug and monitor incoming OSC messages.
- **`osc_listener.html`:** A lightweight utility that logs messages received over a `BroadcastChannel`.
- **`osc_sender.html`:** A configurable toggle button that sends OSC messages via the HTTP API.
- **`midi_monitor.html`**, **`midi_listener.html`**, **`midi_sender.html`**: Similar utilities for MIDI interaction.

## Setup & Installation

1.  **Dependencies:**
    Install the required Python libraries:
    ```bash
    pip install python-osc python-rtmidi
    ```
2.  **OBS Configuration:**
    - Go to `Tools` -> `Scripts` in OBS.
    - Add `osc_io.py`, `midi_io.py`, and `http_server.py`.
    - Configure the settings for each script in the OBS Scripts window.
3.  **Browser Sources:**
    - Add a Browser Source in OBS pointing to `http://localhost:8080/osc_monitor.html?event=your_event_name` (or other utility files).

## API Usage

### Sending OSC via HTTP
**Endpoint:** `POST /api/osc/send`
**Body:**
```json
{
  "event_name": "osc_event_0",
  "address": "/4/toggle1",
  "args": [1.0]
}
```

## Documentation
For full documentation, visit: [https://uuoocl.github.io/python_http_osc_midi_server/](https://uuoocl.github.io/python_http_osc_midi_server/)

## Note
This repository was made with Google Gemini.
