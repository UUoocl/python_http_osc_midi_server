import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.abspath('..'))

# Mocking external libraries that might not be available during doc build
MOCK_MODULES = ['obspython', 'rtmidi', 'pythonosc', 'pythonosc.udp_client', 'pythonosc.dispatcher', 'pythonosc.osc_server']
for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = mock.Mock()

project = 'Python HTTP OSC MIDI Server'
copyright = '2026, Jon Wood'
author = 'Jon Wood'
version = '1.0.0'
release = '1.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

language = 'en'

html_theme = 'alabaster'
html_static_path = ['_static']