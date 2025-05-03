"""Track OpenAI API token usage and cost.

This helper is intentionally lightweight – it records cumulative usage in a
JSON file (``.nagatha_usage.json`` in the project root).  Using a file keeps
the dependency surface small and avoids additional database migrations.

If you need more sophisticated reporting (per-day breakdown, per-feature
aggregation), migrate this logic into the existing SQL database – the public
API of :func:`record_usage` can remain unchanged.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import MutableMapping


_log = logging.getLogger()

# ---------------------------------------------------------------------------
# Pricing table
# ---------------------------------------------------------------------------
# Minimal subset of popular ChatCompletion models.  Prices are in USD per 1K
# *tokens* as of February-2024 pricing.  Update when OpenAI revises their
# tariffs.

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "gpt-3.5-turbo-0125": (0.0005, 0.0015),
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o": (0.0025, 0.0100),
    "gpt-4o-2024-05-13": (0.0025, 0.0100),
    "gpt-4-turbo": (0.0100, 0.0300),
    "gpt-4.1-mini": (0.0004, 0.0016), # Input $0.40/M Output $1.60/M
    "gpt-4.1": (0.002, 0.008), # Input $2.00/M Output $8.00/M
    "gpt-4.1-nano": (0.0001, 0.0004), # Input $0.10/M Output $0.40/M
}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

_FILE_PATH = Path(os.getenv("NAGATHA_USAGE_FILE", ".nagatha_usage.json"))
_LOCK = threading.Lock()


def _load() -> MutableMapping[str, dict[str, float]]:
    if _FILE_PATH.is_file():
        try:
            with _FILE_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data  # type: ignore[return-value]
        except Exception as exc:  # pragma: no cover – non-fatal
            _log.warning("Failed to read usage file: %s", exc)
    return {}


def _save(data: MutableMapping[str, dict[str, float]]) -> None:
    try:
        with _FILE_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:  # pragma: no cover
        _log.warning("Failed to write usage file: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Add the given token counts to the persistent running totals.

    Cost is computed using :data:`MODEL_PRICING`.  Unknown models are recorded
    but cost defaults to ``0`` so that future migrations can recalculate when
    pricing becomes known.
    """

    with _LOCK:
        data = _load()
        rec = data.setdefault(model, {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0})

        rec["prompt_tokens"] += prompt_tokens
        rec["completion_tokens"] += completion_tokens

        price = MODEL_PRICING.get(model)
        if price:
            p_cost, c_cost = price
            rec["cost_usd"] += (prompt_tokens / 1000) * p_cost + (completion_tokens / 1000) * c_cost

        _save(data)


def load_usage() -> dict[str, dict[str, float]]:
    """Return the cumulative usage structure."""

    return _load()
