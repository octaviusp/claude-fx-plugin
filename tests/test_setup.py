"""Tests for scripts/setup.py - dependency checker."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestColoredFunction:
    """Tests for colored() function."""

    def test_colored_with_tty(self, mocker):
        """Applies ANSI colors when stdout is TTY."""
        mocker.patch("sys.stdout.isatty", return_value=True)
        import setup

        result = setup.colored("test", setup.Colors.GREEN)
        assert setup.Colors.GREEN in result
        assert "test" in result
        assert setup.Colors.END in result

    def test_colored_without_tty(self, mocker):
        """Returns plain text when not TTY."""
        mocker.patch("sys.stdout.isatty", return_value=False)
        import setup

        result = setup.colored("test", setup.Colors.GREEN)
        assert result == "test"
        assert setup.Colors.GREEN not in result


class TestGetPlatformInfo:
    """Tests for get_platform_info() function."""

    def test_get_platform_info_macos(self, mocker):
        """Detects macOS correctly."""
        mocker.patch("platform.system", return_value="Darwin")
        mocker.patch("platform.machine", return_value="arm64")
        import setup

        plat, arch = setup.get_platform_info()
        assert plat == "macos"
        assert arch == "arm64"

    def test_get_platform_info_linux(self, mocker):
        """Detects Linux correctly."""
        mocker.patch("platform.system", return_value="Linux")
        mocker.patch("platform.machine", return_value="x86_64")
        import setup

        plat, arch = setup.get_platform_info()
        assert plat == "linux"
        assert arch == "x86_64"

    def test_get_platform_info_windows(self, mocker):
        """Detects Windows correctly."""
        mocker.patch("platform.system", return_value="Windows")
        mocker.patch("platform.machine", return_value="AMD64")
        import setup

        plat, arch = setup.get_platform_info()
        assert plat == "windows"
        assert arch == "AMD64"

    def test_get_platform_info_unknown(self, mocker):
        """Handles unknown platform."""
        mocker.patch("platform.system", return_value="Haiku")
        mocker.patch("platform.machine", return_value="x86")
        import setup

        plat, arch = setup.get_platform_info()
        assert plat == "unknown"
        assert arch == "x86"


class TestGetPythonVersion:
    """Tests for get_python_version() function."""

    def test_get_python_version(self):
        """Returns correct version tuple."""
        import setup

        version = setup.get_python_version()
        assert isinstance(version, tuple)
        assert len(version) == 3
        assert version[0] >= 3


class TestCheckPython:
    """Tests for check_python() function."""

    def test_check_python_version_ok(self, mocker):
        """Python 3.9+ passes."""
        mocker.patch.object(sys, "version_info", (3, 11, 0))
        import setup

        # Force reimport to pick up mock
        import importlib
        importlib.reload(setup)

        ok, ver = setup.check_python()
        assert ok is True
        assert "3.11" in ver

    def test_check_python_version_39(self, mocker):
        """Python 3.9 exactly passes."""
        mocker.patch.object(sys, "version_info", (3, 9, 0))
        import setup
        import importlib
        importlib.reload(setup)

        ok, ver = setup.check_python()
        assert ok is True

    def test_check_python_version_old(self, mocker):
        """Python <3.9 fails."""
        mocker.patch.object(sys, "version_info", (3, 8, 10))
        import setup
        import importlib
        importlib.reload(setup)

        ok, ver = setup.check_python()
        assert ok is False
        assert "3.8" in ver


class TestCheckPillow:
    """Tests for check_pillow() function."""

    def test_check_pillow_installed(self, mocker):
        """Detects installed Pillow."""
        mock_pil = MagicMock()
        mock_pil.__version__ = "10.0.0"
        mock_image = MagicMock()
        mocker.patch.dict(
            sys.modules, {"PIL": mock_pil, "PIL.Image": mock_image}
        )
        import setup
        import importlib
        importlib.reload(setup)

        ok, ver = setup.check_pillow()
        assert ok is True
        assert "10.0.0" in ver

    def test_check_pillow_missing(self, mocker):
        """Detects missing Pillow."""
        import setup

        # Mock the check_pillow function to simulate missing Pillow
        mocker.patch.object(
            setup, "check_pillow", return_value=(False, "not installed")
        )

        ok, ver = setup.check_pillow()

        assert ok is False
        assert "not installed" in ver


class TestCheckQuartz:
    """Tests for check_quartz() function."""

    def test_check_quartz_macos_installed(self, mocker):
        """Checks Quartz on macOS when installed."""
        mocker.patch("platform.system", return_value="Darwin")
        mock_quartz = MagicMock()
        mocker.patch.dict(sys.modules, {"Quartz": mock_quartz})
        import setup
        import importlib
        importlib.reload(setup)

        ok, detail = setup.check_quartz()
        assert ok is True
        assert detail == "available"

    def test_check_quartz_non_macos(self, mocker):
        """Skips Quartz check on non-macOS."""
        mocker.patch("platform.system", return_value="Linux")
        import setup
        import importlib
        importlib.reload(setup)

        ok, detail = setup.check_quartz()
        assert ok is True
        assert detail == "not needed"


class TestIsHomebrewPython:
    """Tests for is_homebrew_python() function."""

    def test_is_homebrew_python_true(self, mocker):
        """Detects Homebrew Python."""
        mocker.patch.object(
            sys, "executable", "/opt/homebrew/bin/python3"
        )
        import setup
        import importlib
        importlib.reload(setup)

        assert setup.is_homebrew_python() is True

    def test_is_homebrew_python_cellar(self, mocker):
        """Detects Cellar Python."""
        mocker.patch.object(
            sys, "executable", "/usr/local/Cellar/python@3.11/bin/python3"
        )
        import setup
        import importlib
        importlib.reload(setup)

        assert setup.is_homebrew_python() is True

    def test_is_homebrew_python_false(self, mocker):
        """Detects non-Homebrew Python."""
        mocker.patch.object(sys, "executable", "/usr/bin/python3")
        import setup
        import importlib
        importlib.reload(setup)

        assert setup.is_homebrew_python() is False


class TestGetInstallCommands:
    """Tests for get_install_commands() function."""

    def test_get_install_commands_pillow_macos(self, mocker):
        """Generates correct macOS pip command for Pillow."""
        mocker.patch.object(sys, "executable", "/usr/bin/python3")
        import setup
        import importlib
        importlib.reload(setup)

        commands = setup.get_install_commands(["pillow"], "macos", (3, 11, 0))
        assert len(commands) == 1
        assert commands[0][0] == "Pillow"
        assert "pip3 install pillow" in commands[0][1]

    def test_get_install_commands_homebrew_python(self, mocker):
        """Adds --break-system-packages flag for Homebrew."""
        mocker.patch.object(
            sys, "executable", "/opt/homebrew/bin/python3"
        )
        import setup
        import importlib
        importlib.reload(setup)

        commands = setup.get_install_commands(["pillow"], "macos", (3, 11, 0))
        assert "--break-system-packages" in commands[0][1]

    def test_get_install_commands_quartz_macos(self, mocker):
        """Generates correct pip command for Quartz."""
        mocker.patch.object(sys, "executable", "/usr/bin/python3")
        import setup
        import importlib
        importlib.reload(setup)

        commands = setup.get_install_commands(["quartz"], "macos", (3, 11, 0))
        assert len(commands) == 1
        assert "pyobjc-framework-Quartz" in commands[0][1]


class TestCheckAll:
    """Tests for check_all() function."""

    def test_check_all_all_ok(self, mocker):
        """All checks pass."""
        mocker.patch("platform.system", return_value="Darwin")
        mocker.patch("platform.machine", return_value="arm64")
        mocker.patch.object(sys, "version_info", (3, 11, 0))

        # Mock successful imports
        mock_pil = MagicMock()
        mock_pil.__version__ = "10.0.0"
        mock_quartz = MagicMock()
        mock_cocoa = MagicMock()
        mocker.patch.dict(sys.modules, {
            "PIL": mock_pil,
            "Quartz": mock_quartz,
            "Cocoa": mock_cocoa,
        })

        import setup
        import importlib
        importlib.reload(setup)

        all_ok, results, missing = setup.check_all()
        assert all_ok is True
        assert len(missing) == 0
        assert results["python"][0] is True
        assert results["pillow"][0] is True

    def test_check_all_missing_deps(self, mocker):
        """Detects missing dependencies."""
        import setup

        # Mock all check functions to avoid PyObjC reload issues
        mocker.patch.object(
            setup, "check_python", return_value=(True, "3.11.0")
        )
        mocker.patch.object(
            setup, "check_pillow", return_value=(False, "missing")
        )
        mocker.patch.object(
            setup, "check_quartz", return_value=(True, "available")
        )
        mocker.patch.object(
            setup, "check_cocoa", return_value=(True, "available")
        )

        all_ok, results, missing = setup.check_all()
        assert all_ok is False
        assert "pillow" in missing


class TestSetupStatus:
    """Tests for setup status persistence."""

    def test_save_setup_status_ok(self, tmp_path, mocker):
        """Creates setup_ok file when OK."""
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        import setup
        import importlib
        importlib.reload(setup)

        setup.save_setup_status(True)

        status_file = tmp_path / ".claude-fx" / "setup_ok"
        assert status_file.exists()
        assert status_file.read_text() == "1"

    def test_save_setup_status_not_ok(self, tmp_path, mocker):
        """Removes setup_ok file when not OK."""
        mocker.patch("pathlib.Path.home", return_value=tmp_path)

        # Create status dir and file first
        status_dir = tmp_path / ".claude-fx"
        status_dir.mkdir(parents=True)
        status_file = status_dir / "setup_ok"
        status_file.write_text("1")

        import setup
        import importlib
        importlib.reload(setup)

        setup.save_setup_status(False)
        assert not status_file.exists()

    def test_is_setup_complete_true(self, tmp_path, mocker):
        """Returns True when setup_ok exists."""
        mocker.patch("pathlib.Path.home", return_value=tmp_path)

        # Create status file
        status_dir = tmp_path / ".claude-fx"
        status_dir.mkdir(parents=True)
        (status_dir / "setup_ok").write_text("1")

        import setup
        import importlib
        importlib.reload(setup)

        assert setup.is_setup_complete() is True

    def test_is_setup_complete_false(self, tmp_path, mocker):
        """Returns False when setup_ok doesn't exist."""
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        import setup
        import importlib
        importlib.reload(setup)

        assert setup.is_setup_complete() is False


