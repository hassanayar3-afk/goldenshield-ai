#!/data/data/com.termux/files/usr/bin/bash
# يُستدعى مرة واحدة من Termux على الهاتف (Widget / Tasker / sshd) — يثبت ويشغّل دون Windows
set -euo pipefail
export GOLDENSHIELD_OFFICIAL_ROOT="${GOLDENSHIELD_OFFICIAL_ROOT:-$HOME/goldenshield-ai}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"
bash "$SCRIPT_DIR/INSTALL_TERMUX.sh"
bash "$SCRIPT_DIR/START_FULL_STACK.sh"
bash "$SCRIPT_DIR/CHECK_API.sh"
