from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import tools.uart.uart_mcp_server as uart_mcp_server
from tests.tools.uart.test_uartd import DaemonHarness


class UartMcpServerTests(unittest.TestCase):
    def test_detect_state_hint(self) -> None:
        self.assertEqual(uart_mcp_server.detect_state_hint('=> '), 'uboot')
        self.assertEqual(uart_mcp_server.detect_state_hint('root@board:~# '), 'linux_root')
        self.assertEqual(uart_mcp_server.detect_state_hint('login: '), 'linux_login')

    def test_uart_tail_and_command_mapping(self) -> None:
        with TemporaryDirectory(prefix='uart-mcp-') as temp_dir:
            harness = DaemonHarness(Path(temp_dir))
            harness.start()
            try:
                harness.fake_serial.read_queue.put(b'U-Boot SPL 2026.01\r\n=> ')
                client = uart_mcp_server.UartdClient(harness.config.socket_path)

                tail_result = uart_mcp_server.handle_tool_call(client, 'uart_tail', {'lines': 20}, 5.0, 'crlf')
                structured_tail = tail_result['structuredContent']
                self.assertTrue(structured_tail['ok'])
                self.assertEqual(structured_tail['state_hint'], 'uboot')

                def delayed_command_output() -> None:
                    import time
                    time.sleep(0.2)
                    harness.fake_serial.read_queue.put(b'printenv\r\nbootcmd=run mmcboot\r\n=> ')

                import threading
                thread = threading.Thread(target=delayed_command_output, daemon=True)
                thread.start()
                command_result = uart_mcp_server.handle_tool_call(
                    client,
                    'uart_command',
                    {'line': 'printenv', 'expect': '=> ', 'timeout': 2, 'newline': 'crlf'},
                    5.0,
                    'crlf',
                )
                structured_command = command_result['structuredContent']
                self.assertTrue(structured_command['ok'])
                self.assertIn('bootcmd=run mmcboot', structured_command['output'])
                self.assertEqual(structured_command['state_hint'], 'uboot')
                thread.join(timeout=1)
            finally:
                harness.close()

    def test_mcp_stdio_initialize_list_and_call(self) -> None:
        with TemporaryDirectory(prefix='uart-mcp-stdio-') as temp_dir:
            harness = DaemonHarness(Path(temp_dir))
            harness.start()
            try:
                harness.fake_serial.read_queue.put(b'login: ')
                proc = subprocess.Popen(
                    [
                        'python3',
                        '/home/nstel/ti/TI_Bringup/tools/uart/uart-mcp-server.py',
                        '--socket',
                        str(harness.config.socket_path),
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                try:
                    self._send_mcp(proc, {
                        'jsonrpc': '2.0',
                        'id': 1,
                        'method': 'initialize',
                        'params': {},
                    })
                    init = self._recv_mcp(proc)
                    self.assertEqual(init['result']['serverInfo']['name'], 'uart')

                    self._send_mcp(proc, {
                        'jsonrpc': '2.0',
                        'id': 2,
                        'method': 'tools/list',
                        'params': {},
                    })
                    tools = self._recv_mcp(proc)
                    tool_names = {item['name'] for item in tools['result']['tools']}
                    self.assertIn('uart_tail', tool_names)
                    self.assertIn('uart_command', tool_names)

                    self._send_mcp(proc, {
                        'jsonrpc': '2.0',
                        'id': 3,
                        'method': 'tools/call',
                        'params': {'name': 'uart_tail', 'arguments': {'lines': 20}},
                    })
                    call = self._recv_mcp(proc)
                    structured = call['result']['structuredContent']
                    self.assertTrue(structured['ok'])
                    self.assertEqual(structured['state_hint'], 'linux_login')
                finally:
                    proc.terminate()
                    proc.communicate(timeout=5)
            finally:
                harness.close()

    def _send_mcp(self, proc: subprocess.Popen, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        assert proc.stdin is not None
        proc.stdin.write(f'Content-Length: {len(body)}\r\n\r\n'.encode('utf-8'))
        proc.stdin.write(body)
        proc.stdin.flush()

    def _recv_mcp(self, proc: subprocess.Popen) -> dict:
        assert proc.stdout is not None
        headers = {}
        while True:
            line = proc.stdout.readline()
            if not line:
                raise AssertionError('MCP server closed stdout unexpectedly')
            if line in {b'\r\n', b'\n'}:
                break
            name, value = line.decode('utf-8').split(':', 1)
            headers[name.strip().lower()] = value.strip()
        length = int(headers['content-length'])
        body = proc.stdout.read(length)
        return json.loads(body.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
