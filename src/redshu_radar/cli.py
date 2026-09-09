import argparse
from collections.abc import Sequence

from redshu_radar import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="redshu-radar")
    parser.add_argument(
        "--version",
        action="version",
        version=f"redshu-radar {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    return 0
