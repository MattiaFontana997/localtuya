from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTUYA = ROOT / "custom_components/localtuya/pytuya/__init__.py"
TESTS = ROOT / "tests/test_pytuya.py"

src = PYTUYA.read_text(encoding="utf-8")
old = '''            header = parse_header(self.buffer)\n\n            # Do not attempt authentication/decryption until the\n            # complete frame has arrived.\n'''
new = '''            try:\n                header = parse_header(self.buffer)\n            except DecodeError as ex:\n                # A malformed header is a terminal failure for the current\n                # TCP stream. Wake every waiter immediately instead of letting\n                # asyncio.Protocol.data_received() raise while callers sit\n                # blocked until their request timeout expires.\n                self.debug(\n                    "Failed to decode Tuya frame header: %s",\n                    ex,\n                )\n                self.buffer = b""\n                self.abort(ex)\n                return\n\n            # Do not attempt authentication/decryption until the\n            # complete frame has arrived.\n'''
if old not in src:
    raise SystemExit("add_data parse_header anchor not found")
src = src.replace(old, new, 1)

old = '''        if self.dispatcher is not None:\n            self.dispatcher.local_key = self.real_local_key\n        try:\n            listener = self.listener and self.listener()\n'''
new = '''        if self.dispatcher is not None:\n            self.dispatcher.local_key = self.real_local_key\n            # A closed transport can never satisfy outstanding requests.\n            # Fail them now so device outages/reboots do not masquerade as\n            # ordinary command timeouts.\n            disconnect_error = (\n                exc\n                if isinstance(exc, BaseException)\n                else ConnectionError("Tuya device connection lost")\n            )\n            self.dispatcher.abort(disconnect_error)\n        try:\n            listener = self.listener and self.listener()\n'''
if old not in src:
    raise SystemExit("connection_lost anchor not found")
src = src.replace(old, new, 1)
PYTUYA.write_text(src, encoding="utf-8")

tests = TESTS.read_text(encoding="utf-8")
anchor = '''    async def test_connection_loss_discards_34_session_key(self):\n'''
insert = '''    async def test_malformed_header_wakes_pending_request_immediately(self):\n        """Malformed wire headers must fail pending exchanges without timeout."""\n        protocol = self._protocol(3.3)\n        waiter = asyncio.create_task(\n            protocol.dispatcher.wait_for(1, DP_QUERY, timeout=5)\n        )\n        await asyncio.sleep(0)\n\n        malformed = struct.pack(\n            MESSAGE_HEADER_FMT,\n            PREFIX_VALUE,\n            1,\n            DP_QUERY,\n            1001,\n        )\n        protocol.data_received(malformed)\n\n        with self.assertRaises(DecodeError):\n            await asyncio.wait_for(waiter, timeout=0.2)\n\n        await protocol.close()\n\n    async def test_connection_loss_wakes_pending_request_immediately(self):\n        """A dropped device socket must abort waiters instead of timing out."""\n        protocol = self._protocol(3.3)\n        waiter = asyncio.create_task(\n            protocol.dispatcher.wait_for(1, DP_QUERY, timeout=5)\n        )\n        await asyncio.sleep(0)\n\n        protocol.connection_lost(None)\n\n        with self.assertRaises(ConnectionError):\n            await asyncio.wait_for(waiter, timeout=0.2)\n\n        await protocol.close()\n\n'''
if insert not in tests:
    if anchor not in tests:
        raise SystemExit("test insertion anchor not found")
    tests = tests.replace(anchor, insert + anchor, 1)
TESTS.write_text(tests, encoding="utf-8")
