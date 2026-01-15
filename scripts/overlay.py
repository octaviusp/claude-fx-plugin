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
    from Cocoa import (
        NSApplication, NSWindow, NSView, NSImage, NSColor, NSTimer,
        NSMakeRect, NSBackingStoreBuffered, NSFloatingWindowLevel,
        NSCompositingOperationSourceOver, NSScreen,
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

MAX_HEIGHT = 350


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

        # Load manifest
        self.theme_path = PLUGIN_ROOT / 'themes' / 'default'
        self.manifest = self.load_manifest()

        # Calculate size from first image
        self.width = 200
        self.height = MAX_HEIGHT
        self.calculate_size('idle')

        # Get terminal position
        pos = get_terminal_position()
        x = pos['x'] + pos['w'] - self.width - 20
        # macOS y is from bottom, convert from top
        screen_height = NSScreen.mainScreen().frame().size.height
        y = screen_height - pos['y'] - 40 - self.height

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

        # Create image view
        self.image_view = ImageView.alloc().initWithFrame_(
            NSMakeRect(0, 0, self.width, self.height)
        )
        self.window.setContentView_(self.image_view)

        # State tracking
        self.current_state = 'idle'
        self.load_state_image('idle')

        # Show window
        self.window.makeKeyAndOrderFront_(None)

        # Start polling timer (every 0.2 seconds)
        m = 'scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_'
        self.timer = getattr(NSTimer, m)(0.2, self, 'pollState:', None, True)

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
                    if size.height > MAX_HEIGHT:
                        ratio = MAX_HEIGHT / size.height
                        self.width = int(size.width * ratio)
                        self.height = MAX_HEIGHT
                    else:
                        self.width = int(size.width)
                        self.height = int(size.height)

    def load_state_image(self, state: str):
        """Load image for a given state."""
        self.current_state = state

        states = self.manifest.get('states', {})
        state_config = states.get(state, states.get('idle', {}))
        animation = state_config.get('animation', '')

        if animation:
            img_path = self.theme_path / animation
            if img_path.exists():
                img = NSImage.alloc().initWithContentsOfFile_(str(img_path))
                if img:
                    # Scale image
                    img.setSize_((self.width, self.height))
                    self.image_view.setImage_(img)

    def pollState_(self, timer):
        """Check state file for updates (called by NSTimer)."""
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                new_state = data.get('state', 'idle')
                if new_state != self.current_state:
                    self.calculate_size(new_state)
                    self.load_state_image(new_state)
                    # Resize window
                    frame = self.window.frame()
                    frame.size.width = self.width
                    frame.size.height = self.height
                    self.window.setFrame_display_(frame, True)
                    self.image_view.setFrame_(
                        NSMakeRect(0, 0, self.width, self.height)
                    )
        except Exception:
            pass

    def write_pid(self):
        """Write PID file."""
        FX_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

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
