"""
Web UI for the Local Research & Synthesis Desk.
────────────────────────────────────────────────
A browser-based interface that streams multi-agent orchestration
progress in real time using Server-Sent Events (SSE).

Usage:
    python -m src.app.web              # starts on http://localhost:5000
    PORT=8080 python -m src.app.web    # custom port

Architecture:
    Flask serves the SPA (index.html) and exposes two API endpoints:
      POST /api/run      — kicks off a workflow and streams agent steps as SSE
      POST /api/tools    — runs the tool demo and returns results
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

# Ensure src/ is on path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.foundry_boot import FoundryLocalBootstrapper, FoundryConnection  # noqa: E402
from app.documents import load_documents, LoadedDocuments  # noqa: E402
from app.agents import (  # noqa: E402
    create_planner,
    create_retriever,
    create_critic,
    create_writer,
    create_tool_agent,
    word_count,
    extract_keywords,
)
from app.demos import list_demos, get_demo  # noqa: E402
from app.orchestrator import MAX_CRITIC_LOOPS, _critic_found_gaps  # noqa: E402

load_dotenv()
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
for noisy in ("httpx", "httpcore", "openai", "urllib3", "werkzeug"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

log = logging.getLogger(__name__)

# ─── Flask app ───────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)


# ─── Security Headers ────────────────────────────────────────────
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # CSP allows inline styles/scripts for this single-page app
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response

# ─── Lazy globals (initialised on first request) ─────────────────
_conn: FoundryConnection | None = None
_docs: LoadedDocuments | None = None


def _get_connection() -> FoundryConnection:
    """Bootstrap Foundry Local once and cache."""
    global _conn
    if _conn is None:
        log.info("Bootstrapping Foundry Local …")
        boot = FoundryLocalBootstrapper()
        _conn = boot.bootstrap()
        log.info("Foundry Local ready → %s  model=%s", _conn.endpoint, _conn.model_id)
    return _conn


def _get_docs(docs_path: str = "./data") -> LoadedDocuments:
    """Load documents once and cache."""
    global _docs
    if _docs is None:
        _docs = load_documents(docs_path)
    return _docs


# ─── Helper: clean agent output ──────────────────────────────────────────────

import re as _re

_TOOL_CALL_RE = _re.compile(
    r"<tool_call>.*?</tool_call>\s*",
    _re.DOTALL,
)


def _clean_agent_text(raw: str) -> str:
    """Strip <tool_call> XML fragments that some models emit."""
    return _TOOL_CALL_RE.sub("", raw).strip()


# ─── Helper: run a single agent step ────────────────────────────────────────

async def _agent_step(agent, prompt: str) -> tuple[str, float]:
    t0 = time.perf_counter()
    result = await agent.run(prompt)
    elapsed = time.perf_counter() - t0
    text = _clean_agent_text(str(result))
    return text, elapsed


# ─── Routes ──────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the SPA."""
    return render_template("index.html")


