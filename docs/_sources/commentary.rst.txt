Developer Commentary
====================

Design Choices
--------------

Bridge Pattern
^^^^^^^^^^^^^^
One of the core challenges was allowing OBS Python scripts (which run in their own environments) to communicate with web-based Browser Sources. I implemented a "Bridge Pattern" where:
1. Python scripts capture hardware events (OSC/MIDI).
2. They inject these events into Browser Sources using ``javascript_event``.
3. HTML pages use a ``window.onEvent`` bridge to translate these into standard ``CustomEvent`` objects.

Class-Based Management
^^^^^^^^^^^^^^^^^^^^^^
The OSC implementation was refactored from simple functions to an ``OSCManager`` class. This allows for:
* Thread safety using locks.
* Persistent UDP clients (socket reuse).
* Cleaner separation between the UDP server and the OBS UI logic.

HTTP Server Integration
^^^^^^^^^^^^^^^^^^^^^^^
Instead of relying on external web servers, I built a custom ``ThreadingHTTPServer`` directly into OBS. This ensures that:
* The server root is local to the project (or its parent).
* We can provide an API (``/api/osc/send``, ``/api/midi/send``) that directly interacts with the Python script objects stored in the ``obs`` namespace.

Refactoring Journey
-------------------
The UI was iteratively improved. We experimented with dynamic "Add/Remove" buttons but eventually reverted to a more stable "Number of Clients" counter to ensure compatibility with OBS's unique property handling system.
