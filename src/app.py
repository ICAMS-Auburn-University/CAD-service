from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from config import Settings
from workflow import run_and_dump_json


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split CAD files into parts and upload them to Supabase Storage."
    )
    parser.add_argument("--userid", required=True, help="User identifier for the storage path.")
    parser.add_argument("--orderid", required=True, help="Order identifier for the storage path.")
    parser.add_argument("--input", required=True, help="Path to the input CAD file.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging for debugging purposes.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        settings = Settings.from_env()
        json_payload = run_and_dump_json(args.userid, args.orderid, args.input, settings)
        print(json_payload)
    except Exception as exc:
        logging.getLogger("app").exception("Job failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
