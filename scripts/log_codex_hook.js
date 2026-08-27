#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const input = fs.readFileSync(0);
const repoRoot = path.resolve(__dirname, "..");
const logger = path.join(__dirname, "log_hook.py");
const candidates = process.platform === "win32"
  ? [
      ["py", ["-3"]],
      ["python", []],
      ["python3", []],
    ]
  : [
      ["python3", []],
      ["python", []],
      ["py", ["-3"]],
    ];

for (const [command, prefixArgs] of candidates) {
  const result = spawnSync(
    command,
    [...prefixArgs, logger, "--tool=codex"],
    {
      cwd: repoRoot,
      env: process.env,
      input,
      encoding: "utf8",
      windowsHide: true,
    },
  );

  if (result.error?.code === "ENOENT") continue;
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  process.exit(result.status ?? 1);
}

// Logging must never block Codex when Python is unavailable.
process.exit(0);
