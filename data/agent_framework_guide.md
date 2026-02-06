# Microsoft Agent Framework (MAF) — Quick Reference

The Microsoft Agent Framework is a unified SDK for building, orchestrating,
and deploying AI agents in Python and .NET.

## Core Concepts

### ChatAgent
A ChatAgent wraps a chat-completion client with persistent instructions,
optional tools, and session management.

```python
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient

# Connect to Foundry Local's OpenAI-compatible endpoint
client = OpenAIChatClient(
    base_url="http://localhost:65026/v1",  # from FoundryLocalManager.endpoint
    api_key="local",                        # from FoundryLocalManager.api_key
    model_id="qwen2.5-0.5b-instruct-cuda-gpu:4",
)

agent = ChatAgent(
    chat_client=client,
    name="HelperBot",
    instructions="You are a helpful assistant.",
)
result = await agent.run("Hello!")
```

### Orchestration Patterns

MAF supports five orchestration patterns out of the box:

| Pattern      | Topology      | Use-case                                  |
|------------- |-------------- |------------------------------------------ |
| Sequential   | Pipeline      | Step-by-step processing                   |
| Concurrent   | Fan-out       | Independent parallel tasks                |
| Group Chat   | Star (manager)| Iterative collaborative refinement        |
| Handoff      | Mesh          | Dynamic routing between agents            |
| Magentic     | Planner-based | Complex generalist collaboration          |

### Tool Calling
Agents can call Python functions annotated with Pydantic `Field` metadata:

```python
from typing import Annotated
from pydantic import Field

def get_weather(
    location: Annotated[str, Field(description="City name")],
) -> str:
    return "Sunny, 22 °C"

agent = ChatAgent(
    chat_client=OpenAIChatClient(),
    tools=[get_weather],
)
```

## Installation

```bash
pip install agent-framework-core --pre
```

## References

- GitHub: https://github.com/microsoft/agent-framework
- PyPI: https://pypi.org/project/agent-framework-core/
- Docs: https://learn.microsoft.com/en-us/agent-framework/
- Orchestration overview: https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/overview
