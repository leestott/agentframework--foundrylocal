"""
Foundry Local Bootstrapper
──────────────────────────
Control-plane module that uses the *foundry-local-sdk* to:
  1. Start the Foundry Local service (if not already running).
  2. Download / load the requested model.
  3. Expose the OpenAI-compatible endpoint + API key for data-plane calls.

Reference:
  SDK docs  – https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-sdk?view=foundry-classic
  PyPI      – https://pypi.org/project/foundry-local-sdk/
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

log = logging.getLogger(__name__)


@dataclass
class FoundryConnection:
    """Holds the endpoint, API key, and resolved model ID returned after bootstrap."""
    endpoint: str
    api_key: str
    model_id: str
    model_alias: str


class FoundryLocalBootstrapper:
    """Manages the Foundry Local lifecycle using *foundry-local-sdk*.

    Typical flow
    ─────────────
    >>> boot = FoundryLocalBootstrapper()
    >>> conn = boot.bootstrap()          # blocking – starts service, downloads + loads model
    >>> conn.endpoint                    # e.g. "http://localhost:5272/v1"
    """

    def __init__(self, alias: str | None = None) -> None:
        load_dotenv()
        self.alias = alias or os.getenv("MODEL_ALIAS", "qwen2.5-0.5b")

    # ── public ──────────────────────────────────────────────────────
    def bootstrap(self) -> FoundryConnection:
        """Start service, download & load model, return connection info."""
        try:
            from foundry_local import FoundryLocalManager
        except ImportError as exc:
            raise SystemExit(
                "\n❌  foundry-local-sdk is not installed.\n"
                "   Run:  pip install foundry-local-sdk\n"
                "   Docs: https://pypi.org/project/foundry-local-sdk/\n"
            ) from exc

        log.info("Bootstrapping Foundry Local with alias '%s' …", self.alias)

        # Check for a user-provided endpoint override
        endpoint_override = os.getenv("FOUNDRY_LOCAL_ENDPOINT")

        try:
            if endpoint_override:
                log.info("Using endpoint override: %s", endpoint_override)
                manager = FoundryLocalManager()
                # Still ensure the model is loaded
                manager.download_model(self.alias)
                model_info = manager.load_model(self.alias)
            else:
                # Full bootstrap: start service + download + load model
                manager = FoundryLocalManager(self.alias)
                model_info = manager.get_model_info(self.alias)

        except FileNotFoundError:
            raise SystemExit(
                "\n❌  Foundry Local CLI not found on PATH.\n"
                "   Install it from: https://github.com/microsoft/Foundry-Local\n"
                "   Then verify:     foundry --help\n"
            )
        except Exception as exc:
            raise SystemExit(
                f"\n❌  Foundry Local bootstrap failed: {exc}\n"
                "   • Is Foundry Local installed?  https://github.com/microsoft/Foundry-Local\n"
                "   • Run: foundry model list   — to see available models.\n"
            ) from exc

        endpoint = endpoint_override or manager.endpoint
        api_key = manager.api_key

        conn = FoundryConnection(
            endpoint=endpoint,
            api_key=api_key,
            model_id=model_info.id if model_info else self.alias,
            model_alias=self.alias,
        )
        log.info(
            "✅  Foundry Local ready  →  endpoint=%s  model=%s",
            conn.endpoint,
            conn.model_id,
        )
        return conn
