#!/usr/bin/env python3
"""
Claude FX Hook Handler - Receives hook events and updates overlay state.
Includes setup checking on SessionStart.
"""

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Debug logging (set CLAUDE_FX_DEBUG=1 to enable)
_debug = os.environ.get('CLAUDE_FX_DEBUG', '0') == '1'
logging.basicConfig(
    level=logging.DEBUG if _debug else logging.WARNING,
    format='[claude-fx] %(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Session ID cache (terminal PID, set once per hook invocation)
_session_id = None

# Paths
HOME = Path.home()
FX_DIR = HOME / '.claude-fx'
SETUP_OK_FILE = FX_DIR / 'setup_ok'


def get_socket_path(session_id: int) -> Path:
    """Get socket file path for a session."""
    return FX_DIR / f'sock-{session_id}.sock'


def get_session_id() -> Optional[int]:
    """Get session ID (shell PID for isolation)."""
    global _session_id
    if _session_id is None:
        info = get_terminal_info()
        if info:
            # Use shell_pid for session isolation (unique per terminal window)
            _session_id = info.get('shell_pid')
    return _session_id


PLUGIN_ROOT = Path(os.environ.get(
    'CLAUDE_PLUGIN_ROOT',
    Path(__file__).parent.parent
))

TERMINAL_NAMES = {
    'Terminal', 'iTerm2', 'Alacritty', 'kitty', 'Warp', 'WezTerm'
}

# Cache for terminal info with TTL
_terminal_info = None
_terminal_info_time: float = 0.0
TERMINAL_INFO_CACHE_TTL = 30.0  # Refresh every 30 seconds


def get_terminal_info() -> Optional[dict]:
    """Get terminal info for the shell running Claude Code.

    Returns dict with:
    - shell_pid: PID of the shell (for session isolation)
    - terminal_pid: PID of terminal app (for visibility tracking)
    - window_id: Terminal window ID (for visibility tracking)
    """
    global _terminal_info, _terminal_info_time

    # Return cached if still valid
    now = time.time()
    if _terminal_info is not None:
        if (now - _terminal_info_time) < TERMINAL_INFO_CACHE_TTL:
            return _terminal_info
        logger.debug("Terminal info cache expired, refreshing")

    # Walk process tree to find shell and terminal
    shell_pid = None
    terminal_pid = None
    pid = os.getpid()
    prev_pid = None

    while pid > 1:
        try:
            result = subprocess.run(
                ['ps', '-p', str(pid), '-o', 'ppid=,comm='],
                capture_output=True, text=True
            )
            parts = result.stdout.strip().split(None, 1)
            if len(parts) >= 2:
                ppid, comm = int(parts[0]), parts[1]

                # Check if this is a terminal app
                if any(t.lower() in comm.lower() for t in TERMINAL_NAMES):
                    terminal_pid = pid
                    # shell_pid is the process just below terminal
                    if prev_pid:
                        shell_pid = prev_pid
                    break

                prev_pid = pid
                pid = ppid
            else:
                break
        except Exception:
            break

    if not terminal_pid:
        return None

    # If we didn't find a shell, use the first child we tracked
    if not shell_pid:
        shell_pid = prev_pid or terminal_pid

    # Get window ID by enumerating terminal's windows (even if not frontmost)
    window_id = None
    try:
        from AppKit import NSWorkspace
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
        )

        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        )

        # Find windows belonging to our terminal PID (layer 0 = normal windows)
        terminal_windows = []
        for w in windows:
            if w.get('kCGWindowOwnerPID') == terminal_pid:
                layer = w.get('kCGWindowLayer', 0)
                if layer == 0:
                    terminal_windows.append(w.get('kCGWindowNumber'))

        if len(terminal_windows) == 1:
            # Only one window - use it
            window_id = terminal_windows[0]
        elif len(terminal_windows) > 1:
            # Multiple windows - check if one is frontmost
            frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
            if frontmost.processIdentifier() == terminal_pid:
                # Terminal is frontmost, first layer-0 window is active
                window_id = terminal_windows[0]
            # If not frontmost, can't reliably pick the right window
            # Leave window_id as None - overlay will detect it later
    except Exception:
        pass

    _terminal_info = {
        'shell_pid': shell_pid,
        'terminal_pid': terminal_pid,
        'window_id': window_id
    }
    _terminal_info_time = time.time()
    logger.debug(f"Terminal info cached: {_terminal_info}")
    return _terminal_info


