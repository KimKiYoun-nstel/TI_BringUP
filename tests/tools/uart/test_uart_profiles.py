from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.tools.uart.test_uartd import DaemonHarness
from tools.uart.integration import mcp_server as mcp
from tools.uart.integration.distribution import load_module
from tools.uart.integration.endpoint import EndpointConfigError, resolve_target_endpoint, resolve_token

UartDaemonError = load_module("uartd").UartDaemonError


class UartProfileTests(unittest.TestCase):
    def test_per_target_authentication_for_mcp_and_cli(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            harness = DaemonHarness(root)
            harness.config.auth_token = "test-sk-secret"
            harness.start()
            (root / "sk.token").write_text("test-sk-secret\n")
            (root / "tmds.token").write_text("test-tmds-secret\n")
            profiles = root / "targets.json"
            profiles.write_text(json.dumps({"default_target": "sk", "targets": {
                name: {"transport": "unix", "socket": str(harness.config.socket_path),
                       "token_file": f"{name}.token"} for name in ("sk", "tmds")
            }}))
            args = mcp.build_parser().parse_args(["--targets-file", str(profiles)])
            try:
                sk = mcp.handle_tool_call(args, "uart_status", {"target": "sk"}, 2, "lf")
                self.assertTrue(sk["structuredContent"]["ok"])
                self.assertEqual(sk["structuredContent"]["target"], "sk")
                denied = mcp.handle_tool_call(args, "uart_status", {"target": "tmds"}, 2, "lf")
                self.assertTrue(denied["isError"])
                harness.config.auth_token = "test-tmds-secret"
                tmds = mcp.handle_tool_call(args, "uart_status", {"target": "tmds"}, 2, "lf")
                self.assertTrue(tmds["structuredContent"]["ok"])
                self.assertNotIn("test-tmds-secret", json.dumps(tmds))

                cli = Path(__file__).resolve().parents[3] / "tools/uart/integration/cli.py"
                result = subprocess.run(
                    [sys.executable, str(cli), "--targets-file", str(profiles),
                     "--target", "tmds", "status"], capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["ok"])
            finally:
                harness.close()

    def test_token_overrides_and_missing_file_error(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            profiles = root / "targets.json"
            profiles.write_text(json.dumps({"targets": {"sk": {
                "tcp": "127.0.0.1:17001", "token_file": "profile.token",
            }}}))
            endpoint = resolve_target_endpoint("sk", profiles)
            with self.assertRaises(EndpointConfigError):
                resolve_token(endpoint)
            (root / "profile.token").write_text("profile-token")
            self.assertEqual(resolve_token(endpoint), "profile-token")
            with mock.patch.dict(os.environ, {"UARTD_TOKEN": "env-token"}):
                self.assertEqual(resolve_token(endpoint), "env-token")
                override = root / "override.token"
                override.write_text("\ufefffile-token\n", encoding="utf-8")
                self.assertEqual(resolve_token(endpoint, override), "file-token")
                with mock.patch.dict(os.environ, {"UARTD_TOKEN_FILE": str(override)}):
                    self.assertEqual(resolve_token(endpoint), "file-token")

    def test_management_tool_mapping_and_failed_port_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = DaemonHarness(Path(directory))
            harness.start()
            args = mcp.build_parser().parse_args(["--socket", str(harness.config.socket_path)])
            try:
                raw = mcp.handle_tool_call(args, "uart_send", {"text": "\u0003"}, 2, "lf")
                self.assertTrue(raw["structuredContent"]["ok"])
                self.assertEqual(harness.fake_serial.writes[-1], b"\x03")
                line = mcp.handle_tool_call(args, "uart_sendline", {"line": "help", "newline": "cr"}, 2, "lf")
                self.assertTrue(line["structuredContent"]["ok"])
                self.assertEqual(harness.fake_serial.writes[-1], b"help\r")
                baud = mcp.handle_tool_call(args, "uart_baud", {"baud": 57600}, 2, "lf")
                self.assertTrue(baud["structuredContent"]["ok"])
                self.assertEqual(harness.config.baud, 57600)
                disconnect = mcp.handle_tool_call(args, "uart_disconnect", {}, 2, "lf")
                self.assertTrue(disconnect["structuredContent"]["ok"])
                self.assertIsNone(harness.daemon.serial_port)
                port = mcp.handle_tool_call(args, "uart_set_port", {"port": "FAKE2"}, 2, "lf")
                self.assertTrue(port["structuredContent"]["ok"])
                self.assertEqual(harness.config.port, "FAKE2")
                with mock.patch.object(harness.daemon, "_open_serial", side_effect=UartDaemonError("busy")):
                    failed = mcp.handle_tool_call(args, "uart_set_port", {"port": "BUSY"}, 2, "lf")
                self.assertTrue(failed["isError"])
                self.assertEqual(harness.config.port, "FAKE2")
            finally:
                harness.close()


if __name__ == "__main__":
    unittest.main()
