import argparse
import json
import sys

from .discover import DiscoveryError, discover


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="poppy-agent", description="Unofficial Poppy client")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover", help="show what a business publishes for agents")
    d.add_argument("domain")
    d.add_argument("--json", action="store_true", help="print raw poppy.json")
    args = p.parse_args(argv)

    try:
        result = discover(args.domain)
    except DiscoveryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result.poppy, indent=2) if args.json else result.summary())
    return 0 if not result.problems else 2


if __name__ == "__main__":
    sys.exit(main())
