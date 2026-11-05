#!/usr/bin/env python3
"""uartTool client with TI_Bringup target profiles and token resolution."""
import sys

if __package__:
    from .distribution import uart_api, load_module
    from . import endpoint as uart_endpoint
else:
    from distribution import uart_api, load_module
    import endpoint as uart_endpoint

client = load_module("uartctl")

_build_parser = client.build_parser


def build_parser():
    parser = _build_parser()
    parser.add_argument("--target", default=None, help="Board name from targets.json")
    parser.add_argument("--targets-file", default=str(uart_endpoint.DEFAULT_TARGETS_FILE))
    return parser


def endpoint_from_args(args):
    try:
        endpoint = uart_endpoint.endpoint_from_options(
            tcp=args.tcp, socket_path=args.socket, target=args.target,
            targets_file=args.targets_file,
        )
        token = uart_endpoint.resolve_token(endpoint, token_file=args.token_file)
        return client.Endpoint(
            kind=endpoint.kind, host=endpoint.host, port=endpoint.port,
            socket_path=endpoint.socket_path, token=token,
            response_timeout=args.response_timeout,
        )
    except uart_endpoint.EndpointConfigError as exc:
        raise client.UartCtlError(str(exc)) from exc


client.build_parser = build_parser
client.endpoint_from_args = endpoint_from_args

if __name__ == "__main__":
    try:
        raise SystemExit(client.main())
    except uart_api.UARTAPIError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
