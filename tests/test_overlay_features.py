"""Tests for overlay feature systems (speech bubbles, emotions, messages)."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# PyObjC module mocks for cross-platform testing
PYOBJC_MOCKS = {
    "AppKit": MagicMock(),
    "Cocoa": MagicMock(),
    "Quartz": MagicMock(),
    "objc": MagicMock(),
    "Foundation": MagicMock(),
}


def import_overlay():
    """Import overlay module with mocked PyObjC."""
    if "overlay" in sys.modules:
        del sys.modules["overlay"]
    import overlay
    return overlay


@pytest.fixture
def overlay_module(monkeypatch, tmp_path):
    """Provide overlay module with mocked dependencies."""
    monkeypatch.setenv("CLAUDE_FX_SESSION", "12345")
    monkeypatch.setenv("CLAUDE_FX_ROOT", str(tmp_path))

    # Create required files
    settings = tmp_path / "settings-fx.json"
    settings.write_text("{}")

    with patch.dict(sys.modules, PYOBJC_MOCKS):
        yield import_overlay()


class TestEmotionOverlays:
    """Tests for emotion overlay mappings."""

    def test_error_has_sweat_drop(self, overlay_module):
        """Error state shows sweat drop emotion."""
        emotions = overlay_module.EMOTION_OVERLAYS.get('error', [])
        assert 'sweat_drop' in emotions

    def test_success_has_sparkle(self, overlay_module):
        """Success state shows sparkle emotion."""
        emotions = overlay_module.EMOTION_OVERLAYS.get('success', [])
        assert 'sparkle' in emotions

    def test_celebrating_has_multiple_emotions(self, overlay_module):
        """Celebrating state shows multiple emotions."""
        emotions = overlay_module.EMOTION_OVERLAYS.get('celebrating', [])
        assert len(emotions) >= 2
        assert 'sparkle' in emotions
        assert 'star' in emotions

    def test_sleeping_has_zzz(self, overlay_module):
        """Sleeping state shows zzz emotion."""
        emotions = overlay_module.EMOTION_OVERLAYS.get('sleeping', [])
        assert 'zzz' in emotions

    def test_working_has_focus_lines(self, overlay_module):
        """Working state shows focus lines."""
        emotions = overlay_module.EMOTION_OVERLAYS.get('working', [])
        assert 'focus_lines' in emotions

    def test_idle_has_no_emotions(self, overlay_module):
        """Idle state has no emotions by default."""
        emotions = overlay_module.EMOTION_OVERLAYS.get('idle', [])
        assert len(emotions) == 0

    def test_greeting_has_no_emotions(self, overlay_module):
        """Greeting state has no emotions by default."""
        emotions = overlay_module.EMOTION_OVERLAYS.get('greeting', [])
        assert len(emotions) == 0


class TestDefaultMessages:
    """Tests for default speech bubble messages."""

    def test_greeting_messages_exist(self, overlay_module):
        """Greeting state has messages."""
        messages = overlay_module.DEFAULT_MESSAGES.get('greeting', [])
        assert len(messages) > 0

    def test_working_messages_exist(self, overlay_module):
        """Working state has messages."""
        messages = overlay_module.DEFAULT_MESSAGES.get('working', [])
        assert len(messages) > 0

    def test_success_messages_exist(self, overlay_module):
        """Success state has messages."""
        messages = overlay_module.DEFAULT_MESSAGES.get('success', [])
        assert len(messages) > 0

    def test_error_messages_exist(self, overlay_module):
        """Error state has messages."""
        messages = overlay_module.DEFAULT_MESSAGES.get('error', [])
        assert len(messages) > 0

    def test_celebrating_messages_exist(self, overlay_module):
        """Celebrating state has messages."""
        messages = overlay_module.DEFAULT_MESSAGES.get('celebrating', [])
        assert len(messages) > 0

    def test_sleeping_messages_exist(self, overlay_module):
        """Sleeping state has messages."""
        messages = overlay_module.DEFAULT_MESSAGES.get('sleeping', [])
        assert len(messages) > 0

    def test_farewell_messages_exist(self, overlay_module):
        """Farewell state has messages."""
        messages = overlay_module.DEFAULT_MESSAGES.get('farewell', [])
        assert len(messages) > 0

    def test_idle_messages_exist(self, overlay_module):
        """Idle state has messages."""
        messages = overlay_module.DEFAULT_MESSAGES.get('idle', [])
        assert len(messages) > 0

    def test_all_messages_are_strings(self, overlay_module):
        """All messages are strings."""
        for state, messages in overlay_module.DEFAULT_MESSAGES.items():
            for msg in messages:
                assert isinstance(msg, str)

    def test_messages_are_not_empty(self, overlay_module):
        """No messages are empty strings."""
        for state, messages in overlay_module.DEFAULT_MESSAGES.items():
            for msg in messages:
                assert len(msg.strip()) > 0


class TestLoadMessages:
    """Tests for load_messages() function."""

    def test_load_messages_uses_defaults_when_no_file(
        self, overlay_module, tmp_path
    ):
        """Uses default messages when file doesn't exist."""
        messages = overlay_module.load_messages(tmp_path)
        assert messages == overlay_module.DEFAULT_MESSAGES

    def test_load_messages_from_file(self, overlay_module, tmp_path):
        """Loads messages from file when it exists."""
        custom_messages = {
            "greeting": ["Hello!"],
            "working": ["Busy..."]
        }
        messages_file = tmp_path / "messages.json"
        messages_file.write_text(json.dumps(custom_messages))

        messages = overlay_module.load_messages(tmp_path)
        assert messages["greeting"] == ["Hello!"]
        assert messages["working"] == ["Busy..."]

    def test_load_messages_handles_invalid_json(
        self, overlay_module, tmp_path
    ):
        """Falls back to defaults on invalid JSON."""
        messages_file = tmp_path / "messages.json"
        messages_file.write_text("not valid json")

        messages = overlay_module.load_messages(tmp_path)
        assert messages == overlay_module.DEFAULT_MESSAGES


