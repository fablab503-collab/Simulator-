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

# llama.cpp: its newest ready-made Linux build (GitHub's runners have gh),
# or built from source if there is none.
cli="$(find "$LLAMA_DIR" -name llama-mtmd-cli -type f 2>/dev/null | head -1 || true)"
if [[ -z "$cli" ]]; then
  mkdir -p "$LLAMA_DIR"
  assets="$(gh release view -R ggml-org/llama.cpp --json assets -q '.assets[].name')"
  # The plain processor build: not the CUDA/Vulkan/ROCm/SYCL/ARM ones.
  asset="$(echo "$assets" | grep -Ei '(ubuntu|linux).*x64.*\.(zip|tar\.gz)$' \
    | grep -Eiv 'cuda|vulkan|rocm|hip|sycl|openvino|kompute|arm|aarch64|s390' | head -1 || true)"
  if [[ -n "$asset" ]]; then
    echo "Using llama.cpp $asset" >&2
    gh release download -R ggml-org/llama.cpp --pattern "$asset" -D "$LLAMA_DIR" --clobber
    case "$asset" in
      *.zip) unzip -o -q "$LLAMA_DIR/$asset" -d "$LLAMA_DIR" ;;
      *) tar xzf "$LLAMA_DIR/$asset" -C "$LLAMA_DIR" ;;
    esac
  else
    echo "No ready-made llama.cpp for Linux among: $(echo "$assets" | tr '\n' ' ')" >&2
    echo "Building llama.cpp from source (about 5 minutes)" >&2
    git clone -q --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMA_DIR/src"
    cmake -S "$LLAMA_DIR/src" -B "$LLAMA_DIR/src/build" -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF >&2
    cmake --build "$LLAMA_DIR/src/build" -j "$(nproc)" --target llama-mtmd-cli >&2
  fi
  cli="$(find "$LLAMA_DIR" -name llama-mtmd-cli -type f | head -1)"
fi
export LD_LIBRARY_PATH="$(dirname "$cli")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

echo "Asking $MODEL ($(basename "$brain"))..." >&2
"$cli" -m "$brain" --mmproj "$eyes" --image "$PICTURE" -p "$QUESTION" \
  -n 200 --temp 0 -c 8192 2>"$MODELS_DIR/$MODEL/last-run.log"
