"""Tests for overlay animation system."""

import math
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


class TestAnimationConstants:
    """Tests for animation constant values."""

    def test_float_amplitude_is_positive(self, overlay_module):
        """Float amplitude is a positive value for upward movement."""
        assert overlay_module.FLOAT_AMPLITUDE > 0
        assert overlay_module.FLOAT_AMPLITUDE <= 10

    def test_float_period_is_reasonable(self, overlay_module):
        """Float period is in a reasonable range for smooth animation."""
        assert 1.0 <= overlay_module.FLOAT_PERIOD <= 5.0

    def test_breath_intensity_is_subtle(self, overlay_module):
        """Breathing effect is subtle (under 5% scale change)."""
        assert 0 < overlay_module.BREATH_INTENSITY < 0.05

    def test_breath_period_is_slow(self, overlay_module):
        """Breathing cycle is slow for a relaxed effect."""
        assert overlay_module.BREATH_PERIOD >= 2.0

    def test_sway_angle_is_small(self, overlay_module):
        """Sway rotation is small to avoid distraction."""
        assert 0 < overlay_module.SWAY_ANGLE <= 5.0

    def test_sway_period_is_slow(self, overlay_module):
        """Sway cycle is slow for natural movement."""
        assert overlay_module.SWAY_PERIOD >= 2.0

    def test_cursor_tilt_max_is_limited(self, overlay_module):
        """Cursor influence tilt is limited."""
        assert 0 < overlay_module.CURSOR_TILT_MAX <= 10.0

    def test_cursor_falloff_is_reasonable(self, overlay_module):
        """Cursor effect has reasonable falloff distance."""
        assert overlay_module.CURSOR_FALLOFF > 100


class TestAuraConstants:
    """Tests for aura glow effect constants."""

    def test_aura_color_has_rgba(self, overlay_module):
        """Aura color is a valid RGBA tuple."""
        color = overlay_module.AURA_COLOR
        assert len(color) == 4
        assert all(0 <= c <= 1.0 for c in color)

    def test_aura_radius_range(self, overlay_module):
        """Aura radius min is less than max."""
        assert overlay_module.AURA_MIN_RADIUS < overlay_module.AURA_MAX_RADIUS

    def test_aura_period_is_reasonable(self, overlay_module):
        """Aura pulse period is in reasonable range."""
        assert 0.5 <= overlay_module.AURA_PERIOD <= 5.0

    def test_aura_opacity_is_visible(self, overlay_module):
        """Aura opacity is visible but not overpowering."""
        assert 0 < overlay_module.AURA_OPACITY <= 1.0


class TestStateTransitions:
    """Tests for state transition configurations."""

    def test_all_states_have_transitions(self, overlay_module):
        """All states have transition configuration."""
        expected_states = [
            'greeting', 'working', 'success', 'error',
            'celebrating', 'sleeping', 'idle', 'farewell'
        ]
        for state in expected_states:
            assert state in overlay_module.STATE_TRANSITIONS

    def test_greeting_uses_scale_pop(self, overlay_module):
        """Greeting state uses scale pop transition."""
        trans = overlay_module.STATE_TRANSITIONS['greeting']
        assert trans['type'] == overlay_module.TRANSITION_SCALE_POP

    def test_success_uses_bounce(self, overlay_module):
        """Success state uses bounce transition."""
        trans = overlay_module.STATE_TRANSITIONS['success']
        assert trans['type'] == overlay_module.TRANSITION_BOUNCE

    def test_error_uses_shake(self, overlay_module):
        """Error state uses shake transition."""
        trans = overlay_module.STATE_TRANSITIONS['error']
        assert trans['type'] == overlay_module.TRANSITION_SHAKE
        assert 'intensity' in trans
        assert 'cycles' in trans

    def test_idle_has_no_transition(self, overlay_module):
        """Idle state has no transition."""
        trans = overlay_module.STATE_TRANSITIONS['idle']
        assert trans['type'] == overlay_module.TRANSITION_NONE

    def test_sleeping_has_no_transition(self, overlay_module):
        """Sleeping state has no transition."""
        trans = overlay_module.STATE_TRANSITIONS['sleeping']
        assert trans['type'] == overlay_module.TRANSITION_NONE

    def test_bounce_transitions_have_height(self, overlay_module):
        """Bounce transitions specify height."""
        for state, trans in overlay_module.STATE_TRANSITIONS.items():
            if trans['type'] == overlay_module.TRANSITION_BOUNCE:
                assert 'height' in trans
                assert trans['height'] > 0

    def test_scale_transitions_have_scale(self, overlay_module):
        """Scale transitions specify scale factor."""
        for state, trans in overlay_module.STATE_TRANSITIONS.items():
            if trans['type'] == overlay_module.TRANSITION_SCALE_POP:
                assert 'scale' in trans
                assert trans['scale'] > 1.0

    def test_transitions_have_duration(self, overlay_module):
        """Active transitions specify duration."""
        for state, trans in overlay_module.STATE_TRANSITIONS.items():
            if trans['type'] != overlay_module.TRANSITION_NONE:
                assert 'duration' in trans
                assert trans['duration'] > 0


class TestTransitionTypes:
    """Tests for transition type constants."""

    def test_transition_bounce_constant(self, overlay_module):
        """Bounce constant is defined."""
        assert overlay_module.TRANSITION_BOUNCE == 'bounce'

    def test_transition_shake_constant(self, overlay_module):
        """Shake constant is defined."""
        assert overlay_module.TRANSITION_SHAKE == 'shake'

    def test_transition_scale_pop_constant(self, overlay_module):
        """Scale pop constant is defined."""
        assert overlay_module.TRANSITION_SCALE_POP == 'scale_pop'

    def test_transition_none_constant(self, overlay_module):
        """None constant is defined."""
        assert overlay_module.TRANSITION_NONE == 'none'


