"""Optional live bridge checks (no real ChatGPT login)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ryoku_ai.siwc import BridgePaths, SiwcBridge, bridge_ready


@unittest.skipUnless(bridge_ready()[0], "SIWC bridge dependencies not installed")
class BridgeIntegrationTests(unittest.TestCase):
    def test_ping_and_disconnected_session(self):
        paths = BridgePaths.discover(Path(__file__))
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            with SiwcBridge(storage_dir=storage, test_memory_crypto=True, paths=paths) as bridge:
                ping = bridge.request("ping")
                self.assertTrue(ping.get("pong"))
                session = bridge.request("session")
                self.assertEqual(session.get("status"), "disconnected")
                self.assertFalse(session.get("sharing"))
                profiles = bridge.request("profiles")
                self.assertEqual(profiles, [])


if __name__ == "__main__":
    unittest.main()