def load_settings() -> dict:
    """Load settings from settings-fx.json."""
    settings_file = PLUGIN_ROOT / 'settings-fx.json'
    if settings_file.exists():
        try:
            return json.loads(settings_file.read_text())
        except Exception:
            pass
    return {}


def read_stdin() -> dict:
    """Read JSON from stdin."""
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except Exception:
        return {}


def check_setup() -> bool:
    """
    Check if setup is complete.
    Returns True if all requirements are met.
    """
    # Quick check - if setup_ok file exists, we're good
    if SETUP_OK_FILE.exists():
        return True

    # Run full setup check
    setup_script = PLUGIN_ROOT / 'scripts' / 'setup.py'
    if not setup_script.exists():
        return True  # No setup script, assume OK

    try:
        # Import and run setup check
        import importlib.util
        spec = importlib.util.spec_from_file_location("setup", setup_script)
        setup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_module)

        # Run check (quiet mode, no auto-install)
        return setup_module.main(force_check=True, quiet=False)
    except Exception as e:
        # If setup check fails, print error but don't block
        print(f"Setup check error: {e}", file=sys.stderr)
        return False


def map_event_to_state(event: str, is_error: bool = False) -> str:
    """Map hook event to overlay state."""
    mapping = {
        'SessionStart': 'greeting',
        'PreToolUse': 'working',
        'PostToolUse': 'success' if not is_error else 'error',
        'Stop': 'celebrating',
        'SessionEnd': 'farewell',
        'Notification': 'idle',
    }
    return mapping.get(event, 'idle')


def detect_error(data: dict) -> bool:
    """Check if tool execution had an error."""
    result = data.get('tool_result', {})
    if isinstance(result, dict):
        if result.get('error'):
            return True
        output = str(result.get('output', ''))
    else:
        output = str(result)

    error_patterns = ['error:', 'Error:', 'ERROR', 'failed', 'ENOENT']
    return any(p in output for p in error_patterns)


def send_state_to_overlay(state: str, tool: str = None) -> bool:
    """Send state update to overlay via socket. Returns True if successful."""
    session_id = get_session_id()
    if not session_id:
        logger.debug("No session ID available")
        return False

    socket_path = get_socket_path(session_id)
    if not socket_path.exists():
        logger.debug(f"Socket not found: {socket_path}")
        return False

    # Get terminal info for visibility tracking
    info = get_terminal_info() or {}

    # Build message
    msg = {
        'cmd': 'SET_STATE',
        'state': state,
        'tool': tool,
        'terminal_pid': info.get('terminal_pid'),
        'terminal_window_id': info.get('window_id')
    }

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.5)  # 500ms timeout - don't block Claude
        sock.connect(str(socket_path))
        sock.sendall(f'{json.dumps(msg)}\n'.encode('utf-8'))
        response = sock.recv(1024).decode('utf-8').strip()
        sock.close()
        logger.debug(f"State sent: {state}, response: {response[:50]}")
        return response.startswith('{"status": "ok"}')
    except socket.timeout:
        logger.debug(f"Socket timeout connecting to {socket_path}")
        return False
    except ConnectionRefusedError:
        logger.debug(f"Connection refused: {socket_path}")
        return False
    except FileNotFoundError:
        logger.debug(f"Socket file not found: {socket_path}")
        return False
    except Exception as e:
        logger.debug(f"Socket error: {e}")
        return False


def is_overlay_running() -> bool:
    """Check if overlay is running by testing socket connection."""
    session_id = get_session_id()
    if not session_id:
        return False

    socket_path = get_socket_path(session_id)
    if not socket_path.exists():
        return False

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.1)  # Fast check
        sock.connect(str(socket_path))
        sock.sendall(b'{"cmd": "PING"}\n')
        response = sock.recv(64).decode('utf-8').strip()
        sock.close()
        return response == 'PONG'
    except Exception:
        return False


