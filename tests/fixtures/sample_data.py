"""Sample test data for claude-fx-plugin tests."""

import json

# Sample settings-fx.json content
SAMPLE_SETTINGS = {
    "overlay": {
        "enabled": True,
        "responsive": True,
        "heightRatio": 1,
        "maxHeight": 750,
        "position": "auto",
        "customX": None,
        "customY": None,
        "offsetX": 20,
        "offsetY": 0,
        "showOnlyWhenTerminalActive": True,
        "fadeAnimation": True,
    },
    "audio": {"enabled": True, "volume": 0.5},
    "theme": "default",
}

SAMPLE_SETTINGS_DISABLED = {
    "overlay": {"enabled": False},
    "audio": {"enabled": False},
    "theme": "default",
}

SAMPLE_SETTINGS_AUDIO_DISABLED = {
    "overlay": {"enabled": True},
    "audio": {"enabled": False, "volume": 0.5},
    "theme": "default",
}

# Sample theme manifest.json
SAMPLE_MANIFEST = {
    "name": "Default Theme",
    "description": "Default Claude FX theme",
    "version": "1.0.0",
    "states": {
        "idle": {"animation": "characters/idle.png", "sound": None},
        "greeting": {
            "animation": "characters/greeting.png",
            "sound": "sounds/greeting.wav",
        },
        "working": {
            "animation": "characters/working.png",
            "sound": "sounds/working.wav",
        },
        "success": {
            "animation": "characters/success.png",
            "sound": "sounds/success.wav",
        },
        "error": {
            "animation": "characters/error.png",
            "sound": "sounds/error.wav",
        },
        "celebrating": {
            "animation": "characters/celebrating.png",
            "sound": "sounds/celebration.wav",
        },
        "sleeping": {"animation": "characters/sleeping.png", "sound": None},
    },
}

# Sample state file content
SAMPLE_STATE = {
    "state": "idle",
    "tool": None,
    "terminal_pid": 12345,
    "terminal_window_id": 54321,
    "timestamp": 1705324800000,
}

SAMPLE_STATE_WORKING = {
    "state": "working",
    "tool": "Read",
    "terminal_pid": 12345,
    "terminal_window_id": 54321,
    "timestamp": 1705324800000,
}

SAMPLE_STATE_GREETING = {
    "state": "greeting",
    "tool": None,
    "terminal_pid": 12345,
    "terminal_window_id": 54321,
    "timestamp": 1705324800000,
}

# Sample hook event data
SAMPLE_HOOK_DATA = {
    "session_start": {
        "hook_event_name": "SessionStart",
        "session_id": "abc123",
    },
    "pre_tool_use": {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": "/path/to/file.py"},
    },
    "post_tool_use_success": {
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_result": {"output": "file contents here"},
    },
    "post_tool_use_error": {
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_result": {"error": True, "output": "Error: file not found"},
    },
    "post_tool_use_error_pattern": {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_result": {"output": "ENOENT: no such file or directory"},
    },
    "stop": {
        "hook_event_name": "Stop",
    },
    "session_end": {
        "hook_event_name": "SessionEnd",
    },
    "empty": {},
}

# PS command output samples for terminal detection
PS_OUTPUT_TERMINAL = """12345 Terminal
"""

PS_OUTPUT_ITERM = """12345 iTerm2
"""

PS_OUTPUT_NO_TERMINAL = """12345 python3
"""

PS_OUTPUT_PROCESS_CHAIN = """99999 python3
88888 node
77777 bash
66666 login
12345 Terminal
"""


def get_settings_json():
    """Get sample settings as JSON string."""
    return json.dumps(SAMPLE_SETTINGS)


def get_manifest_json():
    """Get sample manifest as JSON string."""
    return json.dumps(SAMPLE_MANIFEST)


def get_state_json(state="idle"):
    """Get sample state as JSON string."""
    data = SAMPLE_STATE.copy()
    data["state"] = state
    return json.dumps(data)