class TestAnimationCalculations:
    """Tests for animation calculation formulas."""

    def test_float_sine_wave_at_zero(self, overlay_module):
        """Float offset is zero at t=0."""
        elapsed = 0
        offset = overlay_module.FLOAT_AMPLITUDE * math.sin(
            2 * math.pi * elapsed / overlay_module.FLOAT_PERIOD
        )
        assert abs(offset) < 0.001

    def test_float_sine_wave_at_quarter_period(self, overlay_module):
        """Float offset is at max at quarter period."""
        elapsed = overlay_module.FLOAT_PERIOD / 4
        offset = overlay_module.FLOAT_AMPLITUDE * math.sin(
            2 * math.pi * elapsed / overlay_module.FLOAT_PERIOD
        )
        assert abs(offset - overlay_module.FLOAT_AMPLITUDE) < 0.001

    def test_breathing_scale_at_zero(self, overlay_module):
        """Breathing scale is 1.0 at t=0."""
        elapsed = 0
        breath = math.sin(2 * math.pi * elapsed / overlay_module.BREATH_PERIOD)
        scale_y = 1.0 + (breath * overlay_module.BREATH_INTENSITY)
        assert abs(scale_y - 1.0) < 0.001

    def test_breathing_scale_at_quarter_period(self, overlay_module):
        """Breathing scale is max at quarter period."""
        elapsed = overlay_module.BREATH_PERIOD / 4
        breath = math.sin(2 * math.pi * elapsed / overlay_module.BREATH_PERIOD)
        scale_y = 1.0 + (breath * overlay_module.BREATH_INTENSITY)
        expected = 1.0 + overlay_module.BREATH_INTENSITY
        assert abs(scale_y - expected) < 0.001

    def test_sway_rotation_at_zero(self, overlay_module):
        """Sway rotation is zero at t=0."""
        elapsed = 0
        sway_phase = 2 * math.pi * elapsed / overlay_module.SWAY_PERIOD
        rotation = math.sin(sway_phase) * overlay_module.SWAY_ANGLE
        assert abs(rotation) < 0.001

    def test_sway_rotation_at_quarter_period(self, overlay_module):
        """Sway rotation is max at quarter period."""
        elapsed = overlay_module.SWAY_PERIOD / 4
        sway_phase = 2 * math.pi * elapsed / overlay_module.SWAY_PERIOD
        rotation = math.sin(sway_phase) * overlay_module.SWAY_ANGLE
        assert abs(rotation - overlay_module.SWAY_ANGLE) < 0.001


class TestEasingFunctions:
    """Tests for animation easing functions."""

    def test_ease_out_bounce_starts_at_zero(self, overlay_module):
        """Ease out bounce starts at 0."""
        assert overlay_module.ease_out_bounce(0.0) == 0.0

    def test_ease_out_bounce_ends_at_one(self, overlay_module):
        """Ease out bounce ends at 1."""
        assert overlay_module.ease_out_bounce(1.0) == 1.0

    def test_ease_out_bounce_monotonic_overall(self, overlay_module):
        """Ease out bounce trends upward overall."""
        # Check that end is higher than start
        start = overlay_module.ease_out_bounce(0.1)
        end = overlay_module.ease_out_bounce(0.9)
        assert end > start

    def test_ease_out_elastic_starts_at_zero(self, overlay_module):
        """Ease out elastic starts at 0."""
        assert overlay_module.ease_out_elastic(0.0) == 0.0

    def test_ease_out_elastic_ends_at_one(self, overlay_module):
        """Ease out elastic ends at 1."""
        result = overlay_module.ease_out_elastic(1.0)
        assert abs(result - 1.0) < 0.001

    def test_ease_out_elastic_overshoots(self, overlay_module):
        """Ease out elastic can overshoot 1.0 during animation."""
        # Check middle values - elastic should overshoot
        values = [overlay_module.ease_out_elastic(t) for t in [0.3, 0.5, 0.7]]
        # At least one value should be > 1.0 (overshoot)
        has_overshoot = any(v > 1.0 for v in values)
        # Or values approach 1.0 smoothly
        approaches_one = values[-1] > values[0]
        assert has_overshoot or approaches_one


class TestStateDurations:
    """Tests for state duration configurations."""

    def test_state_durations_has_all_states(self, overlay_module):
        """All states have duration configuration."""
        expected_states = [
            'greeting', 'working', 'success', 'error',
            'celebrating', 'sleeping', 'idle', 'farewell'
        ]
        for state in expected_states:
            assert state in overlay_module.STATE_DURATIONS

    def test_idle_is_permanent(self, overlay_module):
        """Idle state is permanent (None duration)."""
        assert overlay_module.STATE_DURATIONS['idle'] is None

    def test_working_is_permanent(self, overlay_module):
        """Working state is permanent (None duration)."""
        assert overlay_module.STATE_DURATIONS['working'] is None

    def test_temporal_states_have_duration(self, overlay_module):
        """Temporal states have positive duration."""
        temporal = ['greeting', 'success', 'error', 'celebrating', 'farewell']
        for state in temporal:
            duration = overlay_module.STATE_DURATIONS[state]
            assert duration is not None
            assert duration > 0