def _cleanup_session_files(session_id: int):
    """Remove socket and PID files for a session."""
    socket_path = get_socket_path(session_id)
    pid_path = FX_DIR / f'pid-{session_id}.txt'

    if socket_path.exists():
        try:
            socket_path.unlink()
        except Exception:
            pass
    if pid_path.exists():
        try:
            pid_path.unlink()
        except Exception:
            pass


def shutdown_overlay():
    """Send shutdown command via socket, with forceful kill fallback."""
    session_id = get_session_id()
    if not session_id:
        return

    socket_path = get_socket_path(session_id)
    pid_path = FX_DIR / f'pid-{session_id}.txt'

    shutdown_sent = False

    # Try graceful shutdown via socket
    if socket_path.exists():
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(str(socket_path))
            sock.sendall(b'{"cmd": "SHUTDOWN"}\n')
            sock.recv(1024)  # Wait for ack
            sock.close()
            shutdown_sent = True
        except Exception:
            pass

    # Forceful kill fallback using PID file
    if not shutdown_sent and pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            # Give it 0.5s to exit gracefully
            time.sleep(0.5)
            # If still alive, SIGKILL
            try:
                os.kill(pid, 0)  # Check if alive
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Already dead
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    # Clean up files regardless
    _cleanup_session_files(session_id)


