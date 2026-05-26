#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

from uart_expect import main


DEFAULT_RUNTIME_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "runtime_log"


def build_agent_argv(argv: list[str]) -> list[str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--runtime-log",
        default=str(DEFAULT_RUNTIME_LOG_PATH),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-runtime-log",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args, remaining = parser.parse_known_args(argv[1:])

    has_log_flag = any(item == "--log" or item.startswith("--log=") for item in remaining)
    has_runtime_tee_flag = any(
        item == "--tee-runtime-log"
        or item == "--runtime-log-path"
        or item.startswith("--runtime-log-path=")
        for item in remaining
    )

    final_argv = [argv[0], *remaining]
    if not args.no_runtime_log and not has_log_flag and not has_runtime_tee_flag:
        final_argv.extend([
            "--tee-runtime-log",
            "--runtime-log-path",
            args.runtime_log,
        ])

    return final_argv


if __name__ == "__main__":
    sys.argv = build_agent_argv(sys.argv)
    raise SystemExit(main())
