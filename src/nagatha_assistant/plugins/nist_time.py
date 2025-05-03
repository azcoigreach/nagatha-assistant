"""NISTTimePlugin – fetches current time from NIST time server (RFC 867 daytime protocol).

Connects to time.nist.gov on port 13, parses the UTC timestamp, converts it to MST
(UTC-7 without DST), and returns a formatted date-time string.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from nagatha_assistant.core.plugin import Plugin


class NistTimePlugin(Plugin):
    """Plugin to fetch current date and time from NIST and return in MST."""

    name = "nist_time"
    version = "0.1.0"

    async def setup(self, config: Dict[str, Any]) -> None:
        # No setup required for this plugin.
        return None

    async def teardown(self) -> None:
        # No teardown required.
        return None

    def function_specs(self) -> List[Dict[str, Any]]:
        """Expose get_nist_time function to the LLM."""
        return [
            {
                "name": "get_nist_time",
                "description": (
                    "Fetch the current date and time from NIST time server (time.nist.gov)"
                    " and return it in the specified timezone (default MST)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "IANA timezone name (e.g. 'America/Denver'). Default is MST (UTC-7).",
                        }
                    },
                    "required": [],
                },
            }
        ]

    async def call(self, name: str, arguments: Dict[str, Any]) -> str:
        if name != "get_nist_time":
            raise ValueError(f"NistTimePlugin cannot handle function {name}")
        tz_name = arguments.get("timezone", "MST")
        try:
            return await self._get_nist_time(tz_name)
        except Exception as exc:
            # Return error message rather than raising to avoid crashing the agent
            return f"Error fetching time: {exc}"

    async def _get_nist_time(self, tz_name: str) -> str:
        """Connect to NIST daytime server or fallback to system UTC, then convert to tz_name."""
        # Attempt NIST daytime protocol (port 13)
        try:
            reader, writer = await asyncio.open_connection("time.nist.gov", 13)
            raw = await reader.read(100)
            writer.close()
            await writer.wait_closed()
            line = raw.decode("ascii", errors="ignore").strip()
            parts = line.split()
            if len(parts) < 3:
                raise ValueError(f"Unexpected response from NIST server: {line}")
            # parts[1]=YY-MM-DD, parts[2]=HH:MM:SS
            yy, mm, dd = parts[1].split("-")
            hh, mi, ss = parts[2].split(":")
            year = 2000 + int(yy)
            month = int(mm)
            day = int(dd)
            hour = int(hh)
            minute = int(mi)
            second = int(ss)
            dt_utc = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        except Exception:
            # Fallback to local system UTC time
            dt_utc = datetime.now(timezone.utc)

        # Resolve requested timezone
        if tz_name == "MST":
            tz = timezone(timedelta(hours=-7), name="MST")
            label = "MST"
        else:
            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(tz_name)
                label = tz_name
            except Exception:
                raise ValueError(f"Unknown timezone: {tz_name}")

        dt_local = dt_utc.astimezone(tz)
        return dt_local.strftime("%Y-%m-%d %H:%M:%S") + f" {label}"