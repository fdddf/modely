"""CLI entrypoint for modely."""

from __future__ import annotations

from .handlers import dispatch
from .parser import build_parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args, parser=parser)
