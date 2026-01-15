#!/usr/bin/env python3
"""
Claude FX Overlay - True transparent overlay using PyObjC (macOS).
Displays PNG/GIF mascot with real transparency - no background window.
"""

import json
import os
import sys
from pathlib import Path

try:
    import objc
    from AppKit import NSWorkspace
    from Cocoa import (
        NSApplication, NSWindow, NSView, NSImage, NSColor, NSTimer,
        NSMakeRect, NSBackingStoreBuffered, NSFloatingWindowLevel,
        NSCompositingOperationSourceOver, NSScreen,
        NSAnimationContext,
    )
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
    )
except ImportError:
    print("Required: pip3 install pyobjc-framework-Cocoa")
    sys.exit(1)

# Paths
HOME = Path.home()
FX_DIR = HOME / '.claude-fx'
STATE_FILE = FX_DIR / 'state.json'
PID_FILE = FX_DIR / 'overlay.pid'

PLUGIN_ROOT = Path(os.environ.get(
    'CLAUDE_FX_ROOT',
    Path(__file__).parent.parent
))

# Default settings
DEFAULT_MAX_HEIGHT = 350
DEFAULT_OFFSET_X = 20
DEFAULT_OFFSET_Y = 40

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


def load_settings() -> dict:
    """Load settings from settings-fx.json."""
    settings_file = PLUGIN_ROOT / 'settings-fx.json'
    if settings_file.exists():
        try:
            return json.loads(settings_file.read_text())
        except Exception:
            pass
    return {}


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


