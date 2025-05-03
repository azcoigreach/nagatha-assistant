import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from nagatha_assistant.plugins.nist_time import NistTimePlugin


class DummyReader:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self, n: int) -> bytes:
        return self._data


class DummyWriter:
    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        return None


@pytest.mark.asyncio
async def test_nist_time_parses_and_converts(monkeypatch):
    """Ensure NIST response is parsed and converted to MST and other timezones."""
    # Provide a fake NIST daytime response: YY-MM-DD HH:MM:SS
    fake_line = b"0 23-01-02 12:00:00 0 0 0 0 UTC(NIST) *\n"

    async def fake_open(host, port):  # noqa: ARG002
        assert host == "time.nist.gov" and port == 13
        return DummyReader(fake_line), DummyWriter()

    monkeypatch.setattr(asyncio, 'open_connection', fake_open)
    plugin = NistTimePlugin()

    # Default timezone MST (UTC-7): 2023-01-02 12:00:00 UTC -> 2023-01-02 05:00:00 MST
    res_mst = await plugin.call('get_nist_time', {})
    assert res_mst == '2023-01-02 05:00:00 MST'

    # UTC timezone should return the same time with 'UTC'
    res_utc = await plugin.call('get_nist_time', {'timezone': 'UTC'})
    assert res_utc == '2023-01-02 12:00:00 UTC'

    # Unknown timezone yields an error message
    res_err = await plugin.call('get_nist_time', {'timezone': 'Foo/Bar'})
    assert 'Unknown timezone' in res_err


@pytest.mark.asyncio
async def test_nist_time_fallback_on_connection_error(monkeypatch):
    """If connection to NIST fails, fallback to system UTC time and convert to MST."""
    # Make open_connection raise
    async def fake_open_fail(host, port):  # noqa: ARG002
        raise ConnectionError('no route to host')

    monkeypatch.setattr(asyncio, 'open_connection', fake_open_fail)
    plugin = NistTimePlugin()

    # Call should not raise, and should return a string ending with MST
    res = await plugin.call('get_nist_time', {})
    assert res.endswith(' MST')
    # Validate format: YYYY-MM-DD HH:MM:SS MST
    parts = res.split()
    assert len(parts) == 3 and parts[2] == 'MST'