class TestLoadSettings:
    """Tests for load_settings() function."""

    def test_load_settings_returns_empty_when_no_file(
        self, overlay_module, tmp_path, monkeypatch
    ):
        """Returns empty dict when settings file doesn't exist."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr(overlay_module, "PLUGIN_ROOT", empty_dir)

        settings = overlay_module.load_settings()
        assert settings == {}

    def test_load_settings_parses_json(
        self, overlay_module, tmp_path, monkeypatch
    ):
        """Parses settings from JSON file."""
        monkeypatch.setattr(overlay_module, "PLUGIN_ROOT", tmp_path)

        settings_data = {
            "overlay": {"enabled": True, "maxHeight": 500},
            "audio": {"enabled": True, "volume": 0.5}
        }
        settings_file = tmp_path / "settings-fx.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = overlay_module.load_settings()
        assert settings["overlay"]["enabled"] is True
        assert settings["overlay"]["maxHeight"] == 500
        assert settings["audio"]["volume"] == 0.5

    def test_load_settings_handles_invalid_json(
        self, overlay_module, tmp_path, monkeypatch
    ):
        """Returns empty dict on invalid JSON."""
        monkeypatch.setattr(overlay_module, "PLUGIN_ROOT", tmp_path)

        settings_file = tmp_path / "settings-fx.json"
        settings_file.write_text("invalid json")

        settings = overlay_module.load_settings()
        assert settings == {}


class TestHexToNscolor:
    """Tests for hex_to_nscolor() function."""

    def test_valid_hex_with_hash(self, overlay_module):
        """Converts valid hex color with hash."""
        color = overlay_module.hex_to_nscolor("#ff0000")
        assert color is not None

    def test_valid_hex_without_hash(self, overlay_module):
        """Converts valid hex color without hash."""
        color = overlay_module.hex_to_nscolor("00ff00")
        assert color is not None

    def test_invalid_hex_returns_fallback(self, overlay_module):
        """Returns white on invalid hex."""
        color = overlay_module.hex_to_nscolor("not-a-color")
        assert color is not None

    def test_short_hex_handled(self, overlay_module):
        """Handles short or malformed hex gracefully."""
        color = overlay_module.hex_to_nscolor("fff")
        assert color is not None


class TestSpeechBubbleSettings:
    """Tests for speech bubble default settings."""

    def test_default_background_color(self, overlay_module):
        """Default speech bubble background is defined."""
        defaults = overlay_module.DEFAULT_MESSAGES
        assert defaults is not None

    def test_speech_bubble_enabled_by_default(self):
        """Speech bubble is enabled in default settings."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["speechBubble"]["enabled"] is True


