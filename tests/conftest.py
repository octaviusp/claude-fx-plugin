"""Shared pytest fixtures for claude-fx-plugin tests."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.fixtures.sample_data import (
    SAMPLE_MANIFEST,
    SAMPLE_SETTINGS,
    SAMPLE_STATE,
)

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


# =============================================================================
# PATH AND DIRECTORY FIXTURES
# =============================================================================


@pytest.fixture
def temp_fx_dir(tmp_path):
    """Create temporary .claude-fx directory."""
    fx_dir = tmp_path / ".claude-fx"
    fx_dir.mkdir()
    return fx_dir


@pytest.fixture
def temp_plugin_root(tmp_path):
    """Create temporary plugin root with theme structure."""
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()

    # Create settings file
    settings_file = plugin_root / "settings-fx.json"
    settings_file.write_text(json.dumps(SAMPLE_SETTINGS))

    # Create theme directory structure
    theme_dir = plugin_root / "themes" / "default"
    theme_dir.mkdir(parents=True)

    # Create manifest
    manifest_file = theme_dir / "manifest.json"
    manifest_file.write_text(json.dumps(SAMPLE_MANIFEST))

    # Create characters and sounds dirs
    (theme_dir / "characters").mkdir()
    (theme_dir / "sounds").mkdir()

    # Create scripts dir
    scripts_dir = plugin_root / "scripts"
    scripts_dir.mkdir()

    return plugin_root


@pytest.fixture
def temp_state_file(temp_fx_dir):
    """Create a temporary state file."""
    state_file = temp_fx_dir / "state-12345.json"
    state_file.write_text(json.dumps(SAMPLE_STATE))
    return state_file


@pytest.fixture
def temp_lock_file(temp_fx_dir):
    """Create a temporary lock file."""
    lock_file = temp_fx_dir / "overlay-12345.lock"
    lock_file.write_text("99999")  # Mock PID
    return lock_file


@pytest.fixture
def temp_pid_file(temp_fx_dir):
    """Create a temporary PID file."""
    pid_file = temp_fx_dir / "overlay-12345.pid"
    pid_file.write_text("99999")
    return pid_file


# =============================================================================
# MOCK PYOBJC FIXTURES
# =============================================================================


@pytest.fixture
def mock_pyobjc():
    """Mock all PyObjC modules for cross-platform testing."""
    from tests.fixtures.mock_pyobjc import (
        MockNSApplication,
        MockNSColor,
        MockNSImage,
        MockNSTimer,
        MockNSView,
        MockNSWindow,
        MockNSWorkspace,
        MockQuartz,
    )

    # Create MockNSObject for Foundation
    class MockNSObject:
        """Mock NSObject base class."""
        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return self

        def performSelectorOnMainThread_withObject_waitUntilDone_(
            self, selector, obj, wait
        ):
            pass

    mocks = {
        "AppKit": MagicMock(),
        "Cocoa": MagicMock(),
        "Quartz": MagicMock(),
        "objc": MagicMock(),
        "Foundation": MagicMock(),
    }

    # Set up Foundation mocks
    mocks["Foundation"].NSObject = MockNSObject

    # Set up AppKit mocks
    mocks["AppKit"].NSApplication = MockNSApplication
    mocks["AppKit"].NSWorkspace = MockNSWorkspace
    mocks["AppKit"].NSWindow = MockNSWindow
    mocks["AppKit"].NSView = MockNSView
    mocks["AppKit"].NSImage = MockNSImage
    mocks["AppKit"].NSTimer = MockNSTimer
    mocks["AppKit"].NSColor = MockNSColor

    # Set up Quartz mocks
    mocks["Quartz"].CGWindowListCopyWindowInfo = (
        MockQuartz.CGWindowListCopyWindowInfo
    )
    mocks["Quartz"].kCGWindowListOptionOnScreenOnly = 1
    mocks["Quartz"].kCGNullWindowID = 0

    with patch.dict(sys.modules, mocks):
        yield mocks


@pytest.fixture
def mock_quartz():
    """Mock just Quartz for window detection tests."""
    from tests.fixtures.mock_pyobjc import MockQuartz

    mock_func = MockQuartz.CGWindowListCopyWindowInfo
    with patch("Quartz.CGWindowListCopyWindowInfo", mock_func):
        yield MockQuartz


@pytest.fixture
def mock_nsworkspace():
    """Mock NSWorkspace for frontmost app detection."""
    from tests.fixtures.mock_pyobjc import MockNSWorkspace

    # Reset to defaults
    MockNSWorkspace._frontmost_pid = 12345
    MockNSWorkspace._frontmost_name = "Terminal"
    MockNSWorkspace._shared = None

    yield MockNSWorkspace


# =============================================================================
# SUBPROCESS FIXTURES
# =============================================================================


@pytest.fixture
def mock_subprocess_success(mocker):
    """Mock successful subprocess calls."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = ""

    mock_popen = mocker.patch("subprocess.Popen")
    mock_popen.return_value.pid = 99999

    return {"run": mock_run, "popen": mock_popen}


