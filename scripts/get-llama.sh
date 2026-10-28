#!/usr/bin/env bash
# Gets llama.cpp (the program that runs Gimmich's compressed AI models) and
# prints the folder holding its programs (llama-mtmd-cli, llama-server).
# Uses the newest ready-made Linux build (GitHub's runners have gh), or
# builds it from source if there is none.
#
# Usage: dir="$(get-llama.sh)"      Setting: LLAMA_DIR (default ~/.cache/gimmich/llama)
set -euo pipefail

LLAMA_DIR="${LLAMA_DIR:-$HOME/.cache/gimmich/llama}"
have() { find "$LLAMA_DIR" -name llama-server -type f 2>/dev/null | head -1; }

if [[ -z "$(have)" ]]; then
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
    cmake --build "$LLAMA_DIR/src/build" -j "$(nproc)" --target llama-mtmd-cli llama-server >&2
  fi
fi
dirname "$(have)"
