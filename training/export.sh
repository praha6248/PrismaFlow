#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
OLLAMA="${OLLAMA:-$HOME/.local/ollama/bin/ollama}"
export OLLAMA_HOST="${OLLAMA_HOST:-100.89.78.124:11434}"
.venv/bin/python vendor/llama.cpp/convert_hf_to_gguf.py out/merged --outtype bf16 --outfile out/gemma3-4b-ux-bf16.gguf
vendor/llama.cpp/build/bin/llama-quantize out/gemma3-4b-ux-bf16.gguf out/gemma3-4b-ux-Q4_K_M.gguf Q4_K_M
"$OLLAMA" create local/gemma3-4b-ux -f Modelfile
"$OLLAMA" list | grep gemma3-4b-ux
