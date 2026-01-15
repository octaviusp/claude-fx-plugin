#!/usr/bin/env python3
"""
Claude FX Plugin - Setup & Requirements Checker

Checks all dependencies and provides helpful guidance for installation.
Can be run standalone or called from hook-handler.py on SessionStart.
"""

import os
import sys
import platform
import subprocess
import shutil
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
    """Print plugin header."""
    print()
    print(colored("=" * 55, Colors.CYAN))
    print(colored("  Claude FX Plugin - Setup Check", Colors.BOLD))
    print(colored("=" * 55, Colors.CYAN))
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
        from PIL import Image
        import PIL
        version = PIL.__version__
        return True, version
    except ImportError:
        return False, "not installed"


def check_tkinter():
    """Check if tkinter is available."""
    try:
        import tkinter
        return True, "available"
    except ImportError:
        return False, "not installed"


def check_quartz():
    """Check if Quartz (pyobjc) is available - macOS only."""
    plat, _ = get_platform_info()
    if plat != 'macos':
        return True, "not needed"

    try:
        from Quartz import CGWindowListCopyWindowInfo
        return True, "available"
    except ImportError:
        return False, "not installed"


def is_homebrew_python():
    """Check if running Homebrew-managed Python."""
    exe = sys.executable.lower()
    return 'homebrew' in exe or 'cellar' in exe


def get_install_commands(missing, plat, python_version):
    """Get platform-specific install commands for missing deps."""
    commands = []
    version_suffix = f"{python_version[0]}.{python_version[1]}"

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

    if 'tkinter' in missing:
        if plat == 'macos':
            if shutil.which('brew'):
                commands.append((
                    "tkinter",
                    f"brew install python-tk@{version_suffix}"
                ))
            else:
                commands.append((
                    "tkinter",
                    "Install Homebrew first: https://brew.sh"
                ))
        elif plat == 'linux':
            if shutil.which('apt'):
                commands.append(("tkinter", "sudo apt install python3-tk"))
            elif shutil.which('dnf'):
                commands.append(
                    ("tkinter", "sudo dnf install python3-tkinter")
                )
            elif shutil.which('pacman'):
                commands.append(("tkinter", "sudo pacman -S tk"))
            else:
                commands.append((
                    "tkinter",
                    "Install python3-tk using your package manager"
                ))

    if 'quartz' in missing and plat == 'macos':
        cmd = f"pip3 install pyobjc-framework-Quartz{pip_flags}"
        commands.append(("Quartz", cmd))

    return commands


def run_install(commands):
    """Run installation commands."""
    print()
    print(colored("Installing dependencies...", Colors.YELLOW))
    print()

    success = True
    for name, cmd in commands:
        print(f"  Installing {name}...")
        print(f"    $ {cmd}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(colored(f"    ✓ {name} installed", Colors.GREEN))
            else:
                print(colored(f"    ✗ Failed to install {name}", Colors.RED))
                if result.stderr:
                    err_lines = result.stderr.strip().split('\n')
                    print(f"      Error: {err_lines[-1][:60]}")
                success = False
        except Exception as e:
            print(colored(f"    ✗ Error: {e}", Colors.RED))
            success = False
        print()

    return success


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

    ok, detail = check_tkinter()
    results['tkinter'] = (ok, detail)
    if not ok:
        missing.append('tkinter')

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
    print_status("tkinter", results['tkinter'][0], results['tkinter'][1])

    plat, _ = get_platform_info()
    if plat == 'macos':
        print_status("Quartz", results['quartz'][0], results['quartz'][1])

    print()


def print_install_instructions(missing, commands):
    """Print installation instructions."""
    if not missing:
        return

    # Describe what each dependency does
    dep_desc = {
        'python': 'Core runtime',
        'pillow': 'Image/GIF processing',
        'tkinter': 'GUI overlay window',
        'quartz': 'Terminal position detection (macOS)',
    }

    print(colored("  Missing dependencies:", Colors.YELLOW))
    for m in missing:
        desc = dep_desc.get(m, '')
        if desc:
            print(f"    - {m}: {desc}")
        else:
            print(f"    - {m}")
    print()

    print(colored("  To fix, run these commands:", Colors.BOLD))
    print()
    for name, cmd in commands:
        print(f"    {colored('$', Colors.CYAN)} {cmd}")
    print()

    restart = colored('restart Claude Code', Colors.YELLOW)
    print(f"  After installing, {restart} to activate the plugin.")
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


def main(force_check=False, auto_install=False, quiet=False):
    """
    Main setup function.

    Args:
        force_check: Run checks even if setup was already complete
        auto_install: Automatically install missing deps without asking
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

    if auto_install:
        run_install(commands)
        all_ok, _, _ = check_all()
        save_setup_status(all_ok)
        return all_ok

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
        '--install', '-i',
        action='store_true',
        help='Automatically install missing dependencies'
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
        auto_install=args.install,
        quiet=args.quiet
    )

    if args.check_only:
        sys.exit(0 if ok else 1)
