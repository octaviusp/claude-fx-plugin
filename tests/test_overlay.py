"""Tests for scripts/overlay.py - PyObjC overlay display."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Create comprehensive PyObjC mocks before importing overlay
def create_pyobjc_mocks():
    """Create all PyObjC mock modules."""
    mock_objc = MagicMock()
    mock_objc.super = lambda cls, self: MagicMock()

    mock_appkit = MagicMock()
    mock_appkit.NSWorkspace = MagicMock()
    mock_appkit.NSApplication = MagicMock()

    mock_cocoa = MagicMock()
    mock_cocoa.NSApplication = MagicMock()
    mock_cocoa.NSWindow = MagicMock()
    mock_cocoa.NSView = MagicMock()
    mock_cocoa.NSImage = MagicMock()
    mock_cocoa.NSColor = MagicMock()
    mock_cocoa.NSTimer = MagicMock()
    mock_cocoa.NSMakeRect = lambda x, y, w, h: (x, y, w, h)
    mock_cocoa.NSBackingStoreBuffered = 2
    mock_cocoa.NSFloatingWindowLevel = 3
    mock_cocoa.NSCompositingOperationSourceOver = 2
    mock_cocoa.NSScreen = MagicMock()
    mock_cocoa.NSAnimationContext = MagicMock()

    mock_quartz = MagicMock()
    mock_quartz.CGWindowListCopyWindowInfo = MagicMock(return_value=[])
    mock_quartz.kCGWindowListOptionOnScreenOnly = 1
    mock_quartz.kCGWindowListExcludeDesktopElements = 16
    mock_quartz.kCGNullWindowID = 0
    mock_quartz.CGColorCreateGenericRGB = MagicMock()

    # Mock Foundation with NSObject base class
    class MockNSObject:
        """Mock NSObject for Overlay inheritance."""
        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return self

        def performSelectorOnMainThread_withObject_waitUntilDone_(
            self, selector, obj, wait
        ):
            pass

    mock_foundation = MagicMock()
    mock_foundation.NSObject = MockNSObject

    return {
        "objc": mock_objc,
        "AppKit": mock_appkit,
        "Cocoa": mock_cocoa,
        "Quartz": mock_quartz,
        "Foundation": mock_foundation,
    }


PYOBJC_MOCKS = create_pyobjc_mocks()


def reset_overlay_module():
    """Reset overlay module for fresh import."""
    mods = [k for k in sys.modules if "overlay" in k.lower()]
    for mod in mods:
        del sys.modules[mod]


def import_overlay():
    """Import overlay with mocked dependencies."""
    from importlib import import_module

    # Add scripts to path
    scripts_path = str(Path(__file__).parent.parent / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)

    return import_module("overlay")


@pytest.fixture
def overlay_module(tmp_path, monkeypatch):
    """Provide overlay module with mocked dependencies."""
    reset_overlay_module()

    # Set environment
    monkeypatch.setenv("CLAUDE_FX_SESSION", "12345")
    monkeypatch.setenv("CLAUDE_FX_ROOT", str(tmp_path))

    # Create settings file
    settings = {
        "overlay": {
            "enabled": True,
            "maxHeight": 350,
            "offsetX": 20,
            "offsetY": 40,
            "responsive": True,
        }
    }
    settings_file = tmp_path / "settings-fx.json"
    settings_file.write_text(json.dumps(settings))

    # Create theme structure
    theme_dir = tmp_path / "themes" / "default"
    theme_dir.mkdir(parents=True)
    manifest = {
        "states": {
            "idle": {"animation": "characters/idle.png"},
            "greeting": {"animation": "characters/greeting.png"},
        }
    }
    (theme_dir / "manifest.json").write_text(json.dumps(manifest))
    (theme_dir / "characters").mkdir()

    with patch.dict(sys.modules, PYOBJC_MOCKS):
        yield import_overlay()


class TestStateDurations:
    """Tests for STATE_DURATIONS constant."""

    def test_idle_is_permanent(self, overlay_module):
        """Idle state has no duration (permanent)."""
        assert overlay_module.STATE_DURATIONS["idle"] is None

    def test_greeting_has_duration(self, overlay_module):
        """Greeting state lasts 3 seconds."""
        assert overlay_module.STATE_DURATIONS["greeting"] == 3.0

    def test_working_is_permanent(self, overlay_module):
        """Working state has no duration (permanent)."""
        assert overlay_module.STATE_DURATIONS["working"] is None

    def test_success_has_duration(self, overlay_module):
        """Success state lasts 3 seconds."""
        assert overlay_module.STATE_DURATIONS["success"] == 3.0

    def test_error_has_duration(self, overlay_module):
        """Error state lasts 3 seconds."""
        assert overlay_module.STATE_DURATIONS["error"] == 3.0

    def test_celebrating_has_duration(self, overlay_module):
        """Celebrating state lasts 3 seconds."""
        assert overlay_module.STATE_DURATIONS["celebrating"] == 3.0

    def test_farewell_has_duration(self, overlay_module):
        """Farewell state lasts 3 seconds."""
        assert overlay_module.STATE_DURATIONS["farewell"] == 3.0


class TestAnimationConstants:
    """Tests for animation constants."""

    def test_float_amplitude(self, overlay_module):
        """Float amplitude is 3 pixels."""
        assert overlay_module.FLOAT_AMPLITUDE == 3.0

    def test_float_period(self, overlay_module):
        """Float period is 2.5 seconds."""
        assert overlay_module.FLOAT_PERIOD == 2.5

    def test_aura_min_radius(self, overlay_module):
        """Aura min radius is 8 pixels."""
        assert overlay_module.AURA_MIN_RADIUS == 8.0

    def test_aura_max_radius(self, overlay_module):
        """Aura max radius is 14 pixels."""
        assert overlay_module.AURA_MAX_RADIUS == 14.0


class TestGetSocketPath:
    """Tests for get_socket_path() function."""

    def test_with_session_id(self, overlay_module, monkeypatch):
        """Returns session-specific socket path with SESSION_ID."""
        monkeypatch.setattr(overlay_module, "SESSION_ID", "99999")

        socket_path = overlay_module.get_socket_path()
        assert "sock-99999.sock" in str(socket_path)

    def test_without_session_id(self, monkeypatch, tmp_path):
        """Raises RuntimeError when SESSION_ID is not set."""
        reset_overlay_module()
        monkeypatch.delenv("CLAUDE_FX_SESSION", raising=False)
        monkeypatch.setenv("CLAUDE_FX_ROOT", str(tmp_path))

        with patch.dict(sys.modules, PYOBJC_MOCKS):
            overlay = import_overlay()
            monkeypatch.setattr(overlay, "SESSION_ID", None)

            with pytest.raises(RuntimeError, match="CLAUDE_FX_SESSION"):
                overlay.get_socket_path()


class TestLoadSettings:
    """Tests for load_settings() function."""

    def test_load_valid_settings(self, overlay_module, tmp_path):
        """Loads settings from valid JSON file."""
        settings = {
            "overlay": {"maxHeight": 500},
            "audio": {"enabled": True}
        }
        settings_file = tmp_path / "settings-fx.json"
        settings_file.write_text(json.dumps(settings))

        overlay_module.PLUGIN_ROOT = tmp_path

        result = overlay_module.load_settings()
        assert result["overlay"]["maxHeight"] == 500

    def test_load_missing_settings(self, overlay_module, tmp_path):
        """Returns empty dict when settings file missing."""
        overlay_module.PLUGIN_ROOT = tmp_path / "nonexistent"

        result = overlay_module.load_settings()
        assert result == {}

    def test_load_invalid_json(self, overlay_module, tmp_path):
        """Returns empty dict on JSON parse error."""
        settings_file = tmp_path / "settings-fx.json"
        settings_file.write_text("{ invalid }")

        overlay_module.PLUGIN_ROOT = tmp_path

        result = overlay_module.load_settings()
        assert result == {}


class TestGetTerminalPosition:
    """Tests for get_terminal_position() function."""

    def test_finds_terminal_window(self, overlay_module, mocker):
        """Finds Terminal.app window position."""
        mock_windows = [
            {
                "kCGWindowOwnerName": "Terminal",
                "kCGWindowBounds": {
                    "X": 100, "Y": 200, "Width": 800, "Height": 600
                }
            }
        ]

        # Patch at module level where it's imported
        mocker.patch.object(
            overlay_module,
            "CGWindowListCopyWindowInfo",
            return_value=mock_windows
        )

        result = overlay_module.get_terminal_position()

        assert result["x"] == 100
        assert result["y"] == 200
        assert result["w"] == 800
        assert result["h"] == 600

    def test_finds_iterm_window(self, overlay_module, mocker):
        """Finds iTerm window position."""
        mock_windows = [
            {
                "kCGWindowOwnerName": "iTerm2",
                "kCGWindowBounds": {
                    "X": 50, "Y": 100, "Width": 1024, "Height": 768
                }
            }
        ]

        mocker.patch.object(
            overlay_module,
            "CGWindowListCopyWindowInfo",
            return_value=mock_windows
        )

        result = overlay_module.get_terminal_position()

        assert result["x"] == 50
        assert result["w"] == 1024

    def test_returns_default_when_no_terminal(self, overlay_module, mocker):
        """Returns default position when no terminal found."""
        mocker.patch.object(
            overlay_module,
            "CGWindowListCopyWindowInfo",
            return_value=[]
        )

        result = overlay_module.get_terminal_position()

        assert result == {"x": 100, "y": 100, "w": 800, "h": 600}

    def test_handles_exception(self, overlay_module, mocker):
        """Returns default position on exception."""
        mocker.patch.object(
            overlay_module,
            "CGWindowListCopyWindowInfo",
            side_effect=Exception("API error")
        )

        result = overlay_module.get_terminal_position()

        assert result == {"x": 100, "y": 100, "w": 800, "h": 600}


class TestIsOurWindowFrontmost:
    """Tests for is_our_window_frontmost() function."""

    def test_returns_false_without_pid(self, overlay_module):
        """Returns False when terminal_pid is None."""
        result = overlay_module.is_our_window_frontmost(None, 12345)
        assert result is False

    def test_returns_false_when_different_app_active(
        self, overlay_module, mocker
    ):
        """Returns False when different app is frontmost."""
        mock_app = MagicMock()
        mock_app.processIdentifier.return_value = 99999  # Different PID

        mock_workspace = MagicMock()
        mock_workspace.frontmostApplication.return_value = mock_app

        # Patch at the overlay module level
        mocker.patch.object(
            overlay_module.NSWorkspace,
            "sharedWorkspace",
            return_value=mock_workspace
        )

        result = overlay_module.is_our_window_frontmost(12345, 54321)
        assert result is False

    def test_handles_exception_safely(self, overlay_module, mocker):
        """Returns True on exception (fail-open, permissive)."""
        mocker.patch.object(
            overlay_module.NSWorkspace,
            "sharedWorkspace",
            side_effect=Exception("Error")
        )

        # Fail-open: show overlay when we can't determine visibility
        result = overlay_module.is_our_window_frontmost(12345, 54321)
        assert result is True


class TestGetTerminalWindowPosition:
    """Tests for get_terminal_window_position() function."""

    def test_returns_none_without_window_id(self, overlay_module):
        """Returns None when window_id is None."""
        result = overlay_module.get_terminal_window_position(None)
        assert result is None

    def test_returns_none_when_window_id_zero(self, overlay_module):
        """Returns None when window_id is 0."""
        result = overlay_module.get_terminal_window_position(0)
        assert result is None

    def test_finds_window_by_id(self, overlay_module, mocker):
        """Finds window position by ID."""
        mock_windows = [
            {
                "kCGWindowNumber": 54321,
                "kCGWindowBounds": {
                    "X": 150, "Y": 250, "Width": 900, "Height": 700
                }
            }
        ]

        # Patch at module level where it's imported
        mocker.patch.object(
            overlay_module,
            "CGWindowListCopyWindowInfo",
            return_value=mock_windows
        )

        result = overlay_module.get_terminal_window_position(54321)

        assert result is not None
        assert result["x"] == 150
        assert result["y"] == 250
        assert result["w"] == 900
        assert result["h"] == 700

    def test_returns_none_when_window_not_found(self, overlay_module, mocker):
        """Returns None when window ID not in list."""
        mock_windows = [
            {"kCGWindowNumber": 11111, "kCGWindowBounds": {}}
        ]

        mocker.patch.object(
            overlay_module,
            "CGWindowListCopyWindowInfo",
            return_value=mock_windows
        )

        result = overlay_module.get_terminal_window_position(99999)
        assert result is None


class TestDefaultConstants:
    """Tests for default constants."""

    def test_default_max_height(self, overlay_module):
        """Default max height is 350."""
        assert overlay_module.DEFAULT_MAX_HEIGHT == 350

    def test_default_offset_x(self, overlay_module):
        """Default X offset is 20."""
        assert overlay_module.DEFAULT_OFFSET_X == 20

    def test_default_offset_y(self, overlay_module):
        """Default Y offset is 40."""
        assert overlay_module.DEFAULT_OFFSET_Y == 40

    def test_default_height_ratio(self, overlay_module):
        """Default height ratio is 0.5."""
        assert overlay_module.DEFAULT_HEIGHT_RATIO == 0.5


class TestPathConfiguration:
    """Tests for path configuration."""

    def test_fx_dir_in_home(self, overlay_module):
        """FX_DIR is in user's home directory."""
        assert ".claude-fx" in str(overlay_module.FX_DIR)

    def test_plugin_root_from_env(self, overlay_module, tmp_path, monkeypatch):
        """PLUGIN_ROOT uses CLAUDE_FX_ROOT env var."""
        reset_overlay_module()
        monkeypatch.setenv("CLAUDE_FX_ROOT", str(tmp_path / "custom"))

        with patch.dict(sys.modules, PYOBJC_MOCKS):
            overlay = import_overlay()
            assert str(tmp_path / "custom") in str(overlay.PLUGIN_ROOT)


class TestSessionIdHandling:
    """Tests for SESSION_ID handling."""

    def test_session_id_from_env(self, monkeypatch, tmp_path):
        """SESSION_ID is read from environment."""
        reset_overlay_module()
        monkeypatch.setenv("CLAUDE_FX_SESSION", "test-session-123")
        monkeypatch.setenv("CLAUDE_FX_ROOT", str(tmp_path))

        with patch.dict(sys.modules, PYOBJC_MOCKS):
            overlay = import_overlay()
            assert overlay.SESSION_ID == "test-session-123"

    def test_session_id_none_when_not_set(self, monkeypatch, tmp_path):
        """SESSION_ID is None when env var not set."""
        reset_overlay_module()
        monkeypatch.delenv("CLAUDE_FX_SESSION", raising=False)
        monkeypatch.setenv("CLAUDE_FX_ROOT", str(tmp_path))

        with patch.dict(sys.modules, PYOBJC_MOCKS):
            overlay = import_overlay()
            assert overlay.SESSION_ID is None
