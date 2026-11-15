import argparse
import json
import sys

from .discover import DiscoveryError, discover
from .ucp import UcpError, brief, search


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="poppy-agent", description="Unofficial Poppy client")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover", help="show what a business publishes for agents")
    d.add_argument("domain")
    d.add_argument("--json", action="store_true", help="print raw poppy.json")
    s = sub.add_parser("search", help="search a shop's catalog (signed out, read only)")
    s.add_argument("domain")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--json", action="store_true", help="raw response")
    sub.add_parser("mcp", help="run the MCP server on stdio (read-only tools)")
    args = p.parse_args(argv)

    if args.cmd == "mcp":
        from .mcp_server import serve

        serve()
        return 0

    if args.cmd == "search":
        try:
            res = search(args.domain, args.query, args.limit)
            print(json.dumps(res, indent=2) if args.json else brief(res))
        except (DiscoveryError, UcpError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        return 0

    try:
        result = discover(args.domain)
    except DiscoveryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result.poppy, indent=2) if args.json else result.summary())
    return 0 if not result.problems else 2


if __name__ == "__main__":
    sys.exit(main())
