#!/usr/bin/env bash
# Shows a screenshot to one of Gimmich's AI models and prints its answer.
# This is how the orchestrator asks "what is on this screen / what should I
# click?". Runs the compressed model with llama.cpp, on the computer's
# processor (no graphics card needed, just slower).
#
# Usage: ask-model.sh <model|system> <picture.png> "<question>"
#   <model>  a name from models/models.toml (e.g. qwen3-vl-4b), or a system
#            (android, windows, mac, linux, games, web) to use its default
# Settings: MODELS_DIR (where models are kept, default ~/gimmich-models),
#           LLAMA_DIR (where llama.cpp is kept, default ~/.cache/gimmich/llama).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MODEL="$1"
PICTURE="$2"
QUESTION="$3"
MODELS_DIR="${MODELS_DIR:-$HOME/gimmich-models}"
LLAMA_DIR="${LLAMA_DIR:-$HOME/.cache/gimmich/llama}"

# A system name means "that system's default model".
case "$MODEL" in
  android|windows|mac|linux|games|web|any) MODEL="$(python3 "$HERE/get-model.py" pick "$MODEL")" ;;
esac

python3 "$HERE/get-model.py" get "$MODEL" --dest "$MODELS_DIR" >&2
brain="$(find "$MODELS_DIR/$MODEL" -name '*.gguf' ! -iname '*mmproj*' | head -1)"
eyes="$(find "$MODELS_DIR/$MODEL" -iname '*mmproj*.gguf' | head -1)"
[[ -n "$brain" && -n "$eyes" ]] || { echo "$MODEL has no compressed copy to run here (it needs a GPU)" >&2; exit 2; }

# llama.cpp's newest ready-made build for Linux (GitHub's runners have gh).
cli="$(find "$LLAMA_DIR" -name llama-mtmd-cli -type f 2>/dev/null | head -1 || true)"
if [[ -z "$cli" ]]; then
  mkdir -p "$LLAMA_DIR"
  gh release download -R ggml-org/llama.cpp --pattern '*bin-ubuntu-x64.*' -D "$LLAMA_DIR" --clobber
  for f in "$LLAMA_DIR"/*bin-ubuntu-x64.*; do
    case "$f" in *.zip) unzip -o -q "$f" -d "$LLAMA_DIR" ;; *.tar.gz) tar xzf "$f" -C "$LLAMA_DIR" ;; esac
  done
  cli="$(find "$LLAMA_DIR" -name llama-mtmd-cli -type f | head -1)"
fi
export LD_LIBRARY_PATH="$(dirname "$cli")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

echo "Asking $MODEL ($(basename "$brain"))..." >&2
"$cli" -m "$brain" --mmproj "$eyes" --image "$PICTURE" -p "$QUESTION" \
  -n 200 --temp 0 -c 8192 2>"$MODELS_DIR/$MODEL/last-run.log"