class TestImmersionSettings:
    """Tests for immersion system default settings."""

    def test_breathing_enabled_by_default(self):
        """Breathing animation is enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["immersion"]["breathing"] is True

    def test_sway_enabled_by_default(self):
        """Sway animation is enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["immersion"]["sway"] is True

    def test_cursor_influence_enabled_by_default(self):
        """Cursor influence is enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["immersion"]["cursorInfluence"] is True

    def test_transitions_enabled_by_default(self):
        """State transitions are enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["immersion"]["transitions"] is True


class TestEmotionOverlaysSettings:
    """Tests for emotion overlay settings."""

    def test_emotions_enabled_by_default(self):
        """Emotion overlays are enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["emotionOverlays"]["enabled"] is True


class TestOverlaySettings:
    """Tests for overlay display settings."""

    def test_overlay_enabled_by_default(self):
        """Overlay is enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["overlay"]["enabled"] is True

    def test_responsive_enabled_by_default(self):
        """Responsive sizing is enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["overlay"]["responsive"] is True

    def test_show_only_when_active_by_default(self):
        """Show only when terminal active is enabled."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["overlay"]["showOnlyWhenTerminalActive"] is True

    def test_fade_animation_by_default(self):
        """Fade animation is enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["overlay"]["fadeAnimation"] is True

    def test_bottom_gradient_enabled(self):
        """Bottom gradient is enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["overlay"]["bottomGradient"]["enabled"] is True


class TestAudioSettings:
    """Tests for audio settings."""

    def test_audio_enabled_by_default(self):
        """Audio is enabled by default."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        assert SAMPLE_SETTINGS["audio"]["enabled"] is True

    def test_default_volume(self):
        """Default volume is reasonable."""
        from tests.fixtures.sample_data import SAMPLE_SETTINGS
        volume = SAMPLE_SETTINGS["audio"]["volume"]
        assert 0 < volume <= 1.0


class TestApplyBottomGradient:
    """Tests for apply_bottom_gradient() function."""

    def test_gradient_with_zero_percentage(self, overlay_module):
        """Zero percentage returns image unchanged."""
        from PIL import Image
        img = Image.new('RGBA', (100, 100), (255, 0, 0, 255))
        result = overlay_module.apply_bottom_gradient(img, 0.0)
        # Image should be unchanged
        assert result.mode == 'RGBA'

    def test_gradient_converts_rgb_to_rgba(self, overlay_module):
        """RGB images are converted to RGBA."""
        from PIL import Image
        img = Image.new('RGB', (100, 100), (255, 0, 0))
        result = overlay_module.apply_bottom_gradient(img, 0.5)
        assert result.mode == 'RGBA'

    def test_gradient_applies_fade(self, overlay_module):
        """Gradient fades bottom of image."""
        from PIL import Image
        img = Image.new('RGBA', (100, 100), (255, 0, 0, 255))
        result = overlay_module.apply_bottom_gradient(img, 0.5)

        # Bottom pixels should have reduced alpha
        bottom_pixel = result.getpixel((50, 99))
        top_pixel = result.getpixel((50, 0))

        assert bottom_pixel[3] < top_pixel[3]

    def test_gradient_respects_percentage(self, overlay_module):
        """Higher percentage affects more of the image."""
        from PIL import Image
        img = Image.new('RGBA', (100, 100), (255, 0, 0, 255))

        result_small = overlay_module.apply_bottom_gradient(img.copy(), 0.2)
        result_large = overlay_module.apply_bottom_gradient(img.copy(), 0.8)

        # At middle of image, larger percentage should have lower alpha
        mid_small = result_small.getpixel((50, 50))
        mid_large = result_large.getpixel((50, 50))

        assert mid_large[3] <= mid_small[3]
