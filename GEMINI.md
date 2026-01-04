# Python HTTP OSC Server for OBS

This project provides a robust integration for OBS Studio, combining a custom HTTP server with an OSC (Open Sound Control) interface. It allows browser sources within OBS to interact with OSC-compatible hardware and software, and enables remote control of OBS via a simple web API.

## Core Components

### 1. `osc_io_browserSource.py` (OBS Script)
The heart of the OSC integration.
- **OSC UDP Server:** Listens for incoming OSC messages on a configurable IP and Port.
- **Dynamic Client Management:** Supports multiple clients, each filtering for specific OSC addresses and routing them to dedicated OBS Browser Sources.
- **Event Bridging:** Dispatches `javascript_event` to OBS sources, which can be captured using `window.onEvent` or custom listeners in HTML/JS.

### 2. `obs_python_http_server.py` (OBS Script)
A built-in web server for OBS.
- **Static File Hosting:** Serves HTML, CSS, and JS files from the **parent directory** of the script's location. This allows for a flexible structure where assets can be organized in neighboring folders.
- **WSS Config Loader:** Automatically loads OBS WebSocket credentials for easy integration with other tools.
- **OSC API:** Provides a `/api/osc/send` endpoint, allowing web-based tools to send OSC messages through the established manager.

### 3. Frontend Utilities
- **`osc_monitor.html`:** A visual overlay to debug and monitor incoming OSC messages.
- **`osc_listener.html`:** A lightweight utility that logs messages received over a `BroadcastChannel`.
- **`osc_sender.html`:** A configurable toggle button that sends OSC messages via the HTTP API.

## Setup & Installation

1.  **Dependencies:**
    Install the required Python library:
    ```bash
    pip install python-osc
    ```
2.  **OBS Configuration:**
    - Go to `Tools` -> `Scripts` in OBS.
    - Add `osc_io_browserSource.py` and `obs_python_http_server.py`.
    - Configure the Server IP/Port and the number of clients you wish to use.
3.  **Browser Sources:**
    - Add a Browser Source in OBS pointing to `http://localhost:8080/osc_monitor.html?event=your_event_name`.

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

## Project Goals
This project aims to bridge the gap between professional audio/lighting protocols (OSC) and modern web technologies within the OBS Studio ecosystem, providing streamers and producers with a high-performance, flexible toolkit.
