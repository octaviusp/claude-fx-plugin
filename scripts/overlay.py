#!/usr/bin/env python3
"""
Claude FX Overlay - True transparent overlay using PyObjC (macOS).
Displays PNG/GIF mascot with real transparency - no background window.
"""

import atexit
import io
import json
import math
import os
import random
import signal
import socket
import sys
import threading
import time
from pathlib import Path

from PIL import Image, ImageFilter

try:
    import objc
    from AppKit import (
        NSWorkspace, NSFont, NSFontAttributeName,
        NSForegroundColorAttributeName, NSEvent,
    )
    from Cocoa import (
        NSApplication, NSWindow, NSView, NSImage, NSColor, NSTimer,
        NSMakeRect, NSBackingStoreBuffered, NSFloatingWindowLevel,
        NSCompositingOperationSourceOver, NSScreen,
        NSAnimationContext, NSBezierPath,
        NSMutableParagraphStyle, NSParagraphStyleAttributeName,
        NSMakePoint, NSAffineTransform,
    )
    from Foundation import (
        NSData, NSObject, NSAttributedString, NSMutableDictionary,
    )
    # NSApplicationActivationPolicy constant (not always exported by PyObjC)
    NSApplicationActivationPolicyProhibited = 2
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGWindowListExcludeDesktopElements,
        kCGNullWindowID,
        CGColorCreateGenericRGB,
    )
except ImportError:
    print("Required: pip3 install pyobjc-framework-Cocoa")
    sys.exit(1)

# Paths
HOME = Path.home()
FX_DIR = HOME / '.claude-fx'

# Session ID from environment (set by hook-handler)
SESSION_ID = os.environ.get('CLAUDE_FX_SESSION')


def get_socket_path() -> Path:
    """Get socket file path for this session."""
    if not SESSION_ID:
        raise RuntimeError("CLAUDE_FX_SESSION required for session isolation")
    return FX_DIR / f'sock-{SESSION_ID}.sock'


PLUGIN_ROOT = Path(os.environ.get(
    'CLAUDE_FX_ROOT',
    Path(__file__).parent.parent
))

# Default settings
DEFAULT_MAX_HEIGHT = 350
DEFAULT_OFFSET_X = 20
DEFAULT_OFFSET_Y = 40
DEFAULT_HEIGHT_RATIO = 0.5  # 50% of terminal height when responsive

# State durations (None = permanent, number = seconds before returning to idle)
# 'farewell' is special - triggers shutdown after duration
STATE_DURATIONS = {
    'idle': None,
    'greeting': 3.0,
    'working': None,
    'success': 3.0,
    'error': 3.0,
    'celebrating': 3.0,
    'sleeping': None,
    'farewell': 3.0,  # Shows greeting then exits
}

# Animation constants - floating effect
FLOAT_AMPLITUDE = 3.0   # pixels of vertical movement
FLOAT_PERIOD = 2.5      # seconds for full oscillation cycle

# Animation constants - aura glow effect
AURA_COLOR = (0.4, 0.55, 1.0, 1.0)  # Soft blue (R, G, B, A)
AURA_MIN_RADIUS = 8.0
AURA_MAX_RADIUS = 14.0
AURA_PERIOD = 1.8       # seconds for pulse cycle
AURA_OPACITY = 0.5

# Animation constants - breathing effect (scale pulse)
BREATH_INTENSITY = 0.008    # 0.8% scale change
BREATH_PERIOD = 3.5         # seconds for full breath cycle

# Animation constants - sway effect (gentle rotation + drift)
SWAY_ANGLE = 1.5            # degrees max rotation
SWAY_PERIOD = 4.0           # seconds for full sway cycle
SWAY_X = 2.0                # pixels horizontal drift

# Animation constants - cursor influence
CURSOR_TILT_MAX = 3.0       # degrees max tilt toward cursor
CURSOR_SHIFT_MAX = 5.0      # pixels max shift toward cursor
CURSOR_FALLOFF = 300.0      # distance for effect falloff

# State transition animation types
TRANSITION_BOUNCE = 'bounce'
TRANSITION_SHAKE = 'shake'
TRANSITION_SCALE_POP = 'scale_pop'
TRANSITION_NONE = 'none'

# State transition configurations
STATE_TRANSITIONS = {
    'greeting': {
        'type': TRANSITION_SCALE_POP, 'scale': 1.08, 'duration': 0.25
    },
    'working': {
        'type': TRANSITION_SCALE_POP, 'scale': 1.05, 'duration': 0.2
    },
    'success': {
        'type': TRANSITION_BOUNCE, 'height': 15, 'duration': 0.4
    },
    'error': {
        'type': TRANSITION_SHAKE, 'intensity': 8, 'cycles': 3, 'duration': 0.3
    },
    'celebrating': {
        'type': TRANSITION_BOUNCE, 'height': 20, 'duration': 0.5
    },
    'sleeping': {'type': TRANSITION_NONE},
    'idle': {'type': TRANSITION_NONE},
    'farewell': {
        'type': TRANSITION_SCALE_POP, 'scale': 1.05, 'duration': 0.2
    },
}

# Emotion overlay mappings (state -> list of overlays to show)
EMOTION_OVERLAYS = {
    'error': ['sweat_drop'],
    'success': ['sparkle'],
    'celebrating': ['sparkle', 'star'],
    'sleeping': ['zzz'],
    'working': ['focus_lines'],
}

# Speech bubble message pools
DEFAULT_MESSAGES = {
    'greeting': [
        "Ready when you are.", "Let's build something.", "Good to see you."
    ],
    'working': ["On it...", "Processing...", "Give me a sec."],
    'success': ["Done.", "Got it.", "Clean."],
    'error': ["Hmm, let me check.", "Something's off.", "Hold on..."],
    'celebrating': ["Nice work!", "Nailed it!", "Victory!"],
    'sleeping': ["Zzz...", "*yawn*", "..."],
    'farewell': ["See you!", "Bye for now.", "Until next time."],
    'idle': ["Need anything?", "I'm here.", "..."],
}


def load_settings() -> dict:
    """Load settings from settings-fx.json."""
    settings_file = PLUGIN_ROOT / 'settings-fx.json'
    if settings_file.exists():
        try:
            return json.loads(settings_file.read_text())
        except Exception:
            pass
    return {}


def apply_bottom_gradient(pil_image: Image.Image, percentage: float):
    """Apply alpha gradient to bottom portion of image.

    Args:
        pil_image: PIL Image (will be converted to RGBA if needed)
        percentage: Fraction of image height to fade (0.0-1.0)

    Returns:
        Modified PIL Image with gradient alpha at bottom
    """
    if percentage <= 0:
        return pil_image

    if pil_image.mode != 'RGBA':
        pil_image = pil_image.convert('RGBA')

    width, height = pil_image.size
    gradient_height = int(height * min(percentage, 1.0))

    if gradient_height <= 0:
        return pil_image

    pixels = pil_image.load()
    start_y = height - gradient_height

    for y in range(start_y, height):
        progress = (y - start_y) / gradient_height
        alpha_mult = 1.0 - progress
        for x in range(width):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, int(a * alpha_mult))

    return pil_image


def pil_to_nsimage(pil_image: Image.Image) -> NSImage:
    """Convert PIL Image to NSImage."""
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG')
    png_data = buffer.getvalue()
    data = NSData.dataWithBytes_length_(png_data, len(png_data))
    return NSImage.alloc().initWithData_(data)


