#!/bin/bash

# Ensure model directory exists
mkdir -p model

# URL for Qwen1.5-1.8B-Chat-Q4_K_M GGUF
MODEL_URL="https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q4_k_m.gguf?download=true"
MODEL_PATH="model/qwen1_5-1_8b-chat-q4_k_m.gguf"

if [ ! -f "$MODEL_PATH" ]; then
  echo "Downloading model weights (~1.1 GB)..."
  # Using wget or curl based on availability
  if command -v curl &> /dev/null; then
    curl -L "$MODEL_URL" -o "$MODEL_PATH"
  elif command -v wget &> /dev/null; then
    wget -O "$MODEL_PATH" "$MODEL_URL"
  else
    echo "Error: Neither curl nor wget is installed."
    exit 1
  fi
  echo "Download complete: $MODEL_PATH"
else
  echo "Model already exists at $MODEL_PATH. Skipping download."
fi
