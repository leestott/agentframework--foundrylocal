# Multi-Agent Orchestration — Design Patterns

## Why Multi-Agent?

Single agents are limited when tasks require diverse expertise. Multi-agent
systems break complex problems into specialized roles, improving quality and
maintainability.

## Pattern Deep-Dive

### 1. Sequential Pipeline
Agents form a chain where each agent processes the output of the previous one.

**When to use**: Tasks with clear stages — planning, execution, review.

**Example flow**:
  User question → Planner → Retriever → Critic → Writer → Final report

Advantages:
- Easy to understand and debug.
- Each agent has clear input/output contract.
- Full conversation history is available to later agents.

### 2. Concurrent Fan-Out
Multiple agents process the same input simultaneously and independently.

**When to use**: Independent analyses that can run in parallel.

**Example flow**:
  Plan → [Retriever | KeywordExtractor | SentimentAnalyzer] → Merge results

Advantages:
- Faster wall-clock time (parallelism).
- Diverse perspectives on the same data.

### 3. Group Chat
A manager coordinates turn-taking among agents in a shared conversation.

**When to use**: Iterative refinement, brainstorming, review cycles.

### 4. Handoff
Agents can dynamically transfer control to the most appropriate agent.

**When to use**: Escalation, fallback, dynamic routing.

## Combining Patterns

Real-world applications often combine patterns. For example:
  1. Sequential: Planner first.
  2. Concurrent: Retriever + ToolAgent in parallel.
  3. Sequential: Critic, then Writer.

This hybrid approach gets the best of both worlds — dependency ordering where
needed, parallelism where possible.

### Code Sketch (Python + MAF)

```python
import asyncio
from agent_framework import ChatAgent

async def run_hybrid(question: str, agents: dict) -> str:
    # Step 1 — Sequential: Plan
    plan = await agents["planner"].run(question)

    # Step 2 — Concurrent: Retrieve + Tool analysis
    retriever_task = agents["retriever"].run(str(plan))
    tool_task = agents["tool"].run(str(plan))
    snippets, keywords = await asyncio.gather(retriever_task, tool_task)

    # Step 3 — Sequential: Critique then Write
    critique = await agents["critic"].run(f"{plan}\n{snippets}")
    report = await agents["writer"].run(f"{snippets}\n{keywords}\n{critique}")
    return str(report)
```
