"""Tests for scripts/hook-handler.py - hook event processor."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Mock modules for cross-platform testing
MOCK_MODULES = {"AppKit": MagicMock(), "Quartz": MagicMock()}


def reset_handler_module():
    """Reset hook-handler module caches."""
    mods_to_remove = [k for k in sys.modules if "hook" in k.lower()]
    for mod in mods_to_remove:
        del sys.modules[mod]


def import_handler():
    """Import hook-handler with mocked PyObjC."""
    from importlib import import_module
    return import_module("hook-handler")


@pytest.fixture
def handler():
    """Provide hook-handler module with mocked dependencies."""
    reset_handler_module()
    with patch.dict(sys.modules, MOCK_MODULES):
        yield import_handler()


class TestMapEventToState:
    """Tests for map_event_to_state() function."""

    def test_session_start_maps_to_greeting(self, handler):
        """SessionStart maps to 'greeting'."""
        assert handler.map_event_to_state("SessionStart") == "greeting"

    def test_pre_tool_use_maps_to_working(self, handler):
        """PreToolUse maps to 'working'."""
        assert handler.map_event_to_state("PreToolUse") == "working"

    def test_post_tool_use_success_maps_to_success(self, handler):
        """PostToolUse without error maps to 'success'."""
        result = handler.map_event_to_state("PostToolUse", is_error=False)
        assert result == "success"

    def test_post_tool_use_error_maps_to_error(self, handler):
        """PostToolUse with error maps to 'error'."""
        result = handler.map_event_to_state("PostToolUse", is_error=True)
        assert result == "error"

    def test_stop_maps_to_celebrating(self, handler):
        """Stop maps to 'celebrating'."""
        assert handler.map_event_to_state("Stop") == "celebrating"

    def test_session_end_maps_to_farewell(self, handler):
        """SessionEnd maps to 'farewell'."""
        assert handler.map_event_to_state("SessionEnd") == "farewell"

    def test_unknown_event_maps_to_idle(self, handler):
        """Unknown events map to 'idle'."""
        assert handler.map_event_to_state("UnknownEvent") == "idle"

    def test_notification_maps_to_idle(self, handler):
        """Notification maps to 'idle'."""
        assert handler.map_event_to_state("Notification") == "idle"


class TestDetectError:
    """Tests for detect_error() function."""

    def test_detect_error_with_error_field_true(self, handler):
        """Detect error when tool_result has error=True."""
        data = {"tool_result": {"error": True, "output": "something"}}
        assert handler.detect_error(data) is True

    def test_detect_error_with_error_pattern_lowercase(self, handler):
        """Detect error from 'error:' pattern."""
        data = {"tool_result": {"output": "error: file not found"}}
        assert handler.detect_error(data) is True

    def test_detect_error_with_error_pattern_uppercase(self, handler):
        """Detect error from 'ERROR' pattern."""
        data = {"tool_result": {"output": "ERROR: something went wrong"}}
        assert handler.detect_error(data) is True

    def test_detect_error_with_failed_pattern(self, handler):
        """Detect error from 'failed' pattern."""
        data = {"tool_result": {"output": "Command failed with exit code 1"}}
        assert handler.detect_error(data) is True

    def test_detect_error_with_enoent_pattern(self, handler):
        """Detect error from 'ENOENT' pattern."""
        data = {"tool_result": {"output": "ENOENT: no such file"}}
        assert handler.detect_error(data) is True

    def test_detect_error_no_error(self, handler):
        """No error when output is clean."""
        data = {"tool_result": {"output": "Success! File written."}}
        assert handler.detect_error(data) is False

    def test_detect_error_empty_result(self, handler):
        """No error when tool_result is empty."""
        data = {"tool_result": {}}
        assert handler.detect_error(data) is False

    def test_detect_error_string_result(self, handler):
        """Handle string tool_result."""
        data = {"tool_result": "error: something failed"}
        assert handler.detect_error(data) is True


class TestGetSocketPath:
    """Tests for get_socket_path() function."""

    def test_get_socket_path_returns_path(self, handler):
        """Returns correct socket file path."""
        socket_path = handler.get_socket_path(12345)
        assert "sock-12345.sock" in str(socket_path)
        assert ".claude-fx" in str(socket_path)

    def test_get_socket_path_in_fx_dir(self, handler):
        """Socket path is in .claude-fx directory."""
        socket_path = handler.get_socket_path(99999)
        assert ".claude-fx" in str(socket_path)


class TestLoadSettings:
    """Tests for load_settings() function."""

    def test_load_settings_valid_json(self, tmp_path, handler):
        """Loads settings from valid JSON file."""
        settings = {"overlay": {"enabled": True}, "audio": {"volume": 0.5}}
        settings_file = tmp_path / "settings-fx.json"
        settings_file.write_text(json.dumps(settings))

        handler.PLUGIN_ROOT = tmp_path

        result = handler.load_settings()
        assert result["overlay"]["enabled"] is True
        assert result["audio"]["volume"] == 0.5

    def test_load_settings_missing_file(self, tmp_path, handler):
        """Returns empty dict when settings file missing."""
        handler.PLUGIN_ROOT = tmp_path
        result = handler.load_settings()
        assert result == {}

    def test_load_settings_invalid_json(self, tmp_path, handler):
        """Returns empty dict on JSON parse error."""
        settings_file = tmp_path / "settings-fx.json"
        settings_file.write_text("{ invalid json }")

        handler.PLUGIN_ROOT = tmp_path
        result = handler.load_settings()
        assert result == {}


class TestReadStdin:
    """Tests for read_stdin() function."""

    def test_read_stdin_valid_json(self, mocker, handler):
        """Reads and parses JSON from stdin."""
        data = json.dumps({"hook_event_name": "SessionStart"})
        mocker.patch("sys.stdin.read", return_value=data)

        result = handler.read_stdin()
        assert result["hook_event_name"] == "SessionStart"

    def test_read_stdin_empty(self, mocker, handler):
        """Returns empty dict on empty stdin."""
        mocker.patch("sys.stdin.read", return_value="")

        result = handler.read_stdin()
        assert result == {}

    def test_read_stdin_invalid_json(self, mocker, handler):
        """Returns empty dict on invalid JSON."""
        mocker.patch("sys.stdin.read", return_value="not json")

        result = handler.read_stdin()
        assert result == {}


class TestSendStateToOverlay:
    """Tests for send_state_to_overlay() function."""

    def test_send_state_no_session(self, mocker, handler):
        """Returns False when no session ID."""
        mocker.patch.object(handler, "get_session_id", return_value=None)

        result = handler.send_state_to_overlay("greeting")
        assert result is False

    def test_send_state_no_socket(self, tmp_path, mocker, handler):
        """Returns False when socket file doesn't exist."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        handler.FX_DIR = fx_dir

        result = handler.send_state_to_overlay("greeting")
        assert result is False

    def test_send_state_connection_refused(self, tmp_path, mocker, handler):
        """Returns False on connection refused."""
        import socket as sock_mod
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")  # Create file but no server

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        handler.FX_DIR = fx_dir

        mock_socket = mocker.MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError()
        mocker.patch.object(
            sock_mod, "socket", return_value=mock_socket
        )

        result = handler.send_state_to_overlay("greeting")
        assert result is False


