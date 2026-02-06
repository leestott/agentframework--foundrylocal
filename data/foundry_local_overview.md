# What Is Foundry Local?

Foundry Local is a lightweight runtime from Microsoft that lets developers run
AI models directly on their own machine — no cloud connection required after the
initial model download.

## Key Features

- **On-device inference**: Models run locally, keeping data private.
- **OpenAI-compatible API**: Use the same `openai` Python SDK you already know;
  just point it at `http://localhost:5272/v1`.
- **Automatic hardware detection**: When you request a model by alias (e.g.
  `qwen2.5`), Foundry Local automatically selects the best variant for your
  GPU, NPU, or CPU.
- **Model management**: Download, load, unload, and cache models through the
  CLI (`foundry model run <alias>`) or the Python SDK (`foundry-local-sdk`).

## Getting Started

1. Install Foundry Local from <https://github.com/microsoft/Foundry-Local>.
2. Verify: `foundry --help`
3. Run a model: `foundry model run qwen2.5`
4. Use the Python SDK:

```python
from foundry_local import FoundryLocalManager

# Pass a model alias — Foundry Local resolves it to the best variant
# for your hardware (e.g. qwen2.5-0.5b → qwen2.5-0.5b-instruct-cuda-gpu:4 on a CUDA GPU)
manager = FoundryLocalManager("qwen2.5-0.5b")
print(manager.endpoint)   # e.g. http://localhost:65026/v1 (port is dynamic)
print(manager.api_key)    # local-only — no real key needed
```

## Supported Models

Foundry Local maintains a growing catalog of optimized models including
Phi-3.5, Qwen 2.5 series, and more.  Run `foundry model list` to see the
full catalog on your machine.

## References

- Website: https://foundrylocal.ai
- GitHub: https://github.com/microsoft/Foundry-Local
- SDK reference: https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-sdk