def kill_orphaned_overlays():
    """Kill any overlay processes that don't have a valid session."""
    try:
        # Find all overlay.py processes
        result = subprocess.run(
            ['pgrep', '-f', 'overlay.py'],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return

        pids = [int(p) for p in result.stdout.strip().split('\n') if p]

        # Get list of valid overlay PIDs from existing PID files
        valid_pids = set()
        for pid_file in FX_DIR.glob('pid-*.txt'):
            try:
                valid_pids.add(int(pid_file.read_text().strip()))
            except Exception:
                pass

        # Kill any overlay not in valid set
        for pid in pids:
            if pid not in valid_pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
    except Exception:
        pass


def change_character_folder(folder: str) -> dict:
    """Send character folder change command to overlay."""
    session_id = get_session_id()
    if not session_id:
        return {"status": "error", "message": "no session"}

    socket_path = get_socket_path(session_id)
    if not socket_path.exists():
        return {"status": "error", "message": "overlay not running"}

    msg = {'cmd': 'CHANGE_CHARACTER', 'folder': folder}

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect(str(socket_path))
        sock.sendall(f'{json.dumps(msg)}\n'.encode('utf-8'))
        response = sock.recv(4096).decode('utf-8').strip()
        sock.close()
        return json.loads(response)
    except Exception as e:
        return {"status": "error", "message": str(e)}


def reload_settings() -> dict:
    """Send settings reload command to overlay."""
    session_id = get_session_id()
    if not session_id:
        return {"status": "error", "message": "no session"}

    socket_path = get_socket_path(session_id)
    if not socket_path.exists():
        return {"status": "error", "message": "overlay not running"}

    msg = {'cmd': 'RELOAD_SETTINGS'}

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect(str(socket_path))
        sock.sendall(f'{json.dumps(msg)}\n'.encode('utf-8'))
        response = sock.recv(4096).decode('utf-8').strip()
        sock.close()
        return json.loads(response)
    except Exception as e:
        return {"status": "error", "message": str(e)}


def cleanup_legacy_files():
    """Remove old state/pid/lock files from file-based IPC era."""
    if not FX_DIR.exists():
        return

    patterns = [
        'state-*.json', 'overlay-*.pid', 'overlay-*.lock',
        'state.json', 'overlay.pid', 'overlay.lock',
        'overlay.sock'  # Legacy socket from when SESSION_ID wasn't set
    ]

    for pattern in patterns:
        for f in FX_DIR.glob(pattern):
            try:
                f.unlink()
            except Exception:
                pass


def start_overlay():
    """Start session-specific overlay process in background."""
    session_id = get_session_id()
    if not session_id:
        return
    overlay_script = PLUGIN_ROOT / 'scripts' / 'overlay.py'
    if overlay_script.exists():
        env = os.environ.copy()
        env['CLAUDE_FX_ROOT'] = str(PLUGIN_ROOT)
        env['CLAUDE_FX_SESSION'] = str(session_id)  # Pass session ID
        subprocess.Popen(
            [sys.executable, str(overlay_script)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )


def send_sound_to_overlay(state: str) -> bool:
    """Send sound playback command to overlay via socket.

    Sound is played by overlay.py using NSSound (in-process, no subprocess).
    This eliminates afplay process accumulation that bloats coreaudiod.
    """
    session_id = get_session_id()
    if not session_id:
        return False

    socket_path = get_socket_path(session_id)
    if not socket_path.exists():
        return False

    msg = {'cmd': 'PLAY_SOUND', 'state': state}

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        sock.connect(str(socket_path))
        sock.sendall(f'{json.dumps(msg)}\n'.encode('utf-8'))
        response = sock.recv(1024).decode('utf-8').strip()
        sock.close()
        return response.startswith('{"status": "ok"}')
    except (socket.timeout, ConnectionRefusedError, FileNotFoundError):
        return False
    except Exception:
        return False


def main():
    """Main entry point."""
    # Handle CLI commands (e.g., change-character, reload-settings)
    if len(sys.argv) > 1 and sys.argv[1] == 'change-character':
        folder = sys.argv[2] if len(sys.argv) > 2 else 'characters'
        result = change_character_folder(folder)
        print(json.dumps(result))
        sys.exit(0 if result.get('status') == 'ok' else 1)

    if len(sys.argv) > 1 and sys.argv[1] == 'reload-settings':
        result = reload_settings()
        print(json.dumps(result))
        sys.exit(0 if result.get('status') == 'ok' else 1)

    # Read hook event
    data = read_stdin()
    event = data.get('hook_event_name', '')

    if not event:
        sys.exit(0)

    # On SessionStart, check setup first
    if event == 'SessionStart':
        # Clean up legacy files from old file-based IPC
        cleanup_legacy_files()

        if not check_setup():
            # Setup incomplete - message already shown by setup.py
            # Don't start overlay, just exit
            sys.exit(0)

    # Skip overlay actions if setup not complete
    if not SETUP_OK_FILE.exists():
        sys.exit(0)

    # Load settings
    settings = load_settings()

    # Check if overlay is enabled
    overlay_cfg = settings.get('overlay', {})
    overlay_enabled = overlay_cfg.get('enabled', True)

    # Determine state
    is_error = event == 'PostToolUse' and detect_error(data)
    state = map_event_to_state(event, is_error)
    tool = data.get('tool_name')

    # Handle SessionEnd - show farewell and shutdown overlay
    if event == 'SessionEnd':
        send_state_to_overlay(state, tool)
        send_sound_to_overlay('farewell')
        time.sleep(0.3)  # Brief delay for farewell to show
        shutdown_overlay()  # Graceful + forceful fallback
        kill_orphaned_overlays()  # Clean up any strays
        sys.exit(0)

    # Send state to overlay via socket
    sent = send_state_to_overlay(state, tool)

    # Start overlay if not running and enabled
    if overlay_enabled and not sent and not is_overlay_running():
        logger.debug("Starting overlay process")
        start_overlay()
        # Retry with exponential backoff (100ms, 200ms, 400ms)
        for attempt, delay in enumerate([0.1, 0.2, 0.4]):
            time.sleep(delay)
            if send_state_to_overlay(state, tool):
                logger.debug(f"State sent on attempt {attempt + 1}")
                break
        else:
            logger.debug("Failed to send state after retries")

    # Play sound (via overlay's NSSound - no subprocess)
    send_sound_to_overlay(state)

    # Always exit 0 to not block Claude
    sys.exit(0)


if __name__ == '__main__':
    main()