class TestIsOverlayRunning:
    """Tests for is_overlay_running() function."""

    def test_is_overlay_running_no_session(self, mocker, handler):
        """Returns False when no session ID."""
        mocker.patch.object(handler, "get_session_id", return_value=None)

        result = handler.is_overlay_running()
        assert result is False

    def test_is_overlay_running_no_socket(self, tmp_path, mocker, handler):
        """Returns False when socket file doesn't exist."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        handler.FX_DIR = fx_dir

        result = handler.is_overlay_running()
        assert result is False

    def test_is_overlay_running_connection_error(
        self, tmp_path, mocker, handler
    ):
        """Returns False on socket connection error."""
        import socket as sock_mod
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        handler.FX_DIR = fx_dir

        mock_socket = mocker.MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError()
        mocker.patch.object(
            sock_mod, "socket", return_value=mock_socket
        )

        result = handler.is_overlay_running()
        assert result is False


class TestStartOverlay:
    """Tests for start_overlay() function."""

    def test_start_overlay_spawns_process(self, tmp_path, mocker, handler):
        """Starts overlay process successfully."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        overlay_script = scripts_dir / "overlay.py"
        overlay_script.write_text("# overlay")

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        handler.PLUGIN_ROOT = tmp_path

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value.pid = 99999

        handler.start_overlay()

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert "overlay.py" in str(call_args)

    def test_start_overlay_sets_env(self, tmp_path, mocker, handler):
        """Sets correct environment variables."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        overlay_script = scripts_dir / "overlay.py"
        overlay_script.write_text("# overlay")

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        handler.PLUGIN_ROOT = tmp_path

        mock_popen = mocker.patch("subprocess.Popen")

        handler.start_overlay()

        call_kwargs = mock_popen.call_args.kwargs
        env = call_kwargs.get("env", {})
        assert env.get("CLAUDE_FX_ROOT") == str(tmp_path)
        assert env.get("CLAUDE_FX_SESSION") == "12345"


class TestShutdownOverlay:
    """Tests for shutdown_overlay() function."""

    def test_shutdown_overlay_no_session(self, mocker, handler):
        """Does nothing when no session ID."""
        mocker.patch.object(handler, "get_session_id", return_value=None)
        # Should not raise
        handler.shutdown_overlay()

    def test_shutdown_overlay_no_socket(self, tmp_path, mocker, handler):
        """Does nothing when socket file doesn't exist."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        handler.FX_DIR = fx_dir

        # Should not raise
        handler.shutdown_overlay()


