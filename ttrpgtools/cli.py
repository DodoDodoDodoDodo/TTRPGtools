"""Command line interface for the TTRPG tools."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from .models import CAREERS, PrerequisiteError, Character, get_career
from .storage import character_from_dict, character_to_dict, load_character, save_character


def _career_list() -> str:
    lines = []
    for career in CAREERS.values():
        lines.append(f"{career.name}")
        for advance in career.advances.values():
            prereqs = ", ".join(advance.prerequisites) or "None"
            lines.append(
                f"  - {advance.name} (XP {advance.xp_cost}, page {advance.page}, prerequisites: {prereqs})"
            )
    return "\n".join(lines)


def _load_character_or_exit(path: str | Path):
    try:
        return load_character(path)
    except FileNotFoundError:
        raise SystemExit(f"Character file '{path}' does not exist.")
    except Exception as exc:  # pragma: no cover - defensive path
        raise SystemExit(f"Could not load character: {exc}") from exc


def _save_character_or_exit(character, path: str | Path) -> None:
    try:
        save_character(character, path)
    except Exception as exc:  # pragma: no cover - defensive path
        raise SystemExit(f"Could not save character: {exc}") from exc


def cmd_new(args: argparse.Namespace) -> None:
    career = get_career(args.career)
    character = Character(name=args.name, career=career, xp_total=args.xp)
    if args.output:
        _save_character_or_exit(character, args.output)
    print(character.to_summary())


def cmd_buy_advance(args: argparse.Namespace) -> None:
    character = _load_character_or_exit(args.file)
    try:
        purchase = character.purchase_advance(args.advance, page_override=args.page)
    except PrerequisiteError as exc:
        raise SystemExit(str(exc))
    _save_character_or_exit(character, args.file)
    print(
        f"Purchased {purchase.name} for {purchase.xp_cost} XP (page {purchase.page}). XP remaining: {character.xp_available}."
    )


def cmd_list(args: argparse.Namespace) -> None:  # noqa: ARG001 - argparse API
    print(_career_list())


def cmd_show(args: argparse.Namespace) -> None:
    character = _load_character_or_exit(args.file)
    print(character.to_summary())


def cmd_save(args: argparse.Namespace) -> None:
    character_data = json.load(sys.stdin) if args.stdin else json.loads(Path(args.source).read_text())
    character = character_from_dict(character_data)
    _save_character_or_exit(character, args.file)
    print(f"Character saved to {args.file}.")


def cmd_load(args: argparse.Namespace) -> None:
    character = _load_character_or_exit(args.file)
    if args.json:
        print(json.dumps(character_to_dict(character), indent=2))
    else:
        print(character.to_summary())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tools for managing TTRPG characters.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="Create a new character")
    new_parser.add_argument("--name", required=True, help="Character name")
    new_parser.add_argument("--career", required=True, help="Career name")
    new_parser.add_argument("--xp", type=int, default=0, help="Total XP available")
    new_parser.add_argument("--output", help="File path to save the new character")
    new_parser.set_defaults(func=cmd_new)

    buy_parser = subparsers.add_parser("buy-advance", help="Purchase an advance")
    buy_parser.add_argument("--file", required=True, help="Character file path")
    buy_parser.add_argument("--advance", required=True, help="Advance name to purchase")
    buy_parser.add_argument("--page", type=int, help="Override rulebook page number")
    buy_parser.set_defaults(func=cmd_buy_advance)

    list_parser = subparsers.add_parser("list", help="List careers and advances")
    list_parser.set_defaults(func=cmd_list)

    show_parser = subparsers.add_parser("show", help="Display a character summary")
    show_parser.add_argument("--file", required=True, help="Character file path")
    show_parser.set_defaults(func=cmd_show)

    save_parser = subparsers.add_parser("save", help="Save character data to a file")
    save_parser.add_argument("--file", required=True, help="Destination file path")
    group = save_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", help="Path to a JSON document describing the character")
    group.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSON from stdin",
    )
    save_parser.set_defaults(func=cmd_save)

    load_parser = subparsers.add_parser("load", help="Load a character file")
    load_parser.add_argument("--file", required=True, help="Character file path")
    load_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the character as raw JSON instead of a summary",
    )
    load_parser.set_defaults(func=cmd_load)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
