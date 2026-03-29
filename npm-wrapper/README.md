# @flocks-ai/flocks

npm wrapper for [Flocks](https://github.com/flocks-ai/flocks) — AI-Native SecOps platform.

Flocks is a Python package. This wrapper detects `uvx`, `pipx`, or a globally installed `flocks` binary and delegates to it.

## Quick start

```bash
# Zero-install (requires uv or pipx)
npx @flocks-ai/flocks

# Install skill from clawhub
npx @flocks-ai/flocks skill install clawhub:github

# Install skill from GitHub
npx @flocks-ai/flocks skill install github:owner/repo
```

## Prerequisites

Install `uv` (recommended):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or install Flocks directly:

```bash
uv tool install flocks    # recommended
pipx install flocks       # alternative
```

## Skill registry

Skills can be installed from:

| Source | Example |
|--------|---------|
| clawhub.com | `flocks skill install clawhub:github` |
| GitHub URL | `flocks skill install github:owner/repo` |
| Direct URL | `flocks skill install https://...` |
| Local path | `flocks skill install ./my-skill` |
| SafeSkill (future) | `flocks skill install safeskill:ioc-lookup` |
