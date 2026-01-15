"""Tests for scripts/hook-handler.py - hook event processor."""

import json
import sys
import time
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


class TestSendSoundToOverlay:
    """Tests for send_sound_to_overlay() function."""

    def test_send_sound_no_session_id(self, mocker, handler):
        """Returns False when no session ID."""
        mocker.patch.object(handler, "get_session_id", return_value=None)

        result = handler.send_sound_to_overlay("greeting")
        assert result is False

    def test_send_sound_no_socket(self, tmp_path, mocker, handler):
        """Returns False when socket doesn't exist."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        handler.FX_DIR = fx_dir

        mocker.patch.object(handler, "get_session_id", return_value=12345)

        result = handler.send_sound_to_overlay("greeting")
        assert result is False

    def test_send_sound_success(self, tmp_path, mocker, handler):
        """Successfully sends sound command via socket."""
        import socket as sock_mod

        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")
        handler.FX_DIR = fx_dir

        mocker.patch.object(handler, "get_session_id", return_value=12345)

        mock_socket = MagicMock()
        mock_socket.recv.return_value = b'{"status": "ok"}'
        mocker.patch.object(sock_mod, "socket", return_value=mock_socket)

        result = handler.send_sound_to_overlay("greeting")

        assert result is True
        mock_socket.connect.assert_called_once()
        mock_socket.sendall.assert_called_once()

    def test_send_sound_socket_error(self, tmp_path, mocker, handler):
        """Returns False on socket error."""
        import socket as sock_mod

        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")
        handler.FX_DIR = fx_dir

        mocker.patch.object(handler, "get_session_id", return_value=12345)

        mock_socket = MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError
        mocker.patch.object(sock_mod, "socket", return_value=mock_socket)

        result = handler.send_sound_to_overlay("greeting")
        assert result is False


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

        # Reset cache and simulate cached result (with valid TTL)
        handler._terminal_info = {
            "shell_pid": 12345,
            "terminal_pid": 67890,
            "window_id": 54321
        }
        handler._terminal_info_time = time.time()  # Set valid cache time

        result = handler.get_terminal_info()
        assert result is not None
        assert result["shell_pid"] == 12345
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
        handler._terminal_info = {
            "shell_pid": 11111,
            "terminal_pid": 33333,
            "window_id": 22222
        }
        handler._terminal_info_time = time.time()  # Set valid cache time

        mock_run = mocker.patch("subprocess.run")

        result = handler.get_terminal_info()
        assert result["shell_pid"] == 11111
        mock_run.assert_not_called()


# =============================================================================
# PHASE 1: MAIN FUNCTION TESTS
# =============================================================================


class TestMainFunction:
    """Tests for main() function - the entry point for all hook events."""

    def test_main_session_start_runs_setup_and_starts_overlay(
        self, tmp_path, mocker, handler
    ):
        """SessionStart checks setup and starts overlay."""
        # Setup environment
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        setup_ok = fx_dir / "setup_ok"
        setup_ok.write_text("ok")

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "overlay.py").write_text("# overlay")

        handler.FX_DIR = fx_dir
        handler.SETUP_OK_FILE = setup_ok
        handler.PLUGIN_ROOT = tmp_path

        # Mock stdin with SessionStart event
        data = json.dumps({"hook_event_name": "SessionStart"})
        mocker.patch("sys.stdin.read", return_value=data)

        # Mock session ID and overlay functions
        mocker.patch.object(handler, "get_session_id", return_value=12345)
        mocker.patch.object(handler, "is_overlay_running", return_value=False)
        mock_start = mocker.patch.object(handler, "start_overlay")
        mocker.patch.object(
            handler, "send_state_to_overlay", return_value=False
        )
        mocker.patch.object(handler, "send_sound_to_overlay")
        mocker.patch.object(handler, "cleanup_legacy_files")
        mocker.patch.object(handler, "check_setup", return_value=True)

        # Run main (will call sys.exit)
        with pytest.raises(SystemExit) as exc_info:
            handler.main()

        assert exc_info.value.code == 0
        mock_start.assert_called_once()

    def test_main_session_end_plays_farewell_and_shuts_down(
        self, tmp_path, mocker, handler
    ):
        """SessionEnd plays farewell sound and shuts down overlay."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        setup_ok = fx_dir / "setup_ok"
        setup_ok.write_text("ok")

        handler.FX_DIR = fx_dir
        handler.SETUP_OK_FILE = setup_ok
        handler.PLUGIN_ROOT = tmp_path

        data = json.dumps({"hook_event_name": "SessionEnd"})
        mocker.patch("sys.stdin.read", return_value=data)

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        mock_send = mocker.patch.object(handler, "send_state_to_overlay")
        mock_sound = mocker.patch.object(handler, "send_sound_to_overlay")
        mock_shutdown = mocker.patch.object(handler, "shutdown_overlay")
        mock_orphans = mocker.patch.object(handler, "kill_orphaned_overlays")
        mocker.patch("time.sleep")

        with pytest.raises(SystemExit) as exc_info:
            handler.main()

        assert exc_info.value.code == 0
        mock_send.assert_called_once_with("farewell", None)
        mock_sound.assert_called_once_with("farewell")
        mock_shutdown.assert_called_once()
        mock_orphans.assert_called_once()

    def test_main_pre_tool_use_sends_working_state(
        self, tmp_path, mocker, handler
    ):
        """PreToolUse sends 'working' state to overlay."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        setup_ok = fx_dir / "setup_ok"
        setup_ok.write_text("ok")

        handler.FX_DIR = fx_dir
        handler.SETUP_OK_FILE = setup_ok
        handler.PLUGIN_ROOT = tmp_path

        data = json.dumps({
            "hook_event_name": "PreToolUse", "tool_name": "Read"
        })
        mocker.patch("sys.stdin.read", return_value=data)

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        mock_send = mocker.patch.object(
            handler, "send_state_to_overlay", return_value=True
        )
        mocker.patch.object(handler, "send_sound_to_overlay")

        with pytest.raises(SystemExit):
            handler.main()

        mock_send.assert_called_with("working", "Read")

    def test_main_post_tool_use_success_sends_success_state(
        self, tmp_path, mocker, handler
    ):
        """PostToolUse with success sends 'success' state."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        setup_ok = fx_dir / "setup_ok"
        setup_ok.write_text("ok")

        handler.FX_DIR = fx_dir
        handler.SETUP_OK_FILE = setup_ok
        handler.PLUGIN_ROOT = tmp_path

        data = json.dumps({
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_result": {"output": "file contents"}
        })
        mocker.patch("sys.stdin.read", return_value=data)

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        mock_send = mocker.patch.object(
            handler, "send_state_to_overlay", return_value=True
        )
        mocker.patch.object(handler, "send_sound_to_overlay")

        with pytest.raises(SystemExit):
            handler.main()

        mock_send.assert_called_with("success", "Read")

    def test_main_post_tool_use_error_sends_error_state(
        self, tmp_path, mocker, handler
    ):
        """PostToolUse with error sends 'error' state."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        setup_ok = fx_dir / "setup_ok"
        setup_ok.write_text("ok")

        handler.FX_DIR = fx_dir
        handler.SETUP_OK_FILE = setup_ok
        handler.PLUGIN_ROOT = tmp_path

        data = json.dumps({
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_result": {"error": True, "output": "Error: file not found"}
        })
        mocker.patch("sys.stdin.read", return_value=data)

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        mock_send = mocker.patch.object(
            handler, "send_state_to_overlay", return_value=True
        )
        mocker.patch.object(handler, "send_sound_to_overlay")

        with pytest.raises(SystemExit):
            handler.main()

        mock_send.assert_called_with("error", "Read")

    def test_main_stop_sends_celebrating_state(
        self, tmp_path, mocker, handler
    ):
        """Stop event sends 'celebrating' state."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        setup_ok = fx_dir / "setup_ok"
        setup_ok.write_text("ok")

        handler.FX_DIR = fx_dir
        handler.SETUP_OK_FILE = setup_ok
        handler.PLUGIN_ROOT = tmp_path

        data = json.dumps({"hook_event_name": "Stop"})
        mocker.patch("sys.stdin.read", return_value=data)

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        mock_send = mocker.patch.object(
            handler, "send_state_to_overlay", return_value=True
        )
        mocker.patch.object(handler, "send_sound_to_overlay")

        with pytest.raises(SystemExit):
            handler.main()

        mock_send.assert_called_with("celebrating", None)

    def test_main_change_character_cli_command(self, mocker, handler):
        """CLI change-character command works."""
        mocker.patch.object(
            handler, "change_character_folder",
            return_value={"status": "ok", "folder": "characters2"}
        )
        mocker.patch.object(
            sys, "argv",
            ["hook-handler.py", "change-character", "characters2"]
        )

        with pytest.raises(SystemExit) as exc_info:
            handler.main()

        assert exc_info.value.code == 0

    def test_main_overlay_disabled_skips_overlay_operations(
        self, tmp_path, mocker, handler
    ):
        """When overlay disabled, plays sounds but doesn't start overlay."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        setup_ok = fx_dir / "setup_ok"
        setup_ok.write_text("ok")

        settings_file = tmp_path / "settings-fx.json"
        settings_file.write_text(json.dumps({
            "overlay": {"enabled": False},
            "audio": {"enabled": True}
        }))

        handler.FX_DIR = fx_dir
        handler.SETUP_OK_FILE = setup_ok
        handler.PLUGIN_ROOT = tmp_path

        data = json.dumps({
            "hook_event_name": "PreToolUse", "tool_name": "Bash"
        })
        mocker.patch("sys.stdin.read", return_value=data)

        mocker.patch.object(handler, "get_session_id", return_value=12345)
        mocker.patch.object(
            handler, "send_state_to_overlay", return_value=False
        )
        mock_start = mocker.patch.object(handler, "start_overlay")
        mocker.patch.object(handler, "is_overlay_running", return_value=False)
        mock_sound = mocker.patch.object(handler, "send_sound_to_overlay")

        with pytest.raises(SystemExit):
            handler.main()

        # Should not start overlay when disabled
        mock_start.assert_not_called()
        # But should still play sounds
        mock_sound.assert_called_once()

    def test_main_empty_event_exits_immediately(self, mocker, handler):
        """Empty event name exits without action."""
        mocker.patch("sys.stdin.read", return_value="{}")

        with pytest.raises(SystemExit) as exc_info:
            handler.main()

        assert exc_info.value.code == 0


# =============================================================================
# PROCESS MANAGEMENT TESTS
# =============================================================================


class TestCleanupSessionFiles:
    """Tests for _cleanup_session_files() function."""

    def test_cleanup_removes_socket_and_pid(self, tmp_path, handler):
        """Removes both socket and PID files."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        pid_file = fx_dir / "pid-12345.txt"
        socket_file.write_text("")
        pid_file.write_text("99999")

        handler.FX_DIR = fx_dir

        handler._cleanup_session_files(12345)

        assert not socket_file.exists()
        assert not pid_file.exists()

    def test_cleanup_handles_missing_socket(self, tmp_path, handler):
        """Handles missing socket file gracefully."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        pid_file = fx_dir / "pid-12345.txt"
        pid_file.write_text("99999")

        handler.FX_DIR = fx_dir

        # Should not raise
        handler._cleanup_session_files(12345)
        assert not pid_file.exists()

    def test_cleanup_handles_missing_pid(self, tmp_path, handler):
        """Handles missing PID file gracefully."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")

        handler.FX_DIR = fx_dir

        # Should not raise
        handler._cleanup_session_files(12345)
        assert not socket_file.exists()

    def test_cleanup_handles_permission_error(self, tmp_path, mocker, handler):
        """Handles permission error gracefully."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")

        handler.FX_DIR = fx_dir

        # Mock unlink to raise PermissionError
        mocker.patch.object(Path, "unlink", side_effect=PermissionError)

        # Should not raise
        handler._cleanup_session_files(12345)


class TestKillOrphanedOverlays:
    """Tests for kill_orphaned_overlays() function."""

    def test_kills_processes_without_pid_files(
        self, tmp_path, mocker, handler
    ):
        """Kills overlay processes that don't have PID files."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()

        handler.FX_DIR = fx_dir

        # pgrep returns PIDs 111, 222, 333
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "111\n222\n333"

        mock_kill = mocker.patch("os.kill")

        handler.kill_orphaned_overlays()

        # All 3 should be killed (no PID files exist)
        assert mock_kill.call_count == 3

    def test_preserves_valid_sessions(self, tmp_path, mocker, handler):
        """Doesn't kill overlays that have valid PID files."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()

        # Create PID file for process 222
        pid_file = fx_dir / "pid-99999.txt"
        pid_file.write_text("222")

        handler.FX_DIR = fx_dir

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "111\n222\n333"

        mock_kill = mocker.patch("os.kill")

        handler.kill_orphaned_overlays()

        # Only 111 and 333 should be killed (222 has a PID file)
        assert mock_kill.call_count == 2
        killed_pids = [call[0][0] for call in mock_kill.call_args_list]
        assert 222 not in killed_pids
        assert 111 in killed_pids
        assert 333 in killed_pids

    def test_handles_pgrep_failure(self, mocker, handler):
        """Handles pgrep returning no results."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""

        mock_kill = mocker.patch("os.kill")

        # Should not raise
        handler.kill_orphaned_overlays()
        mock_kill.assert_not_called()

    def test_handles_kill_exception(self, tmp_path, mocker, handler):
        """Handles os.kill exceptions gracefully."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        handler.FX_DIR = fx_dir

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "111"

        mocker.patch("os.kill", side_effect=ProcessLookupError)

        # Should not raise
        handler.kill_orphaned_overlays()


class TestEnhancedShutdownOverlay:
    """Additional tests for shutdown_overlay() with fallback behavior."""

    def test_shutdown_sends_socket_command_successfully(
        self, tmp_path, mocker, handler
    ):
        """Successfully shuts down via socket."""
        import socket as sock_mod

        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")

        handler.FX_DIR = fx_dir
        mocker.patch.object(handler, "get_session_id", return_value=12345)

        mock_socket = MagicMock()
        mock_socket.recv.return_value = b'{"status": "ok"}'
        mocker.patch.object(sock_mod, "socket", return_value=mock_socket)

        handler.shutdown_overlay()

        mock_socket.connect.assert_called_once()
        mock_socket.sendall.assert_called_once()

    def test_shutdown_falls_back_to_sigterm_on_socket_failure(
        self, tmp_path, mocker, handler
    ):
        """Falls back to SIGTERM when socket fails."""
        import socket as sock_mod

        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")
        pid_file = fx_dir / "pid-12345.txt"
        pid_file.write_text("99999")

        handler.FX_DIR = fx_dir
        mocker.patch.object(handler, "get_session_id", return_value=12345)

        # Socket fails
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError()
        mocker.patch.object(sock_mod, "socket", return_value=mock_socket)

        # Mock os.kill - first call succeeds, second raises (process dead)
        mock_kill = mocker.patch("os.kill")
        mock_kill.side_effect = [None, ProcessLookupError()]

        mocker.patch("time.sleep")

        handler.shutdown_overlay()

        # Should have tried SIGTERM
        import signal
        mock_kill.assert_any_call(99999, signal.SIGTERM)

    def test_shutdown_escalates_to_sigkill_if_process_alive(
        self, tmp_path, mocker, handler
    ):
        """Escalates to SIGKILL if process still alive after SIGTERM."""

        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        pid_file = fx_dir / "pid-12345.txt"
        pid_file.write_text("99999")

        handler.FX_DIR = fx_dir
        mocker.patch.object(handler, "get_session_id", return_value=12345)

        # No socket file
        mock_kill = mocker.patch("os.kill")
        # Process alive after SIGTERM (kill(pid, 0) succeeds)
        mock_kill.side_effect = [None, None, None]

        mocker.patch("time.sleep")

        handler.shutdown_overlay()

        # Should call: SIGTERM, check alive (0), SIGKILL
        assert mock_kill.call_count >= 2

    def test_shutdown_cleans_up_files_regardless_of_method(
        self, tmp_path, mocker, handler
    ):
        """Always cleans up files even if shutdown fails."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")
        pid_file = fx_dir / "pid-12345.txt"
        pid_file.write_text("99999")

        handler.FX_DIR = fx_dir
        mocker.patch.object(handler, "get_session_id", return_value=12345)

        # Socket fails, kill fails with expected exceptions
        import socket as sock_mod
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError()
        mocker.patch.object(sock_mod, "socket", return_value=mock_socket)
        mocker.patch("os.kill", side_effect=PermissionError("kill error"))

        handler.shutdown_overlay()

        # Files should be cleaned up regardless
        assert not socket_file.exists()
        assert not pid_file.exists()


