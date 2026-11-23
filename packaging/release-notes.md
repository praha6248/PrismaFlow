## Install

| System | Download | One command |
| --- | --- | --- |
| Windows 10/11 (x64) | `PrismaFlow-*-windows-x64-setup.exe` | `irm https://raw.githubusercontent.com/praha6248/PrismaFlow/main/install.ps1 \| iex` |
| Linux (x86_64, glibc 2.39+) | `PrismaFlow-*-x86_64.AppImage` or `PrismaFlow-linux-x86_64.tar.gz` | `curl -fsSL https://raw.githubusercontent.com/praha6248/PrismaFlow/main/install.sh \| sh` |

On Linux the window needs WebKit2GTK: `sudo apt install gir1.2-webkit2-4.1 python3-gi`. The AppImage also
needs FUSE 2 (`sudo apt install libfuse2t64`); the one-command installer uses the tarball and does not.

## Models

PrismaFlow generates text with a local model in [Ollama](https://ollama.com/download), so your data stays on
your machine. On first launch the app checks Ollama and shows the commands for anything missing.

| Model | Size | Needed for | Command |
| --- | --- | --- | --- |
| [Gemma 3 12B](https://ollama.com/library/gemma3) | 8.1 GB | everything, 16 GB RAM or more | `ollama pull gemma3:12b` |
| [Gemma 3 4B](https://ollama.com/library/gemma3) | 3.3 GB | everything, less than 16 GB RAM | `ollama pull gemma3:4b` |
| [BGE-M3](https://ollama.com/library/bge-m3) | 1.2 GB | optional, semantic evidence search | `ollama pull bge-m3` |
UX_MODEL_ROW

Without local models you can switch on the quality mode with your own Claude API key. Prompts, including the
collected discussions, are then sent to Anthropic.
