"""Integration tests for claude-fx-plugin - end-to-end flows."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Mock modules for cross-platform testing
MOCK_MODULES = {"AppKit": MagicMock(), "Quartz": MagicMock()}


def reset_modules():
    """Reset all plugin modules."""
    mods = [k for k in sys.modules if "hook" in k.lower() or "overlay" in k]
    for mod in mods:
        del sys.modules[mod]


def import_handler():
    """Import hook-handler with mocked PyObjC."""
    from importlib import import_module
    return import_module("hook-handler")


@pytest.fixture
def plugin_env(tmp_path, mocker):
    """Set up complete plugin environment."""
    reset_modules()

    # Create plugin directory structure
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()

    # Settings file
    settings = {
        "overlay": {"enabled": True, "maxHeight": 350},
        "audio": {"enabled": True, "volume": 0.5},
        "theme": "default",
    }
    (plugin_root / "settings-fx.json").write_text(json.dumps(settings))

    # Theme structure
    theme_dir = plugin_root / "themes" / "default"
    theme_dir.mkdir(parents=True)
    (theme_dir / "characters").mkdir()
    (theme_dir / "sounds").mkdir()

    manifest = {
        "states": {
            "idle": {"animation": "characters/idle.png"},
            "greeting": {"animation": "characters/greeting.png"},
            "working": {"animation": "characters/working.png"},
            "success": {"animation": "characters/success.png"},
            "error": {"animation": "characters/error.png"},
        }
    }
    (theme_dir / "manifest.json").write_text(json.dumps(manifest))

    # Scripts directory
    scripts_dir = plugin_root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "overlay.py").write_text("# overlay")

    # FX directory
    fx_dir = tmp_path / ".claude-fx"
    fx_dir.mkdir()
    (fx_dir / "setup_ok").write_text("1")

    return {
        "plugin_root": plugin_root,
        "fx_dir": fx_dir,
        "theme_dir": theme_dir,
    }


@pytest.fixture
def handler(plugin_env, mocker):
    """Provide configured hook-handler."""
    with patch.dict(sys.modules, MOCK_MODULES):
        handler = import_handler()

        # Configure paths
        handler.PLUGIN_ROOT = plugin_env["plugin_root"]
        handler.FX_DIR = plugin_env["fx_dir"]
        handler.SETUP_OK_FILE = plugin_env["fx_dir"] / "setup_ok"

        # Mock session ID
        mocker.patch.object(handler, "get_session_id", return_value=12345)
        mocker.patch.object(
            handler, "get_terminal_info",
            return_value={"pid": 99999, "window_id": 54321}
        )

        # Reset caches
        handler._terminal_info = None
        handler._session_window_id = None

        yield handler


class TestSessionStartFlow:
    """Tests for SessionStart → greeting → overlay start flow."""

    def test_session_start_maps_to_greeting(self, handler):
        """SessionStart maps to greeting state."""
        state = handler.map_event_to_state("SessionStart")
        assert state == "greeting"

    def test_session_start_triggers_overlay(self, handler, mocker):
        """SessionStart starts overlay if not running."""
        mocker.patch.object(handler, "is_overlay_running", return_value=False)
        mocker.patch.object(
            handler, "send_state_to_overlay", return_value=False
        )
        mock_popen = mocker.patch("subprocess.Popen")

        settings = handler.load_settings()

        if settings.get("overlay", {}).get("enabled", True):
            if not handler.is_overlay_running():
                handler.start_overlay()

        mock_popen.assert_called_once()


class TestToolExecutionFlow:
    """Tests for PreToolUse → PostToolUse flows."""

    def test_pre_tool_use_maps_to_working(self, handler):
        """PreToolUse maps to working state."""
        state = handler.map_event_to_state("PreToolUse")
        assert state == "working"

    def test_post_tool_success_flow(self, handler):
        """PostToolUse success maps to success state."""
        data = {"tool_result": {"output": "File written successfully"}}
        is_error = handler.detect_error(data)
        state = handler.map_event_to_state("PostToolUse", is_error)

        assert state == "success"

    def test_post_tool_error_flow(self, handler):
        """PostToolUse error maps to error state."""
        data = {"tool_result": {"error": True, "output": "File not found"}}
        is_error = handler.detect_error(data)
        state = handler.map_event_to_state("PostToolUse", is_error)

        assert state == "error"


class TestStateTransitions:
    """Tests for state machine transitions."""

    def test_all_events_map_correctly(self, handler):
        """All hook events map to correct states."""
        mappings = [
            ("SessionStart", "greeting"),
            ("PreToolUse", "working"),
            ("Stop", "celebrating"),
            ("SessionEnd", "farewell"),
            ("Notification", "idle"),
        ]

        for event, expected_state in mappings:
            state = handler.map_event_to_state(event)
            assert state == expected_state

    def test_post_tool_use_states(self, handler):
        """PostToolUse maps to success or error based on is_error flag."""
        assert handler.map_event_to_state("PostToolUse", False) == "success"
        assert handler.map_event_to_state("PostToolUse", True) == "error"


class TestSettingsIntegration:
    """Tests for settings affecting behavior."""

    def test_overlay_disabled_no_start(self, handler, plugin_env, mocker):
        """Overlay doesn't start when disabled in settings."""
        # Write disabled settings
        settings = {"overlay": {"enabled": False}}
        settings_file = plugin_env["plugin_root"] / "settings-fx.json"
        settings_file.write_text(json.dumps(settings))

        mock_popen = mocker.patch("subprocess.Popen")
        mocker.patch.object(handler, "is_overlay_running", return_value=False)

        loaded = handler.load_settings()
        if loaded.get("overlay", {}).get("enabled", True):
            handler.start_overlay()

        mock_popen.assert_not_called()

    def test_audio_disabled_no_sound(self, handler, plugin_env, mocker):
        """Sound doesn't play when audio disabled."""
        # Write disabled audio settings
        settings = {"overlay": {"enabled": True}, "audio": {"enabled": False}}
        settings_file = plugin_env["plugin_root"] / "settings-fx.json"
        settings_file.write_text(json.dumps(settings))

        mock_popen = mocker.patch("subprocess.Popen")

        loaded = handler.load_settings()
        handler.play_sound("greeting", loaded)

        mock_popen.assert_not_called()


