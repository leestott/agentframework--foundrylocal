# Building Multi-Agent AI Applications with Foundry Local and Microsoft Agent Framework

**A hands-on guide to orchestrating AI agents entirely on your local machine**

---

## Introduction

What if you could run a team of AI agents—planning, researching, critiquing, and writing—entirely on your laptop? No cloud API keys. No per-token billing. No data leaving your machine.

This demo shows you exactly how to do that using two powerful tools from Microsoft:

- **Foundry Local**: An on-device inference runtime that runs models like Qwen, Phi, and Llama locally
- **Microsoft Agent Framework (MAF)**: A Python library for building and orchestrating AI agents

The result is a "Local Research & Synthesis Desk"—four AI agents that collaborate to answer research questions using your local documents.

---

## Why Multi-Agent Orchestration?

Single LLM calls are powerful, but they have limitations:

1. **Context window constraints** — Complex tasks may exceed the model's context limit
2. **Lack of specialization** — One prompt trying to do everything often underperforms
3. **No iterative refinement** — Single-shot responses miss review and improvement cycles
4. **Hard to debug** — A monolithic prompt is harder to trace than discrete agent steps

Multi-agent orchestration solves these by breaking work into specialized roles:

```
User Question
     │
     ▼
  Planner      → Breaks question into sub-tasks
     │
     ▼
  Retriever    → Finds relevant content from local docs
     │
     ▼
  Critic       → Reviews for gaps and contradictions
     │
     ▼
  Writer       → Produces final report with citations
```

Each agent has a focused system prompt and receives structured input from previous agents. This decomposition improves quality and makes the pipeline debuggable.

---

## The Architecture

Here's how Foundry Local and MAF work together:

```
┌─────────────────────────────────────────────────────────┐
│                    Your Machine                          │
│                                                          │
│  ┌──────────────┐    Control Plane     ┌──────────────┐ │
│  │  Python App   │───(foundry-local-sdk)──►│Foundry Local │
│  │  (MAF agents) │                     │   Service     │ │
│  │               │    Data Plane       │               │ │
│  │  OpenAIChatClient──(OpenAI API)────►│  Model (LLM) │ │
│  └──────────────┘                     └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Control Plane**: The `foundry-local-sdk` manages the runtime—starting the service, downloading models, and returning the endpoint URL.

**Data Plane**: MAF's `OpenAIChatClient` sends chat completions to Foundry Local's OpenAI-compatible API. The port is assigned dynamically, so you never hardcode it.

---

## Key Implementation Details

### 1. Bootstrapping Foundry Local

The first challenge is starting Foundry Local and getting the endpoint URL. Here's how:

```python
from foundry_local import FoundryLocalManager

async def boot_foundry(model_alias: str = "qwen2.5-0.5b"):
    manager = FoundryLocalManager()
    
    # Download model if needed (cached after first download)
    await manager.download_model(model_alias)
    
    # Start the service and get the endpoint
    endpoint = await manager.start()
    
    return endpoint  # e.g., "http://localhost:54321/v1"
```

The SDK handles hardware detection—if you have a compatible GPU, it uses CUDA/DirectML. Otherwise, it falls back to CPU inference.

### 2. Creating MAF Agents

Each agent is a `ChatAgent` with a specialized system prompt:

```python
from agent_framework import ChatAgent, OpenAIChatClient

def create_agents(endpoint: str, model: str):
    client = OpenAIChatClient(
        base_url=endpoint,
        model=model,
        api_key="foundry-local"  # Any non-empty string works
    )
    
    planner = ChatAgent(
        name="Planner",
        instructions="""You are a planning assistant. 
        Break the user's question into 2-4 concrete sub-tasks.
        Output a numbered list of tasks.""",
        client=client
    )
    
    retriever = ChatAgent(
        name="Retriever",
        instructions="""You are a research assistant.
        Given sub-tasks and document snippets, extract relevant information.
        Always cite the source document.""",
        client=client
    )
    
    # ... similarly for Critic and Writer
    
    return {"planner": planner, "retriever": retriever, ...}
```

### 3. Sequential vs. Concurrent Orchestration

The demo showcases both orchestration patterns:

**Sequential Pipeline** — Each agent waits for the previous one:

```python
async def run_sequential(agents, question, docs):
    # Step 1: Planner breaks down the question
    plan = await agents["planner"].run(question)
    
    # Step 2: Retriever finds relevant content
    context = await agents["retriever"].run(
        f"Plan: {plan}\n\nDocuments: {docs}"
    )
    
    # Step 3: Critic reviews for gaps
    critique = await agents["critic"].run(
        f"Plan: {plan}\n\nContext: {context}"
    )
    
    # Step 4: Writer produces final report
    report = await agents["writer"].run(
        f"Plan: {plan}\n\nContext: {context}\n\nCritique: {critique}"
    )
    
    return report
```

**Concurrent Fan-Out** — Independent tasks run in parallel:

```python
async def run_concurrent_retrieval(agents, plan, docs):
    # Retriever and ToolAgent don't depend on each other
    results = await asyncio.gather(
        agents["retriever"].run(f"Plan: {plan}\n\nDocs: {docs}"),
        agents["tool_agent"].run(f"Analyze: {plan}")
    )
    
    return merge_results(results)