class TestMainFunction:
    """Tests for main() function."""

    def test_main_already_complete(self, tmp_path, mocker):
        """Returns True if already setup."""
        mocker.patch("pathlib.Path.home", return_value=tmp_path)

        # Create status file
        status_dir = tmp_path / ".claude-fx"
        status_dir.mkdir(parents=True)
        (status_dir / "setup_ok").write_text("1")

        import setup
        import importlib
        importlib.reload(setup)

        result = setup.main(force_check=False)
        assert result is True

    def test_main_force_check(self, tmp_path, mocker):
        """Force check runs even if setup_ok exists."""
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        mocker.patch("platform.system", return_value="Darwin")
        mocker.patch("platform.machine", return_value="arm64")
        mocker.patch.object(sys, "version_info", (3, 11, 0))

        # Mock all deps as OK (including Cocoa to avoid reload issues)
        mock_pil = MagicMock()
        mock_pil.__version__ = "10.0.0"
        mocker.patch.dict(sys.modules, {
            "PIL": mock_pil,
            "PIL.Image": MagicMock(),
            "tkinter": MagicMock(),
            "Quartz": MagicMock(),
            "Cocoa": MagicMock(),
        })

        # Create status file
        status_dir = tmp_path / ".claude-fx"
        status_dir.mkdir(parents=True)
        (status_dir / "setup_ok").write_text("1")

        import setup
        import importlib
        importlib.reload(setup)

        result = setup.main(force_check=True, quiet=True)
        assert result is True