@app.route("/api/status")
def status():
    """Return service health and config."""
    try:
        conn = _get_connection()
        docs = _get_docs()
        return jsonify({
            "status": "ok",
            "model_id": conn.model_id,
            "model_alias": conn.model_alias,
            "endpoint": conn.endpoint,
            "documents": docs.file_count,
            "chunks": len(docs.chunks),
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/run", methods=["POST"])
def run_workflow():
    """
    Run the multi-agent workflow and stream results as SSE.

    Body JSON: { "question": "...", "mode": "full"|"sequential", "docs_path": "./data" }
    Response: text/event-stream with JSON events.
    """
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    mode = data.get("mode", "full")
    docs_path = data.get("docs_path", "./data")

    if not question:
        return jsonify({"error": "question is required"}), 400

    def generate():
        """Generator that yields SSE events as each agent completes."""
        try:
            conn = _get_connection()
            docs = _get_docs(docs_path)
            doc_block = docs.combined_text if docs.chunks else "(no documents provided)"
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)  # Required for asyncio.gather() to find the loop

            # Emit setup info
            yield _sse({
                "type": "info",
                "model": conn.model_id,
                "endpoint": conn.endpoint,
                "documents": docs.file_count,
                "chunks": len(docs.chunks),
            })

            # ── Step 1: Planner ──────────────────────────────────
            yield _sse({"type": "step_start", "agent": "Planner", "description": "Breaking the question into tasks…"})
            planner = create_planner(conn)
            plan_text, elapsed = loop.run_until_complete(
                _agent_step(planner, f"User question: {question}\n\nAvailable documents:\n{doc_block}")
            )
            yield _sse({"type": "step_done", "agent": "Planner", "output": plan_text, "elapsed": round(elapsed, 2)})

            if mode == "full":
                # ── Step 2: Concurrent (Retriever + ToolAgent) ───
                yield _sse({"type": "step_start", "agent": "Concurrent", "description": "Retriever + ToolAgent running in parallel…"})
                retriever = create_retriever(conn)
                tool_agent = create_tool_agent(conn)

                retriever_prompt = f"Plan:\n{plan_text}\n\nDocuments:\n{doc_block}"
                tool_prompt = f"Please extract keywords from the following text:\n{doc_block}"

                (snippets_text, r_elapsed), (tool_text, t_elapsed) = loop.run_until_complete(
                    asyncio.gather(
                        _agent_step(retriever, retriever_prompt),
                        _agent_step(tool_agent, tool_prompt),
                    )
                )

                yield _sse({
                    "type": "step_done", "agent": "Retriever",
                    "output": snippets_text, "elapsed": round(r_elapsed, 2),
                    "concurrent": True,
                })
                yield _sse({
                    "type": "step_done", "agent": "ToolAgent",
                    "output": tool_text, "elapsed": round(t_elapsed, 2),
                    "concurrent": True,
                })

                # ── Step 3: Critic ⇄ Retriever feedback loop ──
                critique_text = ""
                for iteration in range(1, MAX_CRITIC_LOOPS + 1):
                    iter_label = f" (iteration {iteration}/{MAX_CRITIC_LOOPS})" if MAX_CRITIC_LOOPS > 1 else ""
                    yield _sse({"type": "step_start", "agent": "Critic", "description": f"Reviewing for gaps & contradictions…{iter_label}"})
                    critic = create_critic(conn)
                    critique_text, elapsed = loop.run_until_complete(
                        _agent_step(critic, f"Plan:\n{plan_text}\n\nExtracted snippets:\n{snippets_text}\n\nKeywords/stats:\n{tool_text}")
                    )
                    yield _sse({"type": "step_done", "agent": f"Critic{iter_label}", "output": critique_text, "elapsed": round(elapsed, 2)})

                    if not _critic_found_gaps(critique_text) or iteration == MAX_CRITIC_LOOPS:
                        break

                    # Re-retrieve to fill gaps
                    yield _sse({"type": "step_start", "agent": "Retriever", "description": f"Filling gaps flagged by Critic…{iter_label}"})
                    retriever = create_retriever(conn)
                    re_retriever_prompt = (
                        f"The Critic found these gaps in the previous retrieval:\n{critique_text}\n\n"
                        f"Original plan:\n{plan_text}\n\n"
                        f"Previous snippets (already retrieved):\n{snippets_text}\n\n"
                        f"Documents:\n{doc_block}\n\n"
                        f"Please find additional relevant passages to fill ONLY the gaps listed above. "
                        f"Do not repeat previously retrieved snippets."
                    )
                    new_snippets, elapsed = loop.run_until_complete(
                        _agent_step(retriever, re_retriever_prompt)
                    )
                    yield _sse({"type": "step_done", "agent": f"Retriever (gap-fill{iter_label})", "output": new_snippets, "elapsed": round(elapsed, 2)})
                    snippets_text = f"{snippets_text}\n\n--- Additional snippets (gap-fill iteration {iteration}) ---\n\n{new_snippets}"

                # ── Step 4: Writer ──────────────────────────────
                yield _sse({"type": "step_start", "agent": "Writer", "description": "Composing the final report…"})
                writer = create_writer(conn)
                report_text, elapsed = loop.run_until_complete(
                    _agent_step(writer, (
                        f"Original question: {question}\n\n"
                        f"Plan:\n{plan_text}\n\n"
                        f"Extracted snippets:\n{snippets_text}\n\n"
                        f"Keywords/stats:\n{tool_text}\n\n"
                        f"Critic review:\n{critique_text}"
                    ))
                )
                yield _sse({"type": "step_done", "agent": "Writer", "output": report_text, "elapsed": round(elapsed, 2)})

            else:
                # ── Sequential mode ─────────────────────────────
                yield _sse({"type": "step_start", "agent": "Retriever", "description": "Extracting relevant snippets…"})
                retriever = create_retriever(conn)
                snippets_text, elapsed = loop.run_until_complete(
                    _agent_step(retriever, f"Plan:\n{plan_text}\n\nDocuments:\n{doc_block}")
                )
                yield _sse({"type": "step_done", "agent": "Retriever", "output": snippets_text, "elapsed": round(elapsed, 2)})

                # Critic ⇄ Retriever feedback loop
                critique_text = ""
                for iteration in range(1, MAX_CRITIC_LOOPS + 1):
                    iter_label = f" (iteration {iteration}/{MAX_CRITIC_LOOPS})" if MAX_CRITIC_LOOPS > 1 else ""
                    yield _sse({"type": "step_start", "agent": "Critic", "description": f"Reviewing for gaps & contradictions…{iter_label}"})
                    critic = create_critic(conn)
                    critique_text, elapsed = loop.run_until_complete(
                        _agent_step(critic, f"Plan:\n{plan_text}\n\nExtracted snippets:\n{snippets_text}")
                    )
                    yield _sse({"type": "step_done", "agent": f"Critic{iter_label}", "output": critique_text, "elapsed": round(elapsed, 2)})

                    if not _critic_found_gaps(critique_text) or iteration == MAX_CRITIC_LOOPS:
                        break

                    # Re-retrieve to fill gaps
                    yield _sse({"type": "step_start", "agent": "Retriever", "description": f"Filling gaps flagged by Critic…{iter_label}"})
                    retriever = create_retriever(conn)
                    re_retriever_prompt = (
                        f"The Critic found these gaps in the previous retrieval:\n{critique_text}\n\n"
                        f"Original plan:\n{plan_text}\n\n"
                        f"Previous snippets (already retrieved):\n{snippets_text}\n\n"
                        f"Documents:\n{doc_block}\n\n"
                        f"Please find additional relevant passages to fill ONLY the gaps listed above. "
                        f"Do not repeat previously retrieved snippets."
                    )
                    new_snippets, elapsed = loop.run_until_complete(
                        _agent_step(retriever, re_retriever_prompt)
                    )
                    yield _sse({"type": "step_done", "agent": f"Retriever (gap-fill{iter_label})", "output": new_snippets, "elapsed": round(elapsed, 2)})
                    snippets_text = f"{snippets_text}\n\n--- Additional snippets (gap-fill iteration {iteration}) ---\n\n{new_snippets}"

                yield _sse({"type": "step_start", "agent": "Writer", "description": "Composing the final report…"})
                writer = create_writer(conn)
                report_text, elapsed = loop.run_until_complete(
                    _agent_step(writer, (
                        f"Original question: {question}\n\n"
                        f"Plan:\n{plan_text}\n\n"
                        f"Extracted snippets:\n{snippets_text}\n\n"
                        f"Critic review:\n{critique_text}"
                    ))
                )
                yield _sse({"type": "step_done", "agent": "Writer", "output": report_text, "elapsed": round(elapsed, 2)})

            yield _sse({"type": "complete", "report": report_text})
            loop.close()

        except Exception as exc:
            log.exception("Workflow error")
            yield _sse({"type": "error", "message": str(exc), "traceback": traceback.format_exc()})

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/tools", methods=["POST"])
def run_tools():
    """Run tool calling demo and return results."""
    try:
        conn = _get_connection()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)  # Required for asyncio.gather()
        results = []

        # Test 1: Direct tool calls
        r1 = word_count("The quick brown fox jumps over the lazy dog")
        r2 = extract_keywords(
            "Microsoft Agent Framework enables multi-agent orchestration. "
            "The framework supports sequential and concurrent patterns. "
            "Foundry Local provides on-device inference for the agents."
        )
        results.append({"test": "Direct word_count", "result": str(r1), "status": "pass"})
        results.append({"test": "Direct extract_keywords", "result": str(r2), "status": "pass"})

        # Test 2: LLM-driven tool calling
        tool_agent = create_tool_agent(conn)
        llm_result = loop.run_until_complete(
            _agent_step(tool_agent, "Count the words in: 'Hello world from Foundry Local'")
        )
        results.append({
            "test": "LLM tool calling (word_count)",
            "result": str(llm_result[0]),
            "elapsed": round(llm_result[1], 2),
            "status": "pass",
        })

        # Test 3: LLM keyword extraction
        llm_result2 = loop.run_until_complete(
            _agent_step(
                tool_agent,
                "Extract keywords from: 'Foundry Local runs models locally. "
                "Foundry Local supports multiple hardware backends. "
                "Foundry Local integrates with Microsoft Agent Framework.'"
            )
        )
        results.append({
            "test": "LLM tool calling (extract_keywords)",
            "result": str(llm_result2[0]),
            "elapsed": round(llm_result2[1], 2),
            "status": "pass",
        })

        loop.close()
        return jsonify({"status": "ok", "results": results})

    except Exception as exc:
        log.exception("Tool demo error")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/documents")
