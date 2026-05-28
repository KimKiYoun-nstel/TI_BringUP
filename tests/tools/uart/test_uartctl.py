from __future__ import annotations

import unittest

import tools.uart.uartctl as uartctl


class UartCtlParserTests(unittest.TestCase):
    def test_parser_supports_attach_watch_and_command(self) -> None:
        parser = uartctl.build_parser()

        attach_args = parser.parse_args(["attach", "--backlog-lines", "10"])
        self.assertEqual(attach_args.command, "attach")
        self.assertEqual(attach_args.backlog_lines, 10)

        watch_args = parser.parse_args(["watch", "--backlog-lines", "20"])
        self.assertEqual(watch_args.command, "watch")
        self.assertEqual(watch_args.backlog_lines, 20)

        command_args = parser.parse_args(["command", "version", "--expect", "=> ", "--fresh"])
        self.assertEqual(command_args.command, "command")
        self.assertEqual(command_args.text, "version")
        self.assertEqual(command_args.expect, "=> ")
        self.assertTrue(command_args.fresh)


if __name__ == "__main__":
    unittest.main()
