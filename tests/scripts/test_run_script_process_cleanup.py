from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_SCRIPT = REPO_ROOT / "scripts" / "run.sh"


def test_run_script_delegates_to_flocks_cli() -> None:
    script = RUN_SCRIPT.read_text(encoding="utf-8")

    assert 'exec flocks "$@"' in script
    assert 'exec uv run flocks "$@"' in script