def list_documents():
    """List loaded documents."""
    docs = _get_docs()
    return jsonify({
        "file_count": docs.file_count,
        "chunk_count": len(docs.chunks),
        "files": list({c.filename for c in docs.chunks}),
    })


# ─── Demo API endpoints ──────────────────────────────────────────

@app.route("/api/demos")
def get_demos():
    """List all available demos with metadata."""
    demos = list_demos()
    return jsonify({
        "status": "ok",
        "demos": [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "icon": d.icon,
                "category": d.category,
                "tags": d.tags,
                "suggested_prompt": d.suggested_prompt,
            }
            for d in demos
        ]
    })


@app.route("/api/demo/<demo_id>/run", methods=["POST"])
def run_demo(demo_id: str):
    """
    Run a specific demo and stream results as SSE.
    
    Body JSON: { "prompt": "..." }
    Response: text/event-stream with JSON events.
    """
    data = request.get_json(force=True)
    prompt = data.get("prompt", "").strip()
    
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    
    demo = get_demo(demo_id)
    if demo is None:
        return jsonify({"error": f"Demo '{demo_id}' not found"}), 404
    
    def generate():
        """Generator that yields SSE events for demo execution."""
        try:
            conn = _get_connection()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Emit demo info
            yield _sse({
                "type": "info",
                "demo_id": demo.id,
                "demo_name": demo.name,
                "model": conn.model_id,
                "endpoint": conn.endpoint,
            })
            
            # Run the demo
            yield _sse({
                "type": "step_start",
                "agent": demo.name,
                "description": f"Running {demo.name}..."
            })
            
            t0 = time.perf_counter()
            result = loop.run_until_complete(demo.runner(conn, prompt))
            elapsed = time.perf_counter() - t0
            
            # Handle dict response from demos that return rich metadata
            if isinstance(result, dict) and "response" in result:
                output_text = _clean_agent_text(str(result["response"]))
            elif isinstance(result, dict):
                # Build readable text from structured results (e.g. debate)
                parts = []
                for key, val in result.items():
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, dict):
                                label = item.get("speaker") or item.get("agent") or ""
                                body = item.get("argument") or item.get("output") or str(item)
                                parts.append(f"[{label}]\n{body}")
                            else:
                                parts.append(str(item))
                    elif isinstance(val, str) and len(val) > 2:
                        parts.append(f"{key}: {val}")
                output_text = "\n\n".join(parts) if parts else str(result)
            else:
                output_text = _clean_agent_text(str(result))

            yield _sse({
                "type": "step_done",
                "agent": demo.name,
                "output": output_text,
                "elapsed": round(elapsed, 2)
            })
            
            yield _sse({
                "type": "complete",
                "report": output_text,
                "elapsed": round(elapsed, 2)
            })
            
            loop.close()
            
        except Exception as exc:
            log.exception("Demo error")
            yield _sse({
                "type": "error",
                "message": str(exc),
                "traceback": traceback.format_exc()
            })
    
    return Response(generate(), mimetype="text/event-stream")


# ─── SSE helper ──────────────────────────────────────────────────

def _sse(data: dict) -> str:
    """Format a dict as an SSE event."""
    return f"data: {json.dumps(data)}\n\n"


# ─── Entry point ─────────────────────────────────────────────────

def main():
    port = int(os.getenv("PORT", "5000"))
    print(f"\n  🌐  Local Research & Synthesis Desk — Web UI")
    print(f"  📍  http://localhost:{port}")
    print(f"  ⏹   Press Ctrl+C to stop\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