class TestChangeCharacterFolder:
    """Tests for change_character_folder() function."""

    def test_change_character_folder_success(self, tmp_path, mocker, handler):
        """Successfully changes character folder."""
        import socket as sock_mod

        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")

        handler.FX_DIR = fx_dir
        mocker.patch.object(handler, "get_session_id", return_value=12345)

        mock_socket = MagicMock()
        response = b'{"status": "ok", "folder": "characters2"}'
        mock_socket.recv.return_value = response
        mocker.patch.object(sock_mod, "socket", return_value=mock_socket)

        result = handler.change_character_folder("characters2")

        assert result["status"] == "ok"
        assert result["folder"] == "characters2"

    def test_change_character_folder_no_session(self, mocker, handler):
        """Returns error when no session."""
        mocker.patch.object(handler, "get_session_id", return_value=None)

        result = handler.change_character_folder("characters2")

        assert result["status"] == "error"
        assert "no session" in result["message"]

    def test_change_character_folder_overlay_not_running(
        self, tmp_path, mocker, handler
    ):
        """Returns error when overlay not running."""
        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        # No socket file

        handler.FX_DIR = fx_dir
        mocker.patch.object(handler, "get_session_id", return_value=12345)

        result = handler.change_character_folder("characters2")

        assert result["status"] == "error"
        assert "not running" in result["message"]

    def test_change_character_folder_socket_error(
        self, tmp_path, mocker, handler
    ):
        """Returns error on socket failure."""
        import socket as sock_mod

        fx_dir = tmp_path / ".claude-fx"
        fx_dir.mkdir()
        socket_file = fx_dir / "sock-12345.sock"
        socket_file.write_text("")

        handler.FX_DIR = fx_dir
        mocker.patch.object(handler, "get_session_id", return_value=12345)

        mock_socket = MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError("refused")
        mocker.patch.object(sock_mod, "socket", return_value=mock_socket)

        result = handler.change_character_folder("characters2")

        assert result["status"] == "error"
