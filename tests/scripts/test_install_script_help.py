import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts"


def test_bash_install_help_mentions_optional_tui() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT_DIR / "install.sh"), "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "--with-tui" in output
    assert "bun" in output


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh is required to inspect PowerShell help output")
def test_powershell_install_help_mentions_optional_tui() -> None:
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(SCRIPT_DIR / "install.ps1"), "-Help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "-InstallTui" in output
    assert "bun" in output