```

The concurrent approach saves time when agents are independent—the Retriever searches documents while the ToolAgent extracts keywords, and both complete in the time of the slower task.

### 4. Tool/Function Calling

MAF supports tool calling where the LLM can invoke Python functions. Here's a simple example:

```python
from pydantic import BaseModel, Field

class WordCountInput(BaseModel):
    text: str = Field(description="The text to count words in")

def word_count(text: str) -> int:
    """Count the number of words in the given text."""
    return len(text.split())

# Register the tool with the agent
tool_agent = ChatAgent(
    name="ToolAgent",
    instructions="Use tools to analyze text when asked.",
    client=client,
    tools=[word_count]
)
```

When the user asks "How many words are in this paragraph?", the model emits a tool call, MAF executes the function, and the result is returned to the model for final response generation.

### 5. Streaming Responses in the Web UI

The web UI uses Server-Sent Events (SSE) to stream agent progress:

```python
@app.route("/api/workflow", methods=["POST"])
def run_workflow():
    question = request.json.get("question")
    
    def generate():
        for agent_name, output in orchestrator.run_stream(question):
            data = {"agent": agent_name, "text": output}
            yield f"data: {json.dumps(data)}\n\n"
    
    return Response(generate(), mimetype="text/event-stream")
```

The frontend listens to these events and updates the UI in real-time:

```javascript
const source = new EventSource("/api/workflow?q=" + encodeURIComponent(question));
source.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateAgentOutput(data.agent, data.text);
};
```

---

## What Makes This Demo Interesting

### Completely Local Execution

Every computation—model inference, document retrieval, agent orchestration—happens on your machine. This means:

- **Privacy**: Your documents never leave your device
- **Cost**: No per-token API charges
- **Latency**: No network round-trips
- **Offline**: Works without internet (after initial model download)

### Hardware Flexibility

Foundry Local automatically selects the best backend for your hardware:

- **NVIDIA GPU**: CUDA acceleration
- **AMD/Intel GPU**: DirectML acceleration
- **NPU** (Neural Processing Unit): Hardware-specific optimizations
- **CPU**: Works everywhere, just slower

### Model Quality vs. Speed Tradeoff

The demo defaults to `qwen2.5-0.5b` (500M parameters) for fast iteration. In production, you might use:

| Model | Parameters | Speed | Quality |
|-------|------------|-------|---------|
| qwen2.5-0.5b | 500M | ⚡⚡⚡ | Good for demos |
| qwen2.5-3b | 3B | ⚡⚡ | Better reasoning |
| qwen2.5-7b | 7B | ⚡ | Production quality |
| phi-3.5-mini | 3.8B | ⚡⚡ | Excellent reasoning |

Switch models with a single flag: `--model qwen2.5-7b`

---

## Common Pitfalls and Solutions

### 1. Tool Call XML Leaking into Output

Smaller models sometimes emit raw `<tool_call>` XML in their responses. The fix is to strip it:

```python
import re

def clean_response(text: str) -> str:
    return re.sub(r'<tool_call>.*?</tool_call>\s*', '', text, flags=re.DOTALL).strip()
```

### 2. Model Doesn't Follow Tool Calling Format

Not all models support function calling. Stick to models that explicitly support it:
- Qwen 2.5 family ✅
- Phi-3.5 family ✅
- Llama 3.2 family ✅

### 3. First Run is Slow

Model download can take several minutes depending on size and connection. The model is cached in `~/.foundry/` for future runs.

### 4. Memory Constraints

Larger models need more RAM/VRAM:
- 0.5B model: ~2GB
- 3B model: ~6GB
- 7B model: ~14GB

Check your available memory before selecting a model.

---

## Getting Started

```bash
# 1. Install Foundry Local
# Follow: https://github.com/microsoft/Foundry-Local

# 2. Clone and set up
git clone <this-repo>
cd agentframework-foundrylocal
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# 3. Run the CLI demo
python -m src.app "What are the benefits of multi-agent AI systems?"

# 4. Launch the web UI
python -m src.app.web
# Open http://localhost:5000
```

---

## What's Next?

This demo is a starting point. Here are ideas for extending it:

1. **Add more agents**: A "Fact Checker" agent that verifies claims against external sources
2. **Implement memory**: Let agents remember context across sessions using vector databases
3. **Add human-in-the-loop**: Pause for user approval before the Writer produces the final report
4. **Build evaluation pipelines**: Measure agent quality with automated metrics
5. **Deploy as a service**: Package the orchestrator as a REST API for team use

---

## Resources

- **Foundry Local**: [foundrylocal.ai](https://foundrylocal.ai)
- **Microsoft Agent Framework**: [learn.microsoft.com/en-us/agent-framework](https://learn.microsoft.com/en-us/agent-framework/)
- **MAF GitHub Samples**: [github.com/microsoft/Agent-Framework-Samples](https://github.com/microsoft/Agent-Framework-Samples)
- **Foundry Local SDK Reference**: [Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-sdk)

---

*Built with Microsoft Agent Framework and Foundry Local. All inference runs on your machine.*