@pytest.fixture
def mock_subprocess_failure(mocker):
    """Mock failed subprocess calls."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = "Command failed"

    return mock_run


@pytest.fixture
def mock_ps_terminal(mocker):
    """Mock ps command output for Terminal detection."""
    mock_run = mocker.patch("subprocess.run")

    def ps_side_effect(*args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, list) and "-p" in cmd:
            # Return Terminal as parent
            result.stdout = "12345 Terminal"
        else:
            result.stdout = ""
        return result

    mock_run.side_effect = ps_side_effect
    return mock_run


@pytest.fixture
def mock_ps_no_terminal(mocker):
    """Mock ps command output with no terminal found."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "1 launchd"
    return mock_run


# =============================================================================
# FILE LOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_fcntl_unlocked(mocker):
    """Mock fcntl where lock can be acquired."""
    mock_flock = mocker.patch("fcntl.flock")
    # Lock succeeds (no exception)
    return mock_flock


@pytest.fixture
def mock_fcntl_locked(mocker):
    """Mock fcntl where lock is already held."""
    mock_flock = mocker.patch("fcntl.flock")
    mock_flock.side_effect = BlockingIOError("Lock held")
    return mock_flock


# =============================================================================
# SETTINGS AND CONFIG FIXTURES
# =============================================================================


@pytest.fixture
def mock_settings(temp_plugin_root):
    """Provide mock settings from temp plugin root."""
    return SAMPLE_SETTINGS.copy()


@pytest.fixture
def mock_settings_disabled():
    """Provide settings with overlay disabled."""
    return {
        "overlay": {"enabled": False},
        "audio": {"enabled": False},
        "theme": "default",
    }


@pytest.fixture
def mock_manifest():
    """Provide mock theme manifest."""
    return SAMPLE_MANIFEST.copy()


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================


@pytest.fixture
def mock_env(monkeypatch, temp_plugin_root, temp_fx_dir):
    """Mock environment variables."""
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(temp_plugin_root))
    monkeypatch.setenv("CLAUDE_FX_ROOT", str(temp_plugin_root))
    monkeypatch.setenv("CLAUDE_FX_SESSION", "12345")
    monkeypatch.setenv("HOME", str(temp_fx_dir.parent))
    return {
        "CLAUDE_PLUGIN_ROOT": str(temp_plugin_root),
        "CLAUDE_FX_ROOT": str(temp_plugin_root),
        "CLAUDE_FX_SESSION": "12345",
        "HOME": str(temp_fx_dir.parent),
    }


@pytest.fixture
def mock_session_id():
    """Provide mock session ID."""
    return 12345


# =============================================================================
# STDIN FIXTURES
# =============================================================================


@pytest.fixture
def mock_stdin_session_start(mocker):
    """Mock stdin with SessionStart event."""
    data = json.dumps({"hook_event_name": "SessionStart"})
    mocker.patch("sys.stdin.read", return_value=data)


@pytest.fixture
def mock_stdin_pre_tool(mocker):
    """Mock stdin with PreToolUse event."""
    data = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Read"})
    mocker.patch("sys.stdin.read", return_value=data)


@pytest.fixture
def mock_stdin_post_tool_success(mocker):
    """Mock stdin with successful PostToolUse event."""
    data = json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_result": {"output": "success"},
        }
    )
    mocker.patch("sys.stdin.read", return_value=data)


@pytest.fixture
def mock_stdin_post_tool_error(mocker):
    """Mock stdin with error PostToolUse event."""
    data = json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_result": {"error": True, "output": "Error: file not found"},
        }
    )
    mocker.patch("sys.stdin.read", return_value=data)


@pytest.fixture
def mock_stdin_empty(mocker):
    """Mock empty stdin."""
    mocker.patch("sys.stdin.read", return_value="")


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_caches():
    """Reset module-level caches between tests."""
    yield
    # Clean up after test
    try:
        from tests.fixtures.mock_pyobjc import MockNSTimer, MockQuartz

        MockNSTimer.clear_all()
        MockQuartz.clear_windows()
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def reset_hook_handler_cache():
    """Reset hook-handler caches between tests."""
    yield
    # Reset caches after test
    try:
        if "hook-handler" in sys.modules:
            handler = sys.modules["hook-handler"]
            handler._terminal_info = None
            handler._session_window_id = None
    except Exception:
        pass
