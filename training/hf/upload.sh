#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
REPO="${1:?usage: ./upload.sh <hf-user>/<repo-name>}"
NAME=gemma3-4b-ux
HF="${HF:-../.venv/bin/hf}"
GGUF="$(ls ../out/$NAME-Q4_K_M.gguf ../out/*/$NAME-Q4_K_M.gguf 2>/dev/null | head -1)"
[ -n "$GGUF" ] || { echo "no $NAME-Q4_K_M.gguf under training/out; run ../export.sh first" >&2; exit 1; }
"$HF" auth whoami >/dev/null || { echo "log in first: $HF auth login" >&2; exit 1; }
sed "s|<REPO>|$REPO|g" README.md > /tmp/prismflow-hf-README.md
"$HF" repos create "$REPO" --repo-type model --exist-ok
"$HF" upload "$REPO" /tmp/prismflow-hf-README.md README.md --commit-message "Add model card"
"$HF" upload "$REPO" Modelfile Modelfile --commit-message "Add Ollama Modelfile"
"$HF" upload "$REPO" NOTICE NOTICE --commit-message "Add Gemma notice"
"$HF" upload "$REPO" "$GGUF" "$NAME-Q4_K_M.gguf" --commit-message "Add Q4_K_M GGUF"
echo "https://huggingface.co/$REPO"
