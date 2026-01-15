#!/usr/bin/env python3
"""
Claude FX Plugin - Setup & Requirements Checker

Checks all dependencies and provides helpful guidance for installation.
Can be run standalone or called from hook-handler.py on SessionStart.
"""

import platform
import sys
from pathlib import Path


class Colors:
    """ANSI colors for terminal output."""

    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def colored(text, color):
    """Apply color to text if terminal supports it."""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.END}"
    return text


def print_header():
    """Print plugin header with box drawing."""
    print()
    top = "╔════════════════════════════════════════════╗"
    mid = "║     Claude FX Plugin - Requirements        ║"
    bot = "╚════════════════════════════════════════════╝"
    print(colored(top, Colors.CYAN))
    print(colored(mid, Colors.CYAN))
    print(colored(bot, Colors.CYAN))
    print()


def print_status(name, ok, detail=""):
    """Print a status line."""
    if ok:
        status = colored("✓", Colors.GREEN)
    else:
        status = colored("✗", Colors.RED)

    line = f"  {status} {name}"
    if detail:
        line += f" ({detail})"
    print(line)


def get_platform_info():
    """Get platform information."""
    system = platform.system().lower()
    machine = platform.machine()

    if system == 'darwin':
        return 'macos', machine
    elif system == 'linux':
        return 'linux', machine
    elif system == 'windows':
        return 'windows', machine
    return 'unknown', machine


def get_python_version():
    """Get Python version tuple."""
    return sys.version_info[:3]


def check_python():
    """Check Python version."""
    version = get_python_version()
    version_str = f"{version[0]}.{version[1]}.{version[2]}"
    ok = version >= (3, 9, 0)
    return ok, version_str


def check_pillow():
    """Check if Pillow is installed."""
    try:
        import PIL
        return True, PIL.__version__
    except ImportError:
        return False, "not installed"


def check_quartz():
    """Check if Quartz (pyobjc) is available - macOS only."""
    plat, _ = get_platform_info()
    if plat != 'macos':
        return True, "not needed"

    try:
        import Quartz  # noqa: F401
        return True, "available"
    except ImportError:
        return False, "not installed"


def is_homebrew_python():
    """Check if running Homebrew-managed Python."""
    exe = sys.executable.lower()
    return 'homebrew' in exe or 'cellar' in exe


def get_install_commands(missing, plat, python_version):
    """Get platform-specific install commands for missing deps."""
    _ = python_version  # Reserved for future use
    commands = []

    # Determine pip flags for Homebrew Python
    pip_flags = ""
    if plat == 'macos' and is_homebrew_python():
        pip_flags = " --break-system-packages"

    if 'pillow' in missing:
        if plat == 'macos':
            commands.append(("Pillow", f"pip3 install pillow{pip_flags}"))
        elif plat == 'linux':
            commands.append(("Pillow", "pip3 install pillow"))
        else:
            commands.append(("Pillow", "pip install pillow"))

    if 'quartz' in missing and plat == 'macos':
        cmd = f"pip3 install pyobjc-framework-Quartz{pip_flags}"
        commands.append(("Quartz", cmd))

    return commands


def check_all():
    """
    Run all checks and return results.

    Returns:
        tuple: (all_ok, results_dict, missing_list)
    """
    results = {}
    missing = []

    plat, arch = get_platform_info()
    results['platform'] = (True, f"{plat}/{arch}")

    ok, ver = check_python()
    results['python'] = (ok, ver)
    if not ok:
        missing.append('python')

    ok, ver = check_pillow()
    results['pillow'] = (ok, ver)
    if not ok:
        missing.append('pillow')

    ok, detail = check_quartz()
    results['quartz'] = (ok, detail)
    if not ok and plat == 'macos':
        missing.append('quartz')

    all_ok = len(missing) == 0
    return all_ok, results, missing


def print_results(results, missing):
    """Print check results."""
    print(colored("  Requirements:", Colors.BOLD))
    print()

    print_status("Platform", True, results['platform'][1])
    print_status("Python 3.9+", results['python'][0], results['python'][1])
    print_status("Pillow", results['pillow'][0], results['pillow'][1])

    plat, _ = get_platform_info()
    if plat == 'macos':
        print_status("pyobjc-framework-Quartz", results['quartz'][0],
                     results['quartz'][1])

    print()


def print_install_instructions(missing, commands):
    """Print installation instructions with box drawing."""
    if not missing:
        return

    # Print command box
    w = 50  # inner width
    print(colored("┌" + "─" * w + "┐", Colors.CYAN))
    print(colored("│" + "  Install missing dependencies:".ljust(w) + "│",
                  Colors.CYAN))
    print(colored("├" + "─" * w + "┤", Colors.CYAN))
    print(colored("│" + " " * w + "│", Colors.CYAN))

    for _, cmd in commands:
        padded = f"  {cmd}".ljust(w)
        print(colored(f"│{padded}│", Colors.CYAN))

    print(colored("│" + " " * w + "│", Colors.CYAN))
    print(colored("└" + "─" * w + "┘", Colors.CYAN))
    print()

    restart = colored('restart Claude Code', Colors.YELLOW)
    print(f"  After installing, {restart} to activate.")
    print()


def save_setup_status(ok):
    """Save setup status to avoid repeated checks."""
    status_dir = Path.home() / '.claude-fx'
    status_dir.mkdir(parents=True, exist_ok=True)
    status_file = status_dir / 'setup_ok'

    if ok:
        status_file.write_text('1')
    elif status_file.exists():
        status_file.unlink()


def is_setup_complete():
    """Check if setup was already completed."""
    status_file = Path.home() / '.claude-fx' / 'setup_ok'
    return status_file.exists()


def main(force_check=False, quiet=False):
    """
    Main setup function.

    Args:
        force_check: Run checks even if setup was already complete
        quiet: Don't print anything if all checks pass

    Returns:
        bool: True if all required dependencies are available
    """
    if not force_check and is_setup_complete():
        return True

    all_ok, results, missing = check_all()

    if all_ok:
        if not quiet:
            print_header()
            print_results(results, missing)
            msg = "  ✓ All requirements met! Plugin ready."
            print(colored(msg, Colors.GREEN))
            print()
        save_setup_status(True)
        return True

    print_header()
    print_results(results, missing)

    plat, _ = get_platform_info()
    python_ver = get_python_version()
    commands = get_install_commands(missing, plat, python_ver)

    if not commands:
        save_setup_status(True)
        return True

    print_install_instructions(missing, commands)

    print(colored(
        "  Run /claude-fx:setup to check again after installing.",
        Colors.BLUE
    ))
    print()

    return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Claude FX Plugin Setup')
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force check even if already setup'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Quiet mode - only output if something is missing'
    )
    parser.add_argument(
        '--check-only', '-c',
        action='store_true',
        help='Check only, exit with code 1 if deps missing'
    )

    args = parser.parse_args()

    ok = main(
        force_check=args.force or args.check_only,
        quiet=args.quiet
    )

    if args.check_only:
        sys.exit(0 if ok else 1)
