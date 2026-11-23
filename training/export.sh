#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
NAME="${1:-gemma3-4b-ux}"
DIR="${2:-out}"
OLLAMA="${OLLAMA:-$HOME/.local/ollama/bin/ollama}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
.venv/bin/python vendor/llama.cpp/convert_hf_to_gguf.py "$DIR/merged" --outtype bf16 --outfile "$DIR/$NAME-bf16.gguf"
vendor/llama.cpp/build/bin/llama-quantize "$DIR/$NAME-bf16.gguf" "$DIR/$NAME-Q4_K_M.gguf" Q4_K_M
rm -f "$DIR/$NAME-bf16.gguf"
sed "s|^FROM .*|FROM $PWD/$DIR/$NAME-Q4_K_M.gguf|" Modelfile > "$DIR/$NAME.Modelfile"
"$OLLAMA" create "local/$NAME" -f "$DIR/$NAME.Modelfile"
"$OLLAMA" list | grep "local/$NAME"