def is_terminal_window_visible(terminal_pid: int, window_id: int) -> bool:
    """Check if our specific terminal window is visible and frontmost."""
    if not terminal_pid:
        return True  # Fallback: always show if no PID tracked

    try:
        # First check if terminal app is frontmost
        frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
        if frontmost.processIdentifier() != terminal_pid:
            return False  # Different app is active

        # If we have a window ID, check if it's the topmost terminal window
        if window_id:
            windows = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            )
            # Find first window belonging to our terminal (topmost)
            for w in windows:
                if w.get('kCGWindowOwnerPID') == terminal_pid:
                    # First terminal window we find is the frontmost one
                    return w.get('kCGWindowNumber') == window_id

        return True  # Fallback if no window ID
    except Exception:
        return True


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
    """Custom view that draws an image with transparency."""

    def initWithFrame_(self, frame):
        self = objc.super(ImageView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.image = None
        return self

    def setImage_(self, image):
        self.image = image
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        if self.image:
            # Draw image scaled to fit view
            bounds = self.bounds()
            self.image.drawInRect_fromRect_operation_fraction_(
                bounds,
                NSMakeRect(0, 0, 0, 0),  # Use full source
                NSCompositingOperationSourceOver,
                1.0
            )


class Overlay:
    """Transparent overlay window with animated character."""

    def __init__(self):
        self.app = NSApplication.sharedApplication()

        # Load settings
        self.settings = load_settings()
        overlay_cfg = self.settings.get('overlay', {})
        self.max_height = overlay_cfg.get('maxHeight', DEFAULT_MAX_HEIGHT)
        self.offset_x = overlay_cfg.get('offsetX', DEFAULT_OFFSET_X)
        self.offset_y = overlay_cfg.get('offsetY', DEFAULT_OFFSET_Y)

        # Load manifest
        theme_name = self.settings.get('theme', 'default')
        self.theme_path = PLUGIN_ROOT / 'themes' / theme_name
        self.manifest = self.load_manifest()

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
        self.window.setContentView_(self.content_view)

        # State tracking
        self.current_state = 'idle'
        self.pending_idle_timer = None
        self.load_state_image('idle', crossfade=False)

        # Visibility tracking
        self.terminal_pid = None
        self.terminal_window_id = None
        self.is_visible = True
        self.last_terminal_pos = None
        self.show_only_when_active = overlay_cfg.get(
            'showOnlyWhenTerminalActive', True
        )
        self.fade_animation = overlay_cfg.get('fadeAnimation', True)

        # Show window
        self.window.makeKeyAndOrderFront_(None)

        # Start polling timer (every 0.016 seconds = 60fps for smooth movement)
        m = 'scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_'
        self.timer = getattr(NSTimer, m)(0.016, self, 'pollState:', None, True)

        # Write PID
        self.write_pid()

    def load_manifest(self) -> dict:
        """Load theme manifest."""
        manifest_file = self.theme_path / 'manifest.json'
        if manifest_file.exists():
            try:
                return json.loads(manifest_file.read_text())
            except Exception:
                pass
        return {}

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
        """Load image for a given state."""
        self.current_state = state

        states = self.manifest.get('states', {})
        # Use greeting image for farewell (wave goodbye)
        lookup_state = 'greeting' if state == 'farewell' else state
        state_config = states.get(lookup_state, states.get('idle', {}))
        animation = state_config.get('animation', '')

        if animation:
            img_path = self.theme_path / animation
            if img_path.exists():
                img = NSImage.alloc().initWithContentsOfFile_(str(img_path))
                if img:
                    # Scale image
                    img.setSize_((self.width, self.height))
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
        NSAnimationContext.currentContext().setDuration_(0.2)
        self.image_view_front.animator().setAlphaValue_(0.0)
        self.image_view_back.animator().setAlphaValue_(1.0)
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
        # Stop the poll timer
        if self.timer:
            self.timer.invalidate()
            self.timer = None
        # Cancel any pending timers
        if self.pending_idle_timer:
            self.pending_idle_timer.invalidate()
            self.pending_idle_timer = None
        # Clean up PID file
        if PID_FILE.exists():
            PID_FILE.unlink()
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

    def update_position(self, pos: dict):
        """Update overlay position to follow terminal."""
        screen_height = NSScreen.mainScreen().frame().size.height
        x = pos['x'] + pos['w'] - self.width - self.offset_x
        y = screen_height - pos['y'] - self.offset_y - self.height

        frame = self.window.frame()
        frame.origin.x = x
        frame.origin.y = y
        self.window.setFrame_display_(frame, True)

    def pollState_(self, timer):
        """Check state file for updates (called by NSTimer)."""
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                new_state = data.get('state', 'idle')

                # Get terminal info (only once, on first poll)
                if self.terminal_pid is None:
                    self.terminal_pid = data.get('terminal_pid')
                    self.terminal_window_id = data.get('terminal_window_id')

                # Check visibility if tracking is enabled
                if self.show_only_when_active:
                    should_show = is_terminal_window_visible(
                        self.terminal_pid, self.terminal_window_id
                    )
                    if should_show and not self.is_visible:
                        self.fadeIn()
                    elif not should_show and self.is_visible:
                        self.fadeOut()

                # Track terminal position (follow window movement)
                if self.is_visible and self.terminal_window_id:
                    current_pos = get_terminal_window_position(
                        self.terminal_window_id
                    )
                    if current_pos and current_pos != self.last_terminal_pos:
                        self.last_terminal_pos = current_pos
                        self.update_position(current_pos)

                # Update state if visible and changed
                if self.is_visible and new_state != self.current_state:
                    self.change_state(new_state)
        except Exception:
            pass

    def write_pid(self):
        """Write PID file."""
        FX_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

    def fadeIn(self):
        """Smoothly show the overlay."""
        if self.is_visible:
            return
        self.window.setAlphaValue_(0.0)
        self.window.orderFront_(None)
        if self.fade_animation:
            NSAnimationContext.beginGrouping()
            NSAnimationContext.currentContext().setDuration_(0.3)
            self.window.animator().setAlphaValue_(1.0)
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
            NSAnimationContext.currentContext().setDuration_(0.3)
            self.window.animator().setAlphaValue_(0.0)
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

    def run(self):
        """Start the overlay."""
        try:
            self.app.run()
        finally:
            if PID_FILE.exists():
                PID_FILE.unlink()


def is_running() -> bool:
    """Check if overlay is already running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text())
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink()
    return False


def main():
    if is_running():
        print("Overlay already running")
        sys.exit(0)

    overlay = Overlay()
    overlay.run()


if __name__ == '__main__':
    main()
