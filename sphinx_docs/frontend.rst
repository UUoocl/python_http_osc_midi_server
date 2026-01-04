Frontend Utilities
==================

This section documents the HTML/JS frontend utilities provided with the project.

OSC Monitor (osc_monitor.html)
------------------------------
A visual overlay for OBS that displays incoming OSC messages. It uses a ``BroadcastChannel`` to share messages with other tabs.

* **Usage**: Add as a Browser Source with ``?event=YOUR_EVENT_NAME``.
* **Key Features**: History log, visual flash on message, OBS event bridge.

OSC Listener (osc_listener.html)
--------------------------------
A debug utility that listens to a specific ``BroadcastChannel`` and logs all data.

* **Usage**: Open in a browser with ``?channel=YOUR_EVENT_NAME``.

OSC Sender (osc_sender.html)
----------------------------
A toggle button that sends an OSC message via the HTTP API.

* **Usage**: Open with ``?event=YOUR_EVENT_NAME``.
* **API Endpoint**: ``POST /api/osc/send``

MIDI Sender (midi_sender.html)
------------------------------
A toggle button that sends MIDI messages (hex) via the HTTP API.

* **Usage**: Open with ``?event=YOUR_EVENT_NAME``.
* **API Endpoint**: ``POST /api/midi/send``
