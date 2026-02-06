"""
Orchestration engine — Local Research & Synthesis Desk
──────────────────────────────────────────────────────
Demonstrates **two** multi-agent orchestration patterns using
Microsoft Agent Framework (MAF) + Foundry Local:

  1. **Sequential pipeline**  (Planner → Retriever → Critic → Writer)
     Each agent's output feeds the next as context.
     Best for: step-by-step workflows where order matters.

  2. **Concurrent fan-out**  (Retriever + ToolAgent run in parallel)
     Independent sub-tasks execute simultaneously; results are merged.
     Best for: independent analysis tasks that don't depend on each other.

Reference:
  Orchestration overview – https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/overview
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .agents import (
    create_planner,
    create_retriever,
    create_critic,
    create_writer,
    create_tool_agent,
)
from .documents import LoadedDocuments
from .foundry_boot import FoundryConnection

log = logging.getLogger(__name__)
console = Console()


@dataclass
class StepResult:
    """Captures one agent step for observability."""
    agent_name: str
    input_text: str
    output_text: str
    elapsed_sec: float


@dataclass
class WorkflowResult:
    """Final result of the entire orchestration run."""
    question: str
    steps: list[StepResult] = field(default_factory=list)
    final_report: str = ""


# ────────────────────────────────────────────────────────────────────
# Helper: invoke a single agent and record the step
# ────────────────────────────────────────────────────────────────────

async def _run_agent(agent, prompt: str) -> tuple[str, float]:
    """Invoke *agent.run(prompt)* and return (output_text, elapsed_seconds)."""
    t0 = time.perf_counter()
    result = await agent.run(prompt)
    elapsed = time.perf_counter() - t0
    return str(result), elapsed


# ────────────────────────────────────────────────────────────────────
# Pattern 1 — Sequential pipeline
# ────────────────────────────────────────────────────────────────────

async def run_sequential(
    question: str,
    docs: LoadedDocuments,
    conn: FoundryConnection,
) -> WorkflowResult:
    """
    Sequential orchestration:
      Planner → Retriever → Critic → Writer

    Each agent receives the accumulated context from all previous agents,
    building a progressively richer understanding of the task.

    Why sequential? The Writer needs the Critic's review, which needs the
    Retriever's snippets, which needs the Planner's task breakdown.  Each
    step depends on the one before it.
    """
    wf = WorkflowResult(question=question)
    doc_block = docs.combined_text if docs.chunks else "(no documents provided)"

    # Step 1 — Plan
    console.print(Panel("🗂  [bold cyan]Planner[/] — breaking the question into tasks …"))
    planner = create_planner(conn)
    planner_prompt = (
        f"User question: {question}\n\n"
        f"Available documents:\n{doc_block}"
    )
    plan_text, elapsed = await _run_agent(planner, planner_prompt)
    wf.steps.append(StepResult("Planner", planner_prompt, plan_text, elapsed))
    console.print(Markdown(plan_text))
    console.print(f"  ⏱  {elapsed:.1f}s\n")

    # Step 2 — Retrieve
    console.print(Panel("🔍  [bold green]Retriever[/] — extracting relevant snippets …"))
    retriever = create_retriever(conn)
    retriever_prompt = (
        f"Plan:\n{plan_text}\n\n"
        f"Documents:\n{doc_block}"
    )
    snippets_text, elapsed = await _run_agent(retriever, retriever_prompt)
    wf.steps.append(StepResult("Retriever", retriever_prompt, snippets_text, elapsed))
    console.print(Markdown(snippets_text))
    console.print(f"  ⏱  {elapsed:.1f}s\n")

    # Step 3 — Critique
    console.print(Panel("🧐  [bold yellow]Critic[/] — reviewing for gaps & contradictions …"))
    critic = create_critic(conn)
    critic_prompt = (
        f"Plan:\n{plan_text}\n\n"
        f"Extracted snippets:\n{snippets_text}"
    )
    critique_text, elapsed = await _run_agent(critic, critic_prompt)
    wf.steps.append(StepResult("Critic", critic_prompt, critique_text, elapsed))
    console.print(Markdown(critique_text))
    console.print(f"  ⏱  {elapsed:.1f}s\n")

    # Step 4 — Write final report
    console.print(Panel("✍️  [bold magenta]Writer[/] — composing the final report …"))
    writer = create_writer(conn)
    writer_prompt = (
        f"Original question: {question}\n\n"
        f"Plan:\n{plan_text}\n\n"
        f"Extracted snippets:\n{snippets_text}\n\n"
        f"Critic review:\n{critique_text}"
    )
    report_text, elapsed = await _run_agent(writer, writer_prompt)
    wf.steps.append(StepResult("Writer", writer_prompt, report_text, elapsed))
    wf.final_report = report_text
    console.print(Markdown(report_text))
    console.print(f"  ⏱  {elapsed:.1f}s\n")

    return wf


# ────────────────────────────────────────────────────────────────────
# Pattern 2 — Concurrent fan-out  (Retriever ‖ ToolAgent)
# ────────────────────────────────────────────────────────────────────

async def run_concurrent_retrieval(
    plan_text: str,
    docs: LoadedDocuments,
    conn: FoundryConnection,
) -> tuple[str, str]:
    """
    Concurrent orchestration:
      Retriever and ToolAgent run in parallel on the same input.

    Why concurrent? The Retriever extracts passages while the ToolAgent
    computes keyword frequency — two independent analyses that don't
    depend on each other.  Running them in parallel saves wall-clock time.
    """
    doc_block = docs.combined_text if docs.chunks else "(no documents provided)"

    retriever = create_retriever(conn)
    tool_agent = create_tool_agent(conn)

    retriever_prompt = f"Plan:\n{plan_text}\n\nDocuments:\n{doc_block}"
    tool_prompt = f"Please extract keywords from the following text:\n{doc_block}"

    console.print(
        Panel(
            "⚡  [bold]Concurrent fan-out[/] — Retriever + ToolAgent running in parallel …"
        )
    )

    (snippets_text, r_elapsed), (tool_text, t_elapsed) = await asyncio.gather(
        _run_agent(retriever, retriever_prompt),
        _run_agent(tool_agent, tool_prompt),
    )

    console.print(f"  Retriever finished in {r_elapsed:.1f}s")
    console.print(f"  ToolAgent finished in {t_elapsed:.1f}s\n")

    return snippets_text, tool_text


# ────────────────────────────────────────────────────────────────────
# Full orchestration  (combines both patterns)
# ────────────────────────────────────────────────────────────────────

async def run_full_workflow(
    question: str,
    docs: LoadedDocuments,
    conn: FoundryConnection,
) -> WorkflowResult:
    """
    End-to-end workflow that showcases BOTH orchestration patterns:

      1. Planner runs first  (sequential — must happen before anything else).
      2. Retriever + ToolAgent run concurrently (fan-out on independent tasks).
      3. Critic reviews the merged results (sequential — needs retriever output).
      4. Writer produces the final report (sequential — needs everything above).
    """
    wf = WorkflowResult(question=question)
    doc_block = docs.combined_text if docs.chunks else "(no documents provided)"

    # ── Step 1: Planner (sequential) ─────────────────────────────
    console.print(Panel("🗂  [bold cyan]Planner[/] — breaking the question into tasks …"))
    planner = create_planner(conn)
    planner_prompt = f"User question: {question}\n\nAvailable documents:\n{doc_block}"
    plan_text, elapsed = await _run_agent(planner, planner_prompt)
    wf.steps.append(StepResult("Planner", planner_prompt, plan_text, elapsed))
    console.print(Markdown(plan_text))
    console.print(f"  ⏱  {elapsed:.1f}s\n")

    # ── Step 2: Concurrent fan-out (Retriever ‖ ToolAgent) ───────
    snippets_text, tool_text = await run_concurrent_retrieval(plan_text, docs, conn)
    wf.steps.append(StepResult("Retriever", "(concurrent)", snippets_text, 0))
    wf.steps.append(StepResult("ToolAgent", "(concurrent)", tool_text, 0))
    console.print(Panel("[bold green]Retriever results[/]"))
    console.print(Markdown(snippets_text))
    console.print(Panel("[bold blue]ToolAgent results[/]"))
    console.print(Markdown(tool_text))

    # ── Step 3: Critic (sequential — needs retriever output) ─────
    console.print(Panel("🧐  [bold yellow]Critic[/] — reviewing for gaps & contradictions …"))
    critic = create_critic(conn)
    critic_prompt = (
        f"Plan:\n{plan_text}\n\n"
        f"Extracted snippets:\n{snippets_text}\n\n"
        f"Keywords/stats:\n{tool_text}"
    )
    critique_text, elapsed = await _run_agent(critic, critic_prompt)
    wf.steps.append(StepResult("Critic", critic_prompt, critique_text, elapsed))
    console.print(Markdown(critique_text))
    console.print(f"  ⏱  {elapsed:.1f}s\n")

    # ── Step 4: Writer (sequential — needs everything) ───────────
    console.print(Panel("✍️  [bold magenta]Writer[/] — composing the final report …"))
    writer = create_writer(conn)
    writer_prompt = (
        f"Original question: {question}\n\n"
        f"Plan:\n{plan_text}\n\n"
        f"Extracted snippets:\n{snippets_text}\n\n"
        f"Keywords/stats:\n{tool_text}\n\n"
        f"Critic review:\n{critique_text}"
    )
    report_text, elapsed = await _run_agent(writer, writer_prompt)
    wf.steps.append(StepResult("Writer", writer_prompt, report_text, elapsed))
    wf.final_report = report_text
    console.print(Markdown(report_text))
    console.print(f"  ⏱  {elapsed:.1f}s\n")

    return wf