def load_messages(plugin_root: Path) -> dict:
    """Load speech bubble messages from messages.json or use defaults."""
    messages_file = plugin_root / 'messages.json'
    if messages_file.exists():
        try:
            return json.loads(messages_file.read_text())
        except Exception:
            pass
    return DEFAULT_MESSAGES


def hex_to_nscolor(hex_color: str) -> NSColor:
    """Convert hex color string to NSColor."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return NSColor.colorWithRed_green_blue_alpha_(r, g, b, 1.0)
    return NSColor.whiteColor()


def generate_shadow_image(pil_image: Image.Image, blur: int = 20,
                          opacity: float = 0.3) -> Image.Image:
    """Generate a shadow from a PIL image."""
    if pil_image.mode != 'RGBA':
        pil_image = pil_image.convert('RGBA')

    # Extract alpha channel and create shadow
    alpha = pil_image.split()[3]
    shadow = Image.new('RGBA', pil_image.size, (0, 0, 0, 0))

    # Create shadow from alpha
    shadow_alpha = alpha.point(lambda x: int(x * opacity))
    shadow_blurred = shadow_alpha.filter(ImageFilter.GaussianBlur(blur))

    # Composite shadow
    shadow.putalpha(shadow_blurred)
    return shadow


def ease_out_bounce(t: float) -> float:
    """Easing function for bounce effect."""
    if t < 1 / 2.75:
        return 7.5625 * t * t
    elif t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    elif t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    else:
        t -= 2.625 / 2.75
        return 7.5625 * t * t + 0.984375


def ease_out_elastic(t: float) -> float:
    """Easing function for elastic/pop effect."""
    if t == 0 or t == 1:
        return t
    p = 0.3
    s = p / 4
    return pow(2, -10 * t) * math.sin((t - s) * (2 * math.pi) / p) + 1


def get_cursor_position() -> tuple:
    """Get current mouse cursor position."""
    try:
        loc = NSEvent.mouseLocation()
        return (loc.x, loc.y)
    except Exception:
        return (0, 0)


def get_terminal_position():
    """Get active terminal window position."""
    try:
        terminals = ['Terminal', 'iTerm', 'Alacritty', 'kitty', 'Warp']
        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        )
        for w in windows:
            owner = w.get('kCGWindowOwnerName', '')
            if any(t in owner for t in terminals):
                b = w.get('kCGWindowBounds', {})
                return {
                    'x': int(b.get('X', 100)),
                    'y': int(b.get('Y', 100)),
                    'w': int(b.get('Width', 800)),
                    'h': int(b.get('Height', 600))
                }
    except Exception:
        pass
    return {'x': 100, 'y': 100, 'w': 800, 'h': 600}


def is_our_window_frontmost(terminal_pid: int, window_id: int) -> bool:
    """
    Check if our terminal window is frontmost.

    Behavior:
    - If terminal app NOT frontmost: return False (hide)
    - If window_id known: check if frontmost among terminal's windows
    - If window_id unknown: return True if terminal app is frontmost

    This matches the original behavior that worked well.
    """
    if not terminal_pid:
        return False  # No PID = can't verify = hide

    try:
        # Check app first (fast path)
        frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
        if frontmost.processIdentifier() != terminal_pid:
            return False  # Different app is active

        # Terminal app is frontmost - if no window_id, show (permissive)
        if not window_id:
            return True

        # window_id known: check if OUR window is frontmost among terminals
        opts = (kCGWindowListOptionOnScreenOnly |
                kCGWindowListExcludeDesktopElements)
        windows = CGWindowListCopyWindowInfo(opts, kCGNullWindowID)
        if not windows:
            return True  # Can't verify = show (permissive)

        # Find first layer-0 window belonging to our terminal
        for w in windows:
            if w.get('kCGWindowLayer', 0) != 0:
                continue  # Skip menus, popups, etc.
            if w.get('kCGWindowOwnerPID') != terminal_pid:
                continue  # Skip other apps' windows

            # First terminal window in list is frontmost terminal window
            return w.get('kCGWindowNumber') == window_id

        return True  # No matching windows found = show (permissive)
    except Exception:
        return True  # Error = show (permissive when terminal active)


def get_terminal_window_position(window_id: int) -> dict | None:
    """Get position of specific terminal window by ID."""
    if not window_id:
        return None
    try:
        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        )
        for w in windows:
            if w.get('kCGWindowNumber') == window_id:
                b = w.get('kCGWindowBounds', {})
                return {
                    'x': int(b.get('X', 0)),
                    'y': int(b.get('Y', 0)),
                    'w': int(b.get('Width', 800)),
                    'h': int(b.get('Height', 600))
                }
    except Exception:
        pass
    return None


class ImageView(NSView):
    """Custom view that draws an image with transparency and transforms."""

    def initWithFrame_(self, frame):
        self = objc.super(ImageView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.image = None
        self.rotation = 0.0  # degrees
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        return self

    def setImage_(self, image):
        self.image = image
        self.setNeedsDisplay_(True)

    def setTransform_(self, rotation, scale_x, scale_y, offset_x, offset_y):
        """Set transform parameters for breathing/sway effects."""
        self.rotation = rotation
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        if self.image:
            bounds = self.bounds()
            center_x = bounds.size.width / 2
            center_y = bounds.size.height / 2

            # Apply transforms
            transform = NSAffineTransform.transform()
            transform.translateXBy_yBy_(
                center_x + self.offset_x,
                center_y + self.offset_y
            )
            transform.rotateByDegrees_(self.rotation)
            transform.scaleXBy_yBy_(self.scale_x, self.scale_y)
            transform.translateXBy_yBy_(-center_x, -center_y)
            transform.concat()

            # Draw image
            self.image.drawInRect_fromRect_operation_fraction_(
                bounds,
                NSMakeRect(0, 0, 0, 0),
                NSCompositingOperationSourceOver,
                1.0
            )


class SpeechBubbleView(NSView):
    """Custom view that renders a speech bubble with configurable styling."""

    def initWithFrame_(self, frame):
        self = objc.super(SpeechBubbleView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.text = ""
        self.bg_color = NSColor.colorWithRed_green_blue_alpha_(
            0.1, 0.1, 0.18, 0.95
        )
        self.border_color = NSColor.colorWithRed_green_blue_alpha_(
            0.29, 0.62, 1.0, 1.0
        )
        self.font_color = NSColor.whiteColor()
        self.font_name = "SF Mono"
        self.font_size = 13.0
        self.border_width = 2.0
        self.border_radius = 8.0
        self.padding = 10.0
        self.tail_size = 8.0
        return self

    def configure_(self, config: dict):
        """Configure bubble appearance from settings dict."""
        if 'backgroundColor' in config:
            self.bg_color = hex_to_nscolor(config['backgroundColor'])
            # Add slight transparency
            self.bg_color = self.bg_color.colorWithAlphaComponent_(0.95)
        if 'borderColor' in config:
            self.border_color = hex_to_nscolor(config['borderColor'])
        if 'fontColor' in config:
            self.font_color = hex_to_nscolor(config['fontColor'])
        if 'fontFamily' in config:
            self.font_name = config['fontFamily']
        if 'fontSize' in config:
            self.font_size = float(config['fontSize'])
        if 'borderWidth' in config:
            self.border_width = float(config['borderWidth'])
        if 'borderRadius' in config:
            self.border_radius = float(config['borderRadius'])
        if 'padding' in config:
            self.padding = float(config['padding'])
        self.setNeedsDisplay_(True)

    def setText_(self, text: str):
        """Set the bubble text."""
        self.text = text
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        if not self.text:
            return

        bounds = self.bounds()
        padding = self.padding
        tail = self.tail_size
        radius = self.border_radius

        # Bubble rect (excluding tail)
        bubble_rect = NSMakeRect(
            padding / 2,
            tail + padding / 2,
            bounds.size.width - padding,
            bounds.size.height - tail - padding
        )

        # Draw bubble background with rounded corners
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            bubble_rect, radius, radius
        )

        # Draw tail (pointing down to character)
        tail_x = bounds.size.width / 2
        path.moveToPoint_(NSMakePoint(tail_x - tail, tail + padding / 2))
        path.lineToPoint_(NSMakePoint(tail_x, padding / 2))
        path.lineToPoint_(NSMakePoint(tail_x + tail, tail + padding / 2))
        path.closePath()

        # Fill background
        self.bg_color.setFill()
        path.fill()

        # Draw border
        self.border_color.setStroke()
        path.setLineWidth_(self.border_width)
        path.stroke()

        # Draw text
        font = NSFont.fontWithName_size_(self.font_name, self.font_size)
        if not font:
            font = NSFont.systemFontOfSize_(self.font_size)

        attrs = NSMutableDictionary.dictionary()
        attrs[NSFontAttributeName] = font
        attrs[NSForegroundColorAttributeName] = self.font_color

        # Center text
        para = NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(1)  # NSCenterTextAlignment
        attrs[NSParagraphStyleAttributeName] = para

        attr_str = NSAttributedString.alloc().initWithString_attributes_(
            self.text, attrs
        )
        text_size = attr_str.size()
        text_x = (bounds.size.width - text_size.width) / 2
        text_y = tail + padding + (
            bubble_rect.size.height - text_size.height
        ) / 2
        attr_str.drawAtPoint_(NSMakePoint(text_x, text_y))


class EmotionOverlayView(NSView):
    """View that renders emotion indicators (sweat drop, zzz, sparkles)."""

    def initWithFrame_(self, frame):
        self = objc.super(EmotionOverlayView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.emotions = []  # List of emotion types to display
        self.animation_phase = 0.0
        return self

    def setEmotions_(self, emotions: list):
        """Set which emotions to display."""
        self.emotions = emotions or []
        self.setNeedsDisplay_(True)

    def setAnimationPhase_(self, phase: float):
        """Update animation phase for animated emotions."""
        self.animation_phase = phase
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        if not self.emotions:
            return

        bounds = self.bounds()

        for emotion in self.emotions:
            if emotion == 'sweat_drop':
                self._draw_sweat_drop(bounds)
            elif emotion == 'zzz':
                self._draw_zzz(bounds)
            elif emotion == 'sparkle':
                self._draw_sparkle(bounds)
            elif emotion == 'star':
                self._draw_star(bounds)
            elif emotion == 'focus_lines':
                self._draw_focus_lines(bounds)

    def _draw_sweat_drop(self, bounds):
        """Draw a sweat drop in top-right area."""
        drop_x = bounds.size.width * 0.85
        drop_y = bounds.size.height * 0.75
        size = 12

        # Animate drop falling
        offset = (self.animation_phase % 1.0) * 20

        path = NSBezierPath.bezierPath()
        # Teardrop shape
        path.moveToPoint_(NSMakePoint(drop_x, drop_y - offset))
        path.curveToPoint_controlPoint1_controlPoint2_(
            NSMakePoint(drop_x, drop_y - size - offset),
            NSMakePoint(drop_x + size / 2, drop_y - size / 3 - offset),
            NSMakePoint(drop_x + size / 3, drop_y - size - offset)
        )
        path.curveToPoint_controlPoint1_controlPoint2_(
            NSMakePoint(drop_x, drop_y - offset),
            NSMakePoint(drop_x - size / 3, drop_y - size - offset),
            NSMakePoint(drop_x - size / 2, drop_y - size / 3 - offset)
        )

        # Light blue fill
        NSColor.colorWithRed_green_blue_alpha_(
            0.6, 0.8, 1.0, 0.8
        ).setFill()
        path.fill()

    def _draw_zzz(self, bounds):
        """Draw floating Zzz in top-right area."""
        base_x = bounds.size.width * 0.8
        base_y = bounds.size.height * 0.7

        font_sizes = [14, 11, 8]
        offsets = [(0, 0), (15, 20), (25, 35)]

        # Animate floating up
        float_offset = math.sin(self.animation_phase * 2) * 5

        for i, (size, (ox, oy)) in enumerate(zip(font_sizes, offsets)):
            font = NSFont.boldSystemFontOfSize_(size)
            attrs = {
                NSFontAttributeName: font,
                NSForegroundColorAttributeName: NSColor.colorWithRed_green_blue_alpha_(  # noqa: E501
                    0.7, 0.7, 0.9, 0.8 - i * 0.2
                )
            }
            z_str = NSAttributedString.alloc().initWithString_attributes_(
                "Z", attrs
            )
            z_str.drawAtPoint_(NSMakePoint(
                base_x + ox,
                base_y + oy + float_offset + i * 3
            ))

    def _draw_sparkle(self, bounds):
        """Draw sparkle effects around the character."""
        sparkle_positions = [
            (0.15, 0.8), (0.85, 0.85), (0.9, 0.6), (0.1, 0.5)
        ]

        for i, (px, py) in enumerate(sparkle_positions):
            x = bounds.size.width * px
            y = bounds.size.height * py

            # Animate sparkle size
            phase = (self.animation_phase + i * 0.25) % 1.0
            size = 4 + math.sin(phase * math.pi * 2) * 3
            alpha = 0.5 + math.sin(phase * math.pi * 2) * 0.4

            self._draw_star_shape(x, y, size, alpha)

    def _draw_star(self, bounds):
        """Draw a star in top area."""
        x = bounds.size.width * 0.5
        y = bounds.size.height * 0.9

        # Animate rotation
        rotation = self.animation_phase * 360

        transform = NSAffineTransform.transform()
        transform.translateXBy_yBy_(x, y)
        transform.rotateByDegrees_(rotation)
        transform.concat()

        self._draw_star_shape(0, 0, 10, 0.9)

    def _draw_star_shape(self, x, y, size, alpha):
        """Draw a 4-pointed star shape."""
        color = NSColor.colorWithRed_green_blue_alpha_(
            1.0, 0.95, 0.4, alpha
        )
        color.setFill()

        path = NSBezierPath.bezierPath()
        # 4-pointed star
        path.moveToPoint_(NSMakePoint(x, y + size))
        path.lineToPoint_(NSMakePoint(x + size * 0.3, y + size * 0.3))
        path.lineToPoint_(NSMakePoint(x + size, y))
        path.lineToPoint_(NSMakePoint(x + size * 0.3, y - size * 0.3))
        path.lineToPoint_(NSMakePoint(x, y - size))
        path.lineToPoint_(NSMakePoint(x - size * 0.3, y - size * 0.3))
        path.lineToPoint_(NSMakePoint(x - size, y))
        path.lineToPoint_(NSMakePoint(x - size * 0.3, y + size * 0.3))
        path.closePath()
        path.fill()

    def _draw_focus_lines(self, bounds):
        """Draw focus/concentration lines around character."""
        center_x = bounds.size.width / 2
        center_y = bounds.size.height * 0.6

        NSColor.colorWithRed_green_blue_alpha_(
            0.4, 0.6, 1.0, 0.3
        ).setStroke()

        for i in range(8):
            angle = (i * 45 + self.animation_phase * 30) * math.pi / 180
            inner_r = 60 + math.sin(self.animation_phase * 3 + i) * 10
            outer_r = inner_r + 20

            path = NSBezierPath.bezierPath()
            path.setLineWidth_(2)
            path.moveToPoint_(NSMakePoint(
                center_x + math.cos(angle) * inner_r,
                center_y + math.sin(angle) * inner_r
            ))
            path.lineToPoint_(NSMakePoint(
                center_x + math.cos(angle) * outer_r,
                center_y + math.sin(angle) * outer_r
            ))
            path.stroke()


class Overlay(NSObject):
    """Transparent overlay window with animated character."""

    def init(self):
        self = objc.super(Overlay, self).init()
        if self is None:
            return None
        self._setup()
        return self

    def _setup(self):
        self.app = NSApplication.sharedApplication()
        # Hide from dock - run as background process
        self.app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

        # Load settings
        self.settings = load_settings()
        overlay_cfg = self.settings.get('overlay', {})
        self.base_max_height = overlay_cfg.get('maxHeight', DEFAULT_MAX_HEIGHT)
        self.max_height = self.base_max_height  # Current active max height
        self.offset_x = overlay_cfg.get('offsetX', DEFAULT_OFFSET_X)
        self.offset_y = overlay_cfg.get('offsetY', DEFAULT_OFFSET_Y)
        self.responsive = overlay_cfg.get('responsive', True)
        self.height_ratio = overlay_cfg.get(
            'heightRatio', DEFAULT_HEIGHT_RATIO
        )

        # Bottom gradient settings
        gradient_cfg = overlay_cfg.get('bottomGradient', {})
        self.gradient_enabled = gradient_cfg.get('enabled', True)
        self.gradient_percentage = gradient_cfg.get('percentage', 0.2)

        # Immersion settings
        immersion_cfg = self.settings.get('immersion', {})
        self.breathing_enabled = immersion_cfg.get('breathing', True)
        self.sway_enabled = immersion_cfg.get('sway', True)
        self.cursor_influence_enabled = immersion_cfg.get(
            'cursorInfluence', True
        )
        self.cursor_influence_strength = immersion_cfg.get(
            'cursorInfluenceStrength', 0.5
        )
        self.transitions_enabled = immersion_cfg.get('transitions', True)

        # Speech bubble settings
        self.speech_cfg = self.settings.get('speechBubble', {})
        self.speech_enabled = self.speech_cfg.get('enabled', True)
        self.speech_duration = self.speech_cfg.get('displayDuration', 3.0)

        # Emotion overlay settings
        self.emotions_enabled = self.settings.get('emotionOverlays', {}).get(
            'enabled', True
        )

        # Load manifest
        theme_name = self.settings.get('theme', 'default')
        self.theme_path = PLUGIN_ROOT / 'themes' / theme_name
        self.manifest = self.load_manifest()

        # Character folder override (session-specific, not persisted)
        self.character_folder_override = None  # e.g., "characters2"

        # Get initial terminal position for responsive sizing
        initial_pos = get_terminal_position()
        if self.responsive and initial_pos:
            self.max_height = self.calculate_responsive_height(
                initial_pos['h']
            )
            self.last_terminal_pos = initial_pos

        # Calculate size from first image
        self.width = 200
        self.height = self.max_height
        self.calculate_size('idle')

        # Calculate position
        x, y = self.calculate_position(overlay_cfg)

        # Create borderless transparent window
        rect = NSMakeRect(x, y, self.width, self.height)
        style = 0  # NSBorderlessWindowMask
        self.window = NSWindow.alloc()
        self.window = self.window.initWithContentRect_styleMask_backing_defer_(
            rect, style, NSBackingStoreBuffered, False
        )

        # Make transparent
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setHasShadow_(False)
        self.window.setIgnoresMouseEvents_(True)  # Click-through

        # Create dual image views for crossfade
        content_rect = NSMakeRect(0, 0, self.width, self.height)
        self.content_view = NSView.alloc().initWithFrame_(content_rect)
        self.image_view_back = ImageView.alloc().initWithFrame_(content_rect)
        self.image_view_front = ImageView.alloc().initWithFrame_(content_rect)
        self.image_view_back.setAlphaValue_(0.0)
        self.content_view.addSubview_(self.image_view_back)
        self.content_view.addSubview_(self.image_view_front)

        # Create emotion overlay view (renders on top of character)
        self.emotion_view = EmotionOverlayView.alloc().initWithFrame_(
            content_rect
        )
        self.emotion_view.setAlphaValue_(0.0)
        self.content_view.addSubview_(self.emotion_view)

        # Create speech bubble view (above character)
        bubble_height = 60
        bubble_width = 200
        bubble_rect = NSMakeRect(
            (self.width - bubble_width) / 2,
            self.height - bubble_height - 10,
            bubble_width,
            bubble_height
        )
        self.speech_bubble = SpeechBubbleView.alloc().initWithFrame_(
            bubble_rect
        )
        self.speech_bubble.configure_(self.speech_cfg)
        self.speech_bubble.setAlphaValue_(0.0)
        self.content_view.addSubview_(self.speech_bubble)

        # Load speech messages
        self.messages = load_messages(PLUGIN_ROOT)

        self.window.setContentView_(self.content_view)

        # Setup aura glow effect (layer-backed for shadow)
        self.content_view.setWantsLayer_(True)
        layer = self.content_view.layer()
        layer.setShadowColor_(CGColorCreateGenericRGB(*AURA_COLOR))
        layer.setShadowOpacity_(AURA_OPACITY)
        layer.setShadowRadius_(AURA_MIN_RADIUS)
        layer.setShadowOffset_((0, 0))  # Centered glow

        # State tracking
        self.current_state = 'idle'
        self.last_socket_state = None  # Track last state received via socket
        self.pending_idle_timer = None
        self.load_state_image('idle', crossfade=False)

        # Visibility tracking - received via socket on first message
        self.terminal_pid = None
        self.terminal_window_id = None
        self.is_visible = True
        self.last_terminal_pos = None
        self.show_only_when_active = overlay_cfg.get(
            'showOnlyWhenTerminalActive', True
        )
        self.fade_animation = overlay_cfg.get('fadeAnimation', True)
        # Grace period: don't hide overlay for first 1.5s after startup
        self.startup_time = time.time()

        # Animation state
        self.animation_start = time.time()
        self.base_y = y  # Base Y position (before float offset)
        self.base_x = x  # Base X position

        # Transition animation state
        self.transition_active = False
        self.transition_type = None
        self.transition_start = 0.0
        self.transition_duration = 0.0
        self.transition_params = {}

        # Speech bubble timer
        self.speech_hide_timer = None

        # Don't show window yet - defer until run loop starts
        self.window.setAlphaValue_(0.0)

        # Socket server for IPC (replaces file polling)
        self.socket_path = get_socket_path()
        self.socket_server = None
        self.socket_thread = None
        self.state_lock = threading.Lock()
        self.setup_socket_server()

        # Animation timer (60fps for smooth movement)
        m = 'scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_'
        self.timer = getattr(NSTimer, m)(
            0.016, self, 'animationTick:', None, True
        )

        # Parent process monitor (check every 2s if terminal still alive)
        self.parent_check_timer = getattr(NSTimer, m)(
            2.0, self, 'checkParentAlive:', None, True
        )

        # Defer window show to after run loop starts (fixes startup visibility)
        getattr(NSTimer, m)(0.1, self, 'showWindowDeferred:', None, False)

        # Subscribe to app activation notifications (event-driven visibility)
        self.pending_show_timer = None
        nc = NSWorkspace.sharedWorkspace().notificationCenter()
        nc.addObserver_selector_name_object_(
            self, 'appDidActivate:',
            'NSWorkspaceDidActivateApplicationNotification', None
        )
        nc.addObserver_selector_name_object_(
            self, 'appDidDeactivate:',
            'NSWorkspaceDidDeactivateApplicationNotification', None
        )
        nc.addObserver_selector_name_object_(
            self, 'spaceDidChange:',
            'NSWorkspaceActiveSpaceDidChangeNotification', None
        )

        # Fallback validation timer (500ms) - catches minimize, Space changes
        self.validation_timer = None
        m = 'scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_'
        self.validation_timer = getattr(NSTimer, m)(
            0.5, self, 'validateVisibility:', None, True
        )

        # Setup signal handlers for clean shutdown
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Register cleanup on signals (SIGTERM, SIGINT, SIGHUP)."""
        def handle_signal(signum, frame):
            self._emergency_cleanup()
            os._exit(0)

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGHUP, handle_signal)
        atexit.register(self._emergency_cleanup)

    def _emergency_cleanup(self):
        """Fast cleanup without animations (for signal handlers)."""
        try:
            if self.socket_server:
                self.socket_server.close()
                self.socket_server = None
            if self.socket_path and self.socket_path.exists():
                self.socket_path.unlink(missing_ok=True)
            if hasattr(self, 'pid_path') and self.pid_path.exists():
                self.pid_path.unlink(missing_ok=True)
        except Exception:
            pass

    def load_manifest(self) -> dict:
        """Load theme manifest."""
        manifest_file = self.theme_path / 'manifest.json'
        if manifest_file.exists():
            try:
                return json.loads(manifest_file.read_text())
            except Exception:
                pass
        return {}

    def setup_socket_server(self):
        """Create Unix domain socket server for IPC."""
        FX_DIR.mkdir(parents=True, exist_ok=True)

        # Clean up stale sockets from dead processes
        self._cleanup_stale_sockets()

        # Clean up our own stale socket file
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Create PID file for this session
        self.pid_path = FX_DIR / f'pid-{SESSION_ID}.txt'
        self.pid_path.write_text(str(os.getpid()))

        # Create socket
        self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket_server.bind(str(self.socket_path))
        self.socket_server.listen(5)
        self.socket_server.settimeout(0.1)  # Non-blocking with timeout

        # Start listener thread
        self.socket_thread = threading.Thread(
            target=self.socket_listener_loop,
            daemon=True
        )
        self.socket_thread.start()

    def _cleanup_stale_sockets(self):
        """Remove sockets from dead processes."""
        for sock_file in FX_DIR.glob('sock-*.sock'):
            try:
                session_id = sock_file.stem.replace('sock-', '')
                pid_file = FX_DIR / f'pid-{session_id}.txt'

                if pid_file.exists():
                    pid = int(pid_file.read_text().strip())
                    try:
                        os.kill(pid, 0)
                        continue  # Process alive - skip
                    except ProcessLookupError:
                        pass  # Process dead - clean up

                # Remove stale socket and PID file
                sock_file.unlink(missing_ok=True)
                if pid_file.exists():
                    pid_file.unlink(missing_ok=True)
            except Exception:
                pass

    def socket_listener_loop(self):
        """Accept connections and process commands (runs in thread)."""
        while self.socket_server:
            try:
                conn, _ = self.socket_server.accept()
                self.handle_client(conn)
            except socket.timeout:
                continue  # Check if server still running
            except OSError:
                break  # Socket closed
            except Exception:
                break

    def handle_client(self, conn):
        """Process single client connection."""
        try:
            # Receive message (max 4KB)
            data = conn.recv(4096).decode('utf-8').strip()
            if not data:
                return

            msg = json.loads(data)
            cmd = msg.get('cmd', 'SET_STATE')

            if cmd == 'PING':
                conn.sendall(b'PONG\n')
            elif cmd == 'SHUTDOWN':
                self.schedule_shutdown()
                conn.sendall(b'{"status": "ok"}\n')
            elif cmd == 'SET_STATE':
                self.handle_set_state(msg)
                conn.sendall(b'{"status": "ok"}\n')
            elif cmd == 'CHANGE_CHARACTER':
                folder = msg.get('folder')
                result = self.handle_change_character(folder)
                conn.sendall(f'{json.dumps(result)}\n'.encode('utf-8'))
            else:
                conn.sendall(b'{"status": "error", "message": "unknown"}\n')
        except Exception as e:
            try:
                err = json.dumps({"status": "error", "message": str(e)})
                conn.sendall(f'{err}\n'.encode('utf-8'))
            except Exception:
                pass
        finally:
            conn.close()

    def handle_set_state(self, msg):
        """Update state from socket message (thread-safe)."""
        # Only set terminal info ONCE on first message
        # Don't overwrite - each overlay owns its own terminal window
        if self.terminal_pid is None:
            new_pid = msg.get('terminal_pid')
            new_window_id = msg.get('terminal_window_id')
            if new_pid:
                self.terminal_pid = new_pid
            if new_window_id:
                self.terminal_window_id = new_window_id

        new_state = msg.get('state', 'idle')

        # Track last received state
        with self.state_lock:
            self.last_socket_state = new_state

        # Schedule UI update on main thread (NSTimer is main-thread only)
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            'updateStateFromSocket:', new_state, False
        )

    def handle_change_character(self, folder: str) -> dict:
        """Change character folder for this session (thread-safe)."""
        if not folder:
            return {"status": "error", "message": "folder name required"}

        # Validate folder exists
        folder_path = self.theme_path / folder
        if not folder_path.exists() or not folder_path.is_dir():
            return {"status": "error", "message": f"not found: {folder}"}

        # Check for at least one PNG
        pngs = list(folder_path.glob('*.png'))
        if not pngs:
            return {"status": "error", "message": f"no PNG files in: {folder}"}

        # Set override (thread-safe)
        with self.state_lock:
            self.character_folder_override = folder

        # Reload current state image on main thread
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            'reloadCurrentImage', None, False
        )

        return {"status": "ok", "folder": folder}

    def reloadCurrentImage(self):
        """Reload current state image (after character folder change)."""
        self.load_state_image(self.current_state, crossfade=True)

    def updateStateFromSocket_(self, new_state):
        """Update state on main thread (called from socket thread)."""
        if new_state != self.current_state:
            self.change_state(new_state)

    def schedule_shutdown(self):
        """Schedule shutdown from socket command."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            'shutdown', None, False
        )

    def checkParentAlive_(self, timer):
        """Check if parent terminal is still alive (every 2s)."""
        if not self.terminal_pid:
            return
        try:
            # Signal 0 checks if process exists without sending signal
            os.kill(self.terminal_pid, 0)
        except ProcessLookupError:
            # Parent died - shut down gracefully
            self.shutdown()
        except PermissionError:
            pass  # Process exists but we can't signal it - that's fine

    def calculate_position(self, overlay_cfg: dict) -> tuple:
        """Calculate window position based on settings."""
        screen_height = NSScreen.mainScreen().frame().size.height

        # Check for custom position
        custom_x = overlay_cfg.get('customX')
        custom_y = overlay_cfg.get('customY')

        if custom_x is not None and custom_y is not None:
            # Use custom position (convert Y from top to bottom)
            x = custom_x
            y = screen_height - custom_y - self.height
        else:
            # Auto-detect terminal position
            pos = get_terminal_position()
            x = pos['x'] + pos['w'] - self.width - self.offset_x
            y = screen_height - pos['y'] - self.offset_y - self.height

        return x, y

    def calculate_responsive_height(self, terminal_height: int) -> int:
        """Calculate max height based on terminal size."""
        if not self.responsive or not terminal_height:
            return self.base_max_height
        # Use ratio of terminal height, but cap at base_max_height
        responsive_h = int(terminal_height * self.height_ratio)
        return min(responsive_h, self.base_max_height)

    def calculate_size(self, state: str):
        """Calculate image size maintaining aspect ratio."""
        states = self.manifest.get('states', {})
        state_config = states.get(state, states.get('idle', {}))
        animation = state_config.get('animation', '')

        if animation:
            img_path = self.theme_path / animation
            if img_path.exists():
                img = NSImage.alloc().initWithContentsOfFile_(str(img_path))
                if img:
                    size = img.size()
                    if size.height > self.max_height:
                        ratio = self.max_height / size.height
                        self.width = int(size.width * ratio)
                        self.height = self.max_height
                    else:
                        self.width = int(size.width)
                        self.height = int(size.height)

    def load_state_image(self, state: str, crossfade: bool = True):
        """Load image for a given state with optional bottom gradient."""
        self.current_state = state

        states = self.manifest.get('states', {})
        # Use greeting image for farewell (wave goodbye)
        lookup_state = 'greeting' if state == 'farewell' else state
        state_config = states.get(lookup_state, states.get('idle', {}))
        animation = state_config.get('animation', '')

        if animation:
            # Apply character folder override if set
            original_animation = animation
            if self.character_folder_override:
                animation = animation.replace(
                    'characters/', f'{self.character_folder_override}/', 1
                )

            img_path = self.theme_path / animation

            # Fallback to original if override path doesn't exist
            if self.character_folder_override and not img_path.exists():
                img_path = self.theme_path / original_animation

            if img_path.exists():
                if self.gradient_enabled and self.gradient_percentage > 0:
                    # PIL path: load, resize, apply gradient, convert
                    pil_img = Image.open(str(img_path))
                    pil_img = pil_img.resize(
                        (self.width, self.height),
                        Image.Resampling.LANCZOS
                    )
                    pil_img = apply_bottom_gradient(
                        pil_img, self.gradient_percentage
                    )
                    img = pil_to_nsimage(pil_img)
                else:
                    # Direct NSImage path (no gradient)
                    img = NSImage.alloc().initWithContentsOfFile_(
                        str(img_path)
                    )
                    if img:
                        img.setSize_((self.width, self.height))

                if img:
                    if crossfade and self.fade_animation:
                        self.crossfade_to_image(img)
                    else:
                        self.image_view_front.setImage_(img)

    def crossfade_to_image(self, new_image):
        """Smoothly transition to new image."""
        # Load new image into back view
        self.image_view_back.setImage_(new_image)

        # Animate crossfade
        NSAnimationContext.beginGrouping()
        try:
            NSAnimationContext.currentContext().setDuration_(0.2)
            self.image_view_front.animator().setAlphaValue_(0.0)
            self.image_view_back.animator().setAlphaValue_(1.0)
        finally:
            NSAnimationContext.endGrouping()

        # Swap references after animation
        timer_method = 'scheduledTimerWithTimeInterval_' \
            'target_selector_userInfo_repeats_'
        getattr(NSTimer, timer_method)(
            0.25, self, 'swapImageViews:', None, False
        )

    def swapImageViews_(self, timer):
        """Swap front/back views after crossfade."""
        self.image_view_front, self.image_view_back = \
            self.image_view_back, self.image_view_front
        self.image_view_front.setAlphaValue_(1.0)
        self.image_view_back.setAlphaValue_(0.0)

    def change_state(self, new_state: str):
        """Change to new state with duration handling."""
        # Cancel any pending idle transition
        if self.pending_idle_timer:
            self.pending_idle_timer.invalidate()
            self.pending_idle_timer = None

        # Calculate size and load image
        self.calculate_size(new_state)
        self.load_state_image(new_state)
        self.resize_window()

        # Start transition animation
        self.start_transition(new_state)

        # Show speech bubble
        self.show_speech_bubble(new_state)

        # Set emotion overlays
        self.set_emotion_overlays(new_state)

        # Schedule return to idle if temporal state
        duration = STATE_DURATIONS.get(new_state)
        if duration:
            timer_method = 'scheduledTimerWithTimeInterval_' \
                'target_selector_userInfo_repeats_'
            self.pending_idle_timer = getattr(NSTimer, timer_method)(
                duration, self, 'returnToIdle:', None, False
            )

    def returnToIdle_(self, timer):
        """Auto-transition back to idle state or shutdown if farewell."""
        self.pending_idle_timer = None
        if self.current_state == 'farewell':
            self.shutdown()
        elif self.current_state not in ['idle', 'working', 'sleeping']:
            self.change_state('idle')

    def start_transition(self, state: str):
        """Start a transition animation for the given state."""
        if not self.transitions_enabled:
            return

        config = STATE_TRANSITIONS.get(state, {})
        trans_type = config.get('type', TRANSITION_NONE)

        if trans_type == TRANSITION_NONE:
            return

        self.transition_active = True
        self.transition_type = trans_type
        self.transition_start = time.time()
        self.transition_duration = config.get('duration', 0.3)
        self.transition_params = config

    def show_speech_bubble(self, state: str):
        """Show a speech bubble with a random message for the state."""
        if not self.speech_enabled:
            return

        # Cancel any pending hide timer
        if self.speech_hide_timer:
            self.speech_hide_timer.invalidate()
            self.speech_hide_timer = None

        # Get messages for this state
        state_messages = self.messages.get(state, [])
        if not state_messages:
            self.hide_speech_bubble()
            return

        # Pick a random message
        message = random.choice(state_messages)
        self.speech_bubble.setText_(message)

        # Fade in the bubble
        NSAnimationContext.beginGrouping()
        try:
            NSAnimationContext.currentContext().setDuration_(0.2)
            self.speech_bubble.animator().setAlphaValue_(1.0)
        finally:
            NSAnimationContext.endGrouping()

        # Schedule hide after duration
        timer_method = 'scheduledTimerWithTimeInterval_' \
            'target_selector_userInfo_repeats_'
        self.speech_hide_timer = getattr(NSTimer, timer_method)(
            self.speech_duration, self, 'hideSpeechBubble:', None, False
        )

    def hideSpeechBubble_(self, timer):
        """Timer callback to hide speech bubble."""
        self.speech_hide_timer = None
        self.hide_speech_bubble()

    def hide_speech_bubble(self):
        """Fade out the speech bubble."""
        NSAnimationContext.beginGrouping()
        try:
            NSAnimationContext.currentContext().setDuration_(0.3)
            self.speech_bubble.animator().setAlphaValue_(0.0)
        finally:
            NSAnimationContext.endGrouping()

    def set_emotion_overlays(self, state: str):
        """Set emotion overlays for the current state."""
        if not self.emotions_enabled:
            self.emotion_view.setEmotions_([])
            self.emotion_view.setAlphaValue_(0.0)
            return

        emotions = EMOTION_OVERLAYS.get(state, [])
        self.emotion_view.setEmotions_(emotions)

        if emotions:
            # Fade in emotion overlays
            NSAnimationContext.beginGrouping()
            try:
                NSAnimationContext.currentContext().setDuration_(0.3)
                self.emotion_view.animator().setAlphaValue_(1.0)
            finally:
                NSAnimationContext.endGrouping()
        else:
            # Fade out if no emotions for this state
            NSAnimationContext.beginGrouping()
            try:
                NSAnimationContext.currentContext().setDuration_(0.3)
                self.emotion_view.animator().setAlphaValue_(0.0)
            finally:
                NSAnimationContext.endGrouping()

    def shutdown(self):
        """Clean shutdown - fade out and exit."""
        self.fadeOut()
        # Schedule actual exit after fade completes
        timer_method = 'scheduledTimerWithTimeInterval_' \
            'target_selector_userInfo_repeats_'
        getattr(NSTimer, timer_method)(
            0.5, self, 'exitApp:', None, False
        )

    def exitApp_(self, timer):
        """Exit the application cleanly."""
        # Remove notification observer
        nc = NSWorkspace.sharedWorkspace().notificationCenter()
        nc.removeObserver_(self)
        # Stop the animation timer
        if self.timer:
            self.timer.invalidate()
            self.timer = None
        # Stop parent check timer
        if hasattr(self, 'parent_check_timer') and self.parent_check_timer:
            self.parent_check_timer.invalidate()
            self.parent_check_timer = None
        # Stop validation timer
        if hasattr(self, 'validation_timer') and self.validation_timer:
            self.validation_timer.invalidate()
            self.validation_timer = None
        # Cancel any pending timers
        if self.pending_idle_timer:
            self.pending_idle_timer.invalidate()
            self.pending_idle_timer = None
        self.cancel_pending_show()
        # Close socket server
        if self.socket_server:
            self.socket_server.close()
            self.socket_server = None
        # Clean up socket file
        if self.socket_path.exists():
            self.socket_path.unlink(missing_ok=True)
        # Clean up PID file
        if hasattr(self, 'pid_path') and self.pid_path.exists():
            self.pid_path.unlink(missing_ok=True)
        # Terminate
        self.app.terminate_(None)

    def resize_window(self):
        """Resize window and image views to current size."""
        frame = self.window.frame()
        frame.size.width = self.width
        frame.size.height = self.height
        self.window.setFrame_display_(frame, True)
        view_rect = NSMakeRect(0, 0, self.width, self.height)
        self.content_view.setFrame_(view_rect)
        self.image_view_front.setFrame_(view_rect)
        self.image_view_back.setFrame_(view_rect)

    def get_pid_from_window_id(self, window_id: int) -> int | None:
        """Get the owner PID of a window by its ID."""
        try:
            windows = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            )
            for w in windows:
                if w.get('kCGWindowNumber') == window_id:
                    return w.get('kCGWindowOwnerPID')
        except Exception:
            pass
        return None

    def update_position(self, pos: dict):
        """Update overlay position to follow terminal."""
        screen_height = NSScreen.mainScreen().frame().size.height
        x = pos['x'] + pos['w'] - self.width - self.offset_x
        y = screen_height - pos['y'] - self.offset_y - self.height

        # Store base position for floating animation
        self.base_y = y

        frame = self.window.frame()
        frame.origin.x = x
        frame.origin.y = y
        self.window.setFrame_display_(frame, True)

    def animationTick_(self, timer):
        """Run animations and track terminal position (called by NSTimer)."""
        try:
            # Visibility check during startup grace period
            in_grace = (time.time() - self.startup_time) < 1.5
            if in_grace and self.show_only_when_active:
                if not is_our_window_frontmost(
                    self.terminal_pid, self.terminal_window_id
                ):
                    if self.is_visible:
                        self.fadeOut()

            # Track terminal position and size (follow window)
            if self.is_visible and self.terminal_window_id:
                current_pos = get_terminal_window_position(
                    self.terminal_window_id
                )
                if current_pos:
                    # Check if terminal size changed (responsive resize)
                    old_h = self.last_terminal_pos.get('h') if \
                        self.last_terminal_pos else None
                    if self.responsive and old_h != current_pos['h']:
                        new_max = self.calculate_responsive_height(
                            current_pos['h']
                        )
                        if new_max != self.max_height:
                            self.max_height = new_max
                            self.calculate_size(self.current_state)
                            self.load_state_image(
                                self.current_state, crossfade=False
                            )
                            self.resize_window()

                    # Update position if changed
                    if current_pos != self.last_terminal_pos:
                        self.last_terminal_pos = current_pos
                        self.update_position(current_pos)

            # Run animations every frame
            if self.is_visible:
                elapsed = time.time() - self.animation_start
                now = time.time()

                # Initialize transform values
                rotation = 0.0
                scale_x = 1.0
                scale_y = 1.0
                offset_x = 0.0
                offset_y = 0.0

                # Floating: subtle vertical sine wave (window position)
                float_offset = FLOAT_AMPLITUDE * math.sin(
                    2 * math.pi * elapsed / FLOAT_PERIOD
                )

                # Breathing: subtle Y-axis scale pulse
                if self.breathing_enabled:
                    breath = math.sin(2 * math.pi * elapsed / BREATH_PERIOD)
                    scale_y = 1.0 + (breath * BREATH_INTENSITY)

                # Sway: gentle rotation and horizontal drift
                if self.sway_enabled:
                    sway_phase = 2 * math.pi * elapsed / SWAY_PERIOD
                    rotation += math.sin(sway_phase) * SWAY_ANGLE
                    offset_x += math.sin(sway_phase * 0.7) * SWAY_X

                # Cursor influence: tilt toward mouse
                if self.cursor_influence_enabled:
                    cursor_x, cursor_y = get_cursor_position()
                    frame = self.window.frame()
                    char_x = frame.origin.x + frame.size.width / 2
                    char_y = frame.origin.y + frame.size.height / 2

                    dx = cursor_x - char_x
                    dy = cursor_y - char_y
                    distance = math.sqrt(dx * dx + dy * dy)
                    falloff = min(1.0, CURSOR_FALLOFF / max(distance, 1))
                    strength = self.cursor_influence_strength * falloff

                    cursor_tilt = (dx / 500) * CURSOR_TILT_MAX * strength
                    cursor_shift = (dx / 500) * CURSOR_SHIFT_MAX * strength
                    rotation += cursor_tilt
                    offset_x += cursor_shift

                # Transition animations (override base transforms)
                if self.transition_active and self.transitions_enabled:
                    t_elapsed = now - self.transition_start
                    t_progress = min(1.0, t_elapsed / self.transition_duration)

                    if self.transition_type == TRANSITION_BOUNCE:
                        height = self.transition_params.get('height', 15)
                        # Bounce up with easing - peak at middle, settle back
                        if t_progress < 0.3:
                            # Rise phase
                            offset_y += height * (t_progress / 0.3)
                        else:
                            # Bounce settle phase using easing
                            settle_progress = (t_progress - 0.3) / 0.7
                            eased = ease_out_bounce(settle_progress)
                            offset_y += height * (1.0 - eased)

                    elif self.transition_type == TRANSITION_SHAKE:
                        intensity = self.transition_params.get('intensity', 8)
                        cycles = self.transition_params.get('cycles', 3)
                        # Rapid horizontal oscillation with decay
                        decay = 1.0 - t_progress
                        shake = math.sin(
                            t_progress * cycles * 2 * math.pi
                        ) * intensity * decay
                        offset_x += shake

                    elif self.transition_type == TRANSITION_SCALE_POP:
                        target = self.transition_params.get('scale', 1.08)
                        # Pop out then back using elastic easing
                        pop = ease_out_elastic(t_progress)
                        scale_mult = 1.0 + (target - 1.0) * (1.0 - pop)
                        scale_x *= scale_mult
                        scale_y *= scale_mult

                    # End transition when complete
                    if t_progress >= 1.0:
                        self.transition_active = False

                # Apply transforms to image view
                self.image_view_front.setTransform_(
                    rotation, scale_x, scale_y, offset_x, offset_y
                )

                # Update window position (floating only)
                frame = self.window.frame()
                frame.origin.y = self.base_y + float_offset
                self.window.setFrame_display_(frame, False)

                # Aura: pulsing glow radius
                aura_wave = 0.5 + 0.5 * math.sin(
                    2 * math.pi * elapsed / AURA_PERIOD
                )
                aura_range = AURA_MAX_RADIUS - AURA_MIN_RADIUS
                radius = AURA_MIN_RADIUS + aura_range * aura_wave
                self.content_view.layer().setShadowRadius_(radius)

                # Update emotion overlay animation
                if self.emotions_enabled and self.emotion_view.emotions:
                    self.emotion_view.setAnimationPhase_(elapsed)

        except Exception:
            pass

    def showWindowDeferred_(self, timer):
        """Show window after run loop has started."""
        self.window.setAlphaValue_(1.0)
        self.window.orderFront_(None)

    def fadeIn(self):
        """Smoothly show the overlay."""
        if self.is_visible:
            return
        self.window.setAlphaValue_(0.0)
        self.window.orderFront_(None)
        if self.fade_animation:
            NSAnimationContext.beginGrouping()
            try:
                NSAnimationContext.currentContext().setDuration_(0.3)
                self.window.animator().setAlphaValue_(1.0)
            finally:
                NSAnimationContext.endGrouping()
        else:
            self.window.setAlphaValue_(1.0)
        self.is_visible = True

    def fadeOut(self):
        """Smoothly hide the overlay."""
        if not self.is_visible:
            return
        if self.fade_animation:
            NSAnimationContext.beginGrouping()
            try:
                NSAnimationContext.currentContext().setDuration_(0.3)
                self.window.animator().setAlphaValue_(0.0)
            finally:
                NSAnimationContext.endGrouping()
            # Schedule orderOut after animation
            timer_method = 'scheduledTimerWithTimeInterval_' \
                'target_selector_userInfo_repeats_'
            getattr(NSTimer, timer_method)(
                0.3, self, 'hideWindow:', None, False
            )
        else:
            self.window.setAlphaValue_(0.0)
            self.window.orderOut_(None)
        self.is_visible = False

    def hideWindow_(self, timer):
        """Called after fade out animation to hide window."""
        if not self.is_visible:
            self.window.orderOut_(None)

    def appDidActivate_(self, notification):
        """Called instantly when any app becomes frontmost."""
        try:
            app = notification.userInfo()['NSWorkspaceApplicationKey']
            active_pid = app.processIdentifier()

            if active_pid != self.terminal_pid:
                # Different app - HIDE IMMEDIATELY
                self.cancel_pending_show()
                if self.is_visible:
                    self.fadeOut()
            else:
                # Our terminal - schedule debounced show check
                self.schedule_show_check()
        except Exception:
            # On any error, hide to be safe
            self.cancel_pending_show()
            if self.is_visible:
                self.fadeOut()

    def schedule_show_check(self):
        """Debounce: wait 50ms before showing to prevent flashing."""
        self.cancel_pending_show()
        m = 'scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_'
        self.pending_show_timer = getattr(NSTimer, m)(
            0.05, self, 'verifyAndShow:', None, False
        )

    def cancel_pending_show(self):
        """Cancel any pending show timer."""
        if self.pending_show_timer:
            self.pending_show_timer.invalidate()
            self.pending_show_timer = None

    def verifyAndShow_(self, timer):
        """Verify our terminal is focused before showing."""
        self.pending_show_timer = None
        # is_our_window_frontmost handles both cases:
        # - window_id known: check specific window is frontmost
        # - window_id unknown: permissive (show if terminal app frontmost)
        if is_our_window_frontmost(self.terminal_pid, self.terminal_window_id):
            if not self.is_visible:
                self.fadeIn()

    def appDidDeactivate_(self, notification):
        """Called when app loses focus - hide if our terminal deactivated."""
        try:
            app = notification.userInfo()['NSWorkspaceApplicationKey']
            deactivated_pid = app.processIdentifier()

            if deactivated_pid == self.terminal_pid:
                # Our terminal lost focus - hide immediately
                self.cancel_pending_show()
                if self.is_visible:
                    self.fadeOut()
        except Exception:
            pass

    def spaceDidChange_(self, notification):
        """Called when user switches Spaces - re-check visibility."""
        # Delay check slightly to let Space switch complete
        m = 'scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_'
        getattr(NSTimer, m)(
            0.1, self, 'checkVisibilityAfterSpaceChange:', None, False
        )

    def checkVisibilityAfterSpaceChange_(self, timer):
        """Check visibility after Space change."""
        if not self.terminal_window_id:
            return

        # Check if our window is on-screen (on current Space)
        window_on_screen = self._is_window_on_screen(self.terminal_window_id)

        if not window_on_screen:
            self.cancel_pending_show()
            if self.is_visible:
                self.fadeOut()
        elif is_our_window_frontmost(
            self.terminal_pid, self.terminal_window_id
        ):
            if not self.is_visible:
                self.schedule_show_check()

    def validateVisibility_(self, timer):
        """Periodic ground-truth check via Quartz (catches minimize, etc.)."""
        if not self.terminal_window_id:
            return

        # Skip during startup grace period
        if (time.time() - self.startup_time) < 1.5:
            return

        # Check if window is on-screen (catches minimize, Space change)
        window_on_screen = self._is_window_on_screen(self.terminal_window_id)

        if not window_on_screen:
            # Window minimized or on different Space
            self.cancel_pending_show()
            if self.is_visible:
                self.fadeOut()
        elif is_our_window_frontmost(
            self.terminal_pid, self.terminal_window_id
        ):
            # Window visible and frontmost - ensure overlay shown
            if not self.is_visible:
                self.fadeIn()

    def _is_window_on_screen(self, window_id: int) -> bool:
        """Check if a window is currently visible on screen."""
        if not window_id:
            return False
        try:
            opts = (kCGWindowListOptionOnScreenOnly |
                    kCGWindowListExcludeDesktopElements)
            windows = CGWindowListCopyWindowInfo(opts, kCGNullWindowID)
            if windows:
                for w in windows:
                    if w.get('kCGWindowNumber') == window_id:
                        return True
        except Exception:
            pass
        return False

    def _is_window_valid(self, window_id: int) -> bool:
        """Check if a window ID exists (including off-screen/minimized)."""
        if not window_id:
            return False
        try:
            # Query ALL windows, not just on-screen
            windows = CGWindowListCopyWindowInfo(0, kCGNullWindowID)
            if windows:
                for w in windows:
                    if w.get('kCGWindowNumber') == window_id:
                        return True
        except Exception:
            pass
        return False

    def run(self):
        """Start the overlay."""
        try:
            self.app.run()
        finally:
            # Clean up socket on exit
            if self.socket_server:
                self.socket_server.close()
            if self.socket_path.exists():
                self.socket_path.unlink(missing_ok=True)
            # Clean up PID file
            if hasattr(self, 'pid_path') and self.pid_path.exists():
                self.pid_path.unlink(missing_ok=True)


def main():
    # Socket binding provides singleton enforcement (bind fails if exists)
    overlay = Overlay.alloc().init()
    overlay.run()


if __name__ == '__main__':
    main()
