#!/usr/bin/env python3
"""
Claude FX Overlay - Simple persistent overlay that shows animated GIFs.
Polls a state file and updates the displayed animation accordingly.
"""

import json
import os
import sys
import subprocess
from pathlib import Path

try:
    import tkinter as tk
    from PIL import Image, ImageTk
except ImportError:
    print("Required: pip install pillow")
    sys.exit(1)

# Paths
HOME = Path.home()
FX_DIR = HOME / '.claude-fx'
STATE_FILE = FX_DIR / 'state.json'
PID_FILE = FX_DIR / 'overlay.pid'

# Get plugin root from env or default
PLUGIN_ROOT = Path(os.environ.get(
    'CLAUDE_FX_ROOT',
    Path(__file__).parent.parent
))


def get_terminal_position():
    """Get active terminal window position (macOS)."""
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID
        )
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
    # Fallback: bottom-right of screen
    return {'x': 100, 'y': 100, 'w': 800, 'h': 600}


class GifPlayer:
    """Handles GIF frame extraction and cycling."""

    def __init__(self, path: Path):
        self.frames = []
        self.durations = []
        self.current = 0
        self.load(path)

    def load(self, path: Path):
        """Load GIF and extract frames."""
        self.frames = []
        self.durations = []
        self.current = 0

        if not path.exists():
            return

        try:
            img = Image.open(path)
            while True:
                frame = img.copy().convert('RGBA')
                self.frames.append(frame)
                self.durations.append(img.info.get('duration', 100))
                img.seek(img.tell() + 1)
        except EOFError:
            pass
        except Exception as e:
            print(f"Error loading GIF: {e}")

    def next_frame(self) -> tuple:
        """Get next frame and its duration."""
        if not self.frames:
            return None, 100
        frame = self.frames[self.current]
        duration = self.durations[self.current]
        self.current = (self.current + 1) % len(self.frames)
        return frame, duration


class Overlay:
    """Transparent overlay window with animated character."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Claude FX")

        # Transparent, borderless, always-on-top
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        # macOS transparency
        try:
            self.root.attributes('-transparent', True)
            self.root.config(bg='systemTransparent')
            self.bg_color = 'systemTransparent'
        except Exception:
            # Fallback for Linux
            self.root.attributes('-alpha', 0.95)
            self.bg_color = '#1a1a1a'
            self.root.config(bg=self.bg_color)

        # Canvas for the image
        self.size = 150
        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size,
            bg=self.bg_color,
            highlightthickness=0
        )
        self.canvas.pack()

        # Load settings
        self.settings = self.load_settings()
        self.theme_path = PLUGIN_ROOT / 'themes' / 'default'

        # State tracking
        self.current_state = 'idle'
        self.gif_player = None
        self.photo = None

        # Position near terminal
        self.position_window()

        # Load initial state
        self.load_state_gif('idle')

        # Start animation and polling loops
        self.animate()
        self.poll_state()

        # Write PID
        self.write_pid()

    def load_settings(self) -> dict:
        """Load settings from settings-fx.json."""
        settings_file = PLUGIN_ROOT / 'settings-fx.json'
        if settings_file.exists():
            try:
                return json.loads(settings_file.read_text())
            except Exception:
                pass
        return {}

    def position_window(self):
        """Position overlay next to terminal."""
        pos = get_terminal_position()
        # Bottom-right of terminal with offset
        x = pos['x'] + pos['w'] - self.size - 20
        y = pos['y'] + pos['h'] - self.size - 40
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")

    def load_state_gif(self, state: str):
        """Load GIF for a given state."""
        gif_path = self.theme_path / 'characters' / f'{state}.gif'
        if not gif_path.exists():
            gif_path = self.theme_path / 'characters' / 'idle.gif'
        if gif_path.exists():
            self.gif_player = GifPlayer(gif_path)
        self.current_state = state

    def animate(self):
        """Update animation frame."""
        if self.gif_player and self.gif_player.frames:
            frame, duration = self.gif_player.next_frame()
            if frame:
                # Resize to fit
                frame = frame.resize((self.size, self.size), Image.LANCZOS)
                self.photo = ImageTk.PhotoImage(frame)
                self.canvas.delete('all')
                self.canvas.create_image(
                    self.size // 2, self.size // 2,
                    image=self.photo
                )
            self.root.after(duration, self.animate)
        else:
            self.root.after(100, self.animate)

    def poll_state(self):
        """Check state file for updates."""
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                new_state = data.get('state', 'idle')
                if new_state != self.current_state:
                    self.load_state_gif(new_state)
                    # Reposition in case terminal moved
                    self.position_window()
        except Exception:
            pass
        self.root.after(100, self.poll_state)

    def write_pid(self):
        """Write PID file."""
        FX_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

    def run(self):
        """Start the overlay."""
        try:
            self.root.mainloop()
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
