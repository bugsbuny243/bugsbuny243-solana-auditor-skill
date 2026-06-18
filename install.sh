#!/bin/bash
# solana-auditor-skill installer
# Installs into .claude/skills/ for Solana AI Kit / Claude Code

set -e

SKILL_DIR=".claude/skills/solana-auditor-skill"
REPO="https://github.com/bugsbuny243/solana-auditor-skill"

echo "Installing solana-auditor-skill..."

if [ -d "$SKILL_DIR" ]; then
  echo "Updating existing installation..."
  cd "$SKILL_DIR" && git pull && cd -
else
  mkdir -p .claude/skills
  git clone "$REPO" "$SKILL_DIR"
fi

echo "✅ solana-auditor-skill installed at $SKILL_DIR"
echo "Usage: /skill solana-auditor-skill"
