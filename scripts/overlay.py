#!/usr/bin/env python3
"""
Claude FX Overlay - Simple persistent overlay that shows animated GIFs.
Polls a state file and updates the displayed animation accordingly.
Supports both local files and URLs.
"""

import io
import json
import os
import sys
import urllib.request
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
CACHE_DIR = FX_DIR / 'cache'

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


def is_url(path: str) -> bool:
    """Check if path is a URL."""
    return path.startswith('http://') or path.startswith('https://')


def load_image_from_url(url: str) -> Image.Image:
    """Download and load image from URL."""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Claude-FX-Plugin/1.0'}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        data = response.read()
    return Image.open(io.BytesIO(data))


class GifPlayer:
    """Handles GIF frame extraction and cycling."""

    def __init__(self, source: str, theme_path: Path = None):
        self.frames = []
        self.durations = []
        self.current = 0
        self.load(source, theme_path)

    def load(self, source: str, theme_path: Path = None):
        """Load GIF from file path or URL."""
        self.frames = []
        self.durations = []
        self.current = 0

        try:
            if is_url(source):
                img = load_image_from_url(source)
            else:
                # Resolve relative path from theme
                if theme_path and not os.path.isabs(source):
                    path = theme_path / source
                else:
                    path = Path(source)
                if not path.exists():
                    print(f"File not found: {path}")
                    return
                img = Image.open(path)

            # Extract all frames
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

        # Load settings and manifest
        self.settings = self.load_settings()
        self.theme_path = PLUGIN_ROOT / 'themes' / 'default'
        self.manifest = self.load_manifest()

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

    def load_manifest(self) -> dict:
        """Load theme manifest."""
        manifest_file = self.theme_path / 'manifest.json'
        if manifest_file.exists():
            try:
                return json.loads(manifest_file.read_text())
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
        """Load GIF for a given state from manifest or fallback."""
        self.current_state = state

        # Try to get animation from manifest
        states = self.manifest.get('states', {})
        state_config = states.get(state, states.get('idle', {}))
        animation = state_config.get('animation', '')

        if animation:
            self.gif_player = GifPlayer(animation, self.theme_path)
        else:
            # Fallback to local file
            gif_path = self.theme_path / 'characters' / f'{state}.gif'
            if not gif_path.exists():
                gif_path = self.theme_path / 'characters' / 'idle.gif'
            if gif_path.exists():
                self.gif_player = GifPlayer(str(gif_path))

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