class TestErrorDetectionPatterns:
    """Tests for error detection in tool results."""

    @pytest.mark.parametrize("error_text", [
        "error: command not found",
        "Error: permission denied",
        "ERROR in compilation",
        "Build failed",
        "ENOENT: no such file",
    ])
    def test_detects_error_patterns(self, handler, error_text):
        """Detects various error patterns."""
        data = {"tool_result": {"output": error_text}}
        assert handler.detect_error(data) is True

    @pytest.mark.parametrize("success_text", [
        "Command completed successfully",
        "File written to disk",
        "Build succeeded",
        "All tests passed",
    ])
    def test_no_false_positives(self, handler, success_text):
        """Doesn't falsely detect errors in success messages."""
        data = {"tool_result": {"output": success_text}}
        assert handler.detect_error(data) is False


class TestCleanupFlow:
    """Tests for cleanup and shutdown flows."""

    def test_cleanup_legacy_files_removes_all(self, handler, plugin_env):
        """cleanup_legacy_files removes all legacy session files."""
        fx_dir = plugin_env["fx_dir"]

        # Create legacy files
        (fx_dir / "state-12345.json").write_text("{}")
        (fx_dir / "overlay-12345.pid").write_text("99999")
        (fx_dir / "overlay-12345.lock").write_text("99999")
        (fx_dir / "state.json").write_text("{}")
        (fx_dir / "overlay.pid").write_text("99999")

        handler.cleanup_legacy_files()

        assert not (fx_dir / "state-12345.json").exists()
        assert not (fx_dir / "overlay-12345.pid").exists()
        assert not (fx_dir / "overlay-12345.lock").exists()
        assert not (fx_dir / "state.json").exists()
        assert not (fx_dir / "overlay.pid").exists()


class TestMultiSessionIsolation:
    """Tests for multi-session support."""

    def test_different_sessions_different_sockets(self, handler, mocker):
        """Different session IDs use different socket paths."""
        socket1 = handler.get_socket_path(11111)
        socket2 = handler.get_socket_path(22222)

        assert "sock-11111.sock" in str(socket1)
        assert "sock-22222.sock" in str(socket2)
        assert socket1 != socket2
