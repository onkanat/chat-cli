# Fine-tuning on an 8GB Mac (Apple Silicon or Intel)

This guide walks you through preparing data, training a small instruct model with LoRA on a low-memory Mac, and creating an Ollama model.

The scripts live under `tools/` and are designed to be minimal and robust. Training defaults favor stability on 8GB RAM.

## Prerequisites

- Python 3.10+ (existing project venv is fine; consider a separate venv for training)
- macOS with 8 GB RAM (MPS works if Apple Silicon)
- Enough disk space for models and checkpoints (a few GB)

## 1) Install training-only dependencies

These are kept separate to avoid bloating your main environment.

```bash
# (Optional) Use a fresh venv for training
python -m venv .venv-train
source .venv-train/bin/activate

# Install minimal training deps
pip install -r tools/requirements-finetune.txt
```

Notes:

- We intentionally avoid `bitsandbytes` since it does not support macOS MPS.
- Training runs in float16/bfloat16 as available; use very small batch sizes.

## 2) Prepare your dataset (Alpaca format)

Use the existing utility to convert your chat histories into a clean Alpaca dataset. Examples:

```bash
# Convert a single history JSON into Alpaca format with a small train/val split
python tools/prepare_finetune_data.py \
  --inputs chat_history.json \
  --format alpaca \
  --output training_data/my_alpaca.json \
  --val_split 0.1

# Or, aggregate all sessions under histories/
python tools/prepare_finetune_data.py \
  --inputs histories \
  --format alpaca \
  --output training_data/all_alpaca.json \
  --val_split 0.05
```

Validate a few records to ensure fields `instruction`, `input`, `output` look correct.

## 3) Run fine-tuning (LoRA, Unsloth/TRL)

Run with a small model. Qwen2.5 1.5B Instruct is a good starting point on 8GB.

```bash
python tools/finetune_unsloth.py \
  --dataset training_data/my_alpaca.json \
  --output_dir runs/qwen2.5-1.5b-lora \
  --base_model unsloth/qwen2.5-1.5b-instruct \
  --seq_len 1024 \
  --micro_batch_size 1 \
  --grad_accum 8 \
  --epochs 1 \
  --fp16
```

Tips:

- If you see out-of-memory, reduce `--seq_len` to 512 and increase `--grad_accum`.
- `--bf16` is fine if supported; otherwise use `--fp16` (recommended for MPS).
- Gemma-2 2B IT can work with conservative settings but is heavier than Qwen 1.5B.

Outputs are saved to `--output_dir` as a PEFT LoRA adapter + tokenizer.

## 4) Try the adapter in Python (optional)

If you want to test the adapter without Ollama first:

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

base = "unsloth/qwen2.5-1.5b-instruct"
adapter_dir = "runs/qwen2.5-1.5b-lora"

model = AutoModelForCausalLM.from_pretrained(base)
model = PeftModel.from_pretrained(model, adapter_dir)
tokenizer = AutoTokenizer.from_pretrained(base)

prompt = "### Talimat:\nMerhaba de.\n\n### Yanıt:\n"
inputs = tokenizer(prompt, return_tensors="pt")
out = model.generate(**inputs, max_new_tokens=64)
print(tokenizer.decode(out[0], skip_special_tokens=True))
 

## 5) Create an Ollama model

Ollama currently consumes GGUF models and supports llama.cpp-compatible LoRA adapters.
PEFT adapters saved by this project are not directly consumable by Ollama.

Still, you can generate a Modelfile with your desired defaults and system prompt:

```bash
python tools/export_to_ollama.py \
  --base gemma3:1b-it-qat \
  --out_dir exports/gemma3-1b-it-qat-lora \
  --tag my/gemma3-1b-it-qat-finetune:latest \
  --system "Kısa ve net yanıt ver."

# Build the model
ollama create -f exports/gemma3-1b-it-qat-lora/Modelfile my/gemma3-1b-it-qat-finetune:latest

# Run it
ollama run my/gemma3-1b-it-qat-finetune:latest
```

If you have converted your PEFT adapter to a llama.cpp-compatible LoRA, pass `--adapter /path/to/adapter.gguf`
and the tool will add an `ADAPTER` line to the Modelfile.

## Troubleshooting

- Out of memory: lower `--seq_len` and raise `--grad_accum`. Keep `--micro_batch_size` at 1.
- Slow training on CPU: consider using Apple Silicon with `--fp16` for MPS acceleration.
- Validation set: either pass `--val_dataset` or `--eval_fraction 0.05` to sample a small eval split.

## Next steps

- Automate PEFT -> llama.cpp LoRA conversion and GGUF export.
- Add ready-made presets for popular small models.
