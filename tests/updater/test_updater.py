import shutil
import subprocess
from pathlib import Path

import pytest

from flocks.updater import updater


def test_run_handles_none_process_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=None, stderr=None)

    monkeypatch.setattr(updater.subprocess, "run", fake_run)

    code, stdout, stderr = updater._run(["npm", "run", "build"], cwd=tmp_path)

    assert code == 0
    assert stdout == ""
    assert stderr == ""


@pytest.mark.asyncio
async def test_run_async_handles_none_process_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=None, stderr=None)

    monkeypatch.setattr(updater.subprocess, "run", fake_run)

    code, stdout, stderr = await updater._run_async(["npm", "run", "build"], cwd=tmp_path)

    assert code == 0
    assert stdout == ""
    assert stderr == ""


def test_find_executable_checks_windows_scripts_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scripts_dir = tmp_path / ".venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    uv_cmd = scripts_dir / "uv.cmd"
    uv_cmd.write_text("", encoding="utf-8")

    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(updater, "_get_repo_root", lambda: tmp_path)

    assert updater._find_executable("uv.cmd") == str(uv_cmd)
