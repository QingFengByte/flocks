from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"


def test_runtime_image_installs_required_cli_tools() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "npm install --global agent-browser" in dockerfile
    assert "agent-browser install --with-deps" in dockerfile
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in dockerfile


def test_runtime_image_no_longer_bundles_system_chromium() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium" not in dockerfile
    assert "    chromium \\" not in dockerfile