class TestCleanupLegacyFiles:
    """Tests for cleanup_legacy_files() function."""

    def test_cleanup_removes_state_files(self, tmp_path, handler):
        """Removes legacy state JSON files."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        state_file = fx_dir / "state-12345.json"
        state_file.write_text("{}")

        handler.FX_DIR = fx_dir
        handler.cleanup_legacy_files()

        assert not state_file.exists()

    def test_cleanup_removes_pid_files(self, tmp_path, handler):
        """Removes legacy PID files."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        pid_file = fx_dir / "overlay-12345.pid"
        pid_file.write_text("99999")

        handler.FX_DIR = fx_dir
        handler.cleanup_legacy_files()

        assert not pid_file.exists()

    def test_cleanup_removes_lock_files(self, tmp_path, handler):
        """Removes legacy lock files."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        lock_file = fx_dir / "overlay-12345.lock"
        lock_file.write_text("99999")

        handler.FX_DIR = fx_dir
        handler.cleanup_legacy_files()

        assert not lock_file.exists()

    def test_cleanup_handles_missing_dir(self, tmp_path, handler):
        """Handles missing FX_DIR gracefully."""
        fx_dir = tmp_path / ".claude-fx"
        # Don't create directory

        handler.FX_DIR = fx_dir
        # Should not raise
        handler.cleanup_legacy_files()


class TestPlaySound:
    """Tests for play_sound() function."""

    def test_play_sound_enabled(self, tmp_path, mocker, handler):
        """Plays sound when audio enabled."""
        theme_dir = tmp_path / "themes" / "default" / "sounds"
        theme_dir.mkdir(parents=True)
        sound_file = theme_dir / "greeting.wav"
        sound_file.write_text("sound data")

        handler.PLUGIN_ROOT = tmp_path

        mock_popen = mocker.patch("subprocess.Popen")

        settings = {
            "audio": {"enabled": True, "volume": 0.7},
            "theme": "default"
        }
        handler.play_sound("greeting", settings)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert "afplay" in call_args
        assert "0.7" in call_args

    def test_play_sound_disabled(self, mocker, handler):
        """Skips sound when audio disabled."""
        mock_popen = mocker.patch("subprocess.Popen")

        settings = {"audio": {"enabled": False}}
        handler.play_sound("greeting", settings)

        mock_popen.assert_not_called()

    def test_play_sound_missing_file(self, tmp_path, mocker, handler):
        """Handles missing sound file gracefully."""
        handler.PLUGIN_ROOT = tmp_path

        mock_popen = mocker.patch("subprocess.Popen")

        settings = {"audio": {"enabled": True}, "theme": "default"}
        handler.play_sound("greeting", settings)

        mock_popen.assert_not_called()

    def test_play_sound_unknown_state(self, mocker, handler):
        """Handles unknown state gracefully."""
        mock_popen = mocker.patch("subprocess.Popen")

        settings = {"audio": {"enabled": True}}
        handler.play_sound("unknown_state", settings)

        mock_popen.assert_not_called()


class TestLoadManifest:
    """Tests for load_manifest() function."""

    def test_load_manifest_valid(self, tmp_path, handler):
        """Loads valid manifest.json."""
        theme_dir = tmp_path / "themes" / "default"
        theme_dir.mkdir(parents=True)
        manifest = {"name": "test", "states": {"idle": {"sound": None}}}
        (theme_dir / "manifest.json").write_text(json.dumps(manifest))

        handler.PLUGIN_ROOT = tmp_path
        result = handler.load_manifest("default")

        assert result["name"] == "test"

    def test_load_manifest_missing(self, tmp_path, handler):
        """Returns empty dict for missing manifest."""
        handler.PLUGIN_ROOT = tmp_path
        result = handler.load_manifest("nonexistent")
        assert result == {}

    def test_load_manifest_invalid_json(self, tmp_path, handler):
        """Returns empty dict for invalid JSON."""
        theme_dir = tmp_path / "themes" / "default"
        theme_dir.mkdir(parents=True)
        (theme_dir / "manifest.json").write_text("{ invalid }")

        handler.PLUGIN_ROOT = tmp_path
        result = handler.load_manifest("default")
        assert result == {}


class TestFindSoundFile:
    """Tests for find_sound_file() function."""

    def test_find_sound_from_manifest(self, tmp_path, handler):
        """Finds sound file via manifest path."""
        theme_dir = tmp_path / "themes" / "default"
        sounds_dir = theme_dir / "sounds"
        sounds_dir.mkdir(parents=True)
        (sounds_dir / "custom.mp3").write_text("sound")

        manifest = {"states": {"greeting": {"sound": "sounds/custom.mp3"}}}
        handler.PLUGIN_ROOT = tmp_path

        result = handler.find_sound_file("greeting", "default", manifest)
        assert result.name == "custom.mp3"

    def test_find_sound_fallback_to_state_name(self, tmp_path, handler):
        """Falls back to state-named file when manifest has no sound."""
        theme_dir = tmp_path / "themes" / "default"
        sounds_dir = theme_dir / "sounds"
        sounds_dir.mkdir(parents=True)
        (sounds_dir / "greeting.aiff").write_text("sound")

        manifest = {"states": {"greeting": {"sound": None}}}
        handler.PLUGIN_ROOT = tmp_path

        result = handler.find_sound_file("greeting", "default", manifest)
        assert result.name == "greeting.aiff"

    def test_find_sound_multiple_formats(self, tmp_path, handler):
        """Finds sound in any supported format."""
        theme_dir = tmp_path / "themes" / "default"
        sounds_dir = theme_dir / "sounds"
        sounds_dir.mkdir(parents=True)

        handler.PLUGIN_ROOT = tmp_path

        # Test each supported format
        for ext in [".wav", ".mp3", ".m4a", ".aiff", ".caf"]:
            sound_file = sounds_dir / f"test{ext}"
            sound_file.write_text("sound")

            manifest = {}
            result = handler.find_sound_file("test", "default", manifest)
            assert result is not None
            assert result.suffix == ext

            sound_file.unlink()

    def test_find_sound_not_found(self, tmp_path, handler):
        """Returns None when no sound file exists."""
        theme_dir = tmp_path / "themes" / "default"
        sounds_dir = theme_dir / "sounds"
        sounds_dir.mkdir(parents=True)

        handler.PLUGIN_ROOT = tmp_path
        manifest = {}

        result = handler.find_sound_file("nonexistent", "default", manifest)
        assert result is None


class TestGetTerminalInfo:
    """Tests for get_terminal_info() function."""

    def test_get_terminal_info_finds_terminal(self, handler, mocker):
        """Successfully detects Terminal.app."""
        # Set up mock for subprocess.run
        call_count = [0]

        def ps_side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            result.returncode = 0
            # Simulate process tree: current -> bash -> Terminal
            if call_count[0] <= 3:
                result.stdout = "12345 Terminal"
            else:
                result.stdout = "1 launchd"
            return result

        mocker.patch("subprocess.run", side_effect=ps_side_effect)

        # Reset cache and simulate cached result
        handler._terminal_info = {"pid": 12345, "window_id": 54321}

        result = handler.get_terminal_info()
        assert result is not None
        assert result["pid"] == 12345
        assert result["window_id"] == 54321

    def test_get_terminal_info_no_terminal(self, mocker, handler):
        """Returns None when no terminal in process tree."""
        def ps_side_effect(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "1 launchd"
            return result

        mocker.patch("subprocess.run", side_effect=ps_side_effect)
        handler._terminal_info = None

        result = handler.get_terminal_info()
        assert result is None

    def test_get_terminal_info_caching(self, mocker, handler):
        """Terminal info is cached across calls."""
        handler._terminal_info = {"pid": 11111, "window_id": 22222}

        mock_run = mocker.patch("subprocess.run")

        result = handler.get_terminal_info()
        assert result["pid"] == 11111
        mock_run.assert_not_called()
