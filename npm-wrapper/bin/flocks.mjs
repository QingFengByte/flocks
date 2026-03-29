#!/usr/bin/env node
/**
 * Flocks npm wrapper
 *
 * Flocks is a Python package. This thin wrapper detects available Python
 * launchers and delegates to the real `flocks` CLI.
 *
 * Install preference order:
 *   1. uvx flocks     — uv is the recommended Python launcher
 *   2. pipx run flocks — pipx fallback
 *   3. flocks         — globally installed via pip
 *
 * Usage:
 *   npx @flocks-ai/flocks [command] [options]
 *   npx @flocks-ai/flocks skill install clawhub:github
 */

import { spawnSync, execFileSync } from "node:child_process"
import { existsSync } from "node:fs"

const args = process.argv.slice(2)

function hasCommand(cmd) {
  try {
    execFileSync(cmd, ["--version"], { stdio: "ignore" })
    return true
  } catch {
    return false
  }
}

function run(launcher, launcherArgs) {
  const result = spawnSync(launcher, [...launcherArgs, ...args], {
    stdio: "inherit",
    shell: false,
  })
  process.exit(result.status ?? 1)
}

// 1. Try uvx (uv's tool runner — zero-install, like npx but for Python)
if (hasCommand("uvx")) {
  run("uvx", ["flocks"])
}

// 2. Try pipx run
if (hasCommand("pipx")) {
  run("pipx", ["run", "flocks"])
}

// 3. Try globally installed flocks binary
if (hasCommand("flocks")) {
  run("flocks", [])
}

// 4. Nothing found — guide the user
console.error(`
  Error: Flocks requires Python (uv or pipx).

  Quick install options:
    • Install uv (recommended):
        curl -LsSf https://astral.sh/uv/install.sh | sh
      Then retry: npx @flocks-ai/flocks

    • Or install directly:
        uv tool install flocks
        pipx install flocks

  See: https://github.com/flocks-ai/flocks
`)
process.exit(1)
