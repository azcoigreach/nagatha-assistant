"""Example plugin that echoes the provided text.

This demonstrates the minimal structure required for Nagatha plugins so that
the chat agent can discover and call them via OpenAI function calling.
"""

from __future__ import annotations

from typing import Any, Dict, List

from nagatha_assistant.core.plugin import Plugin


class EchoPlugin(Plugin):
    """A trivial plugin that returns the same text that was given to it."""

    name = "echo"
    version = "0.1.0"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def setup(self, config: Dict[str, Any]) -> None:  # noqa: D401
        # For this simple plugin there is nothing to configure.
        return None

    async def teardown(self) -> None:  # noqa: D401
        return None

    # ------------------------------------------------------------------
    # Function-calling spec
    # ------------------------------------------------------------------

    def function_specs(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "echo",
                "description": "Return exactly the text that was passed in.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to echo back.",
                        }
                    },
                    "required": ["text"],
                },
            }
        ]

    async def call(self, name: str, arguments: Dict[str, Any]) -> str:  # noqa: D401
        import logging

        logger = logging.getLogger(__name__)

        if name != "echo":
            raise ValueError(f"EchoPlugin can only handle 'echo', not {name}")

        text = str(arguments.get("text", ""))
        logger.debug("EchoPlugin returning '%s'", text)
        return text
