"""Utility for tweaking generated character JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

CharacterPayload = Dict[str, Any]


def _load(path: Path) -> CharacterPayload:
    return json.loads(path.read_text())


def _save(data: CharacterPayload, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def _ensure_xp_available(data: CharacterPayload) -> None:
    xp_block = data.setdefault("xp", {})
    total = int(xp_block.get("total", 0))
    spent = int(xp_block.get("spent", 0))
    xp_block["available"] = total - spent


def _set_skill(data: CharacterPayload, spec: str) -> None:
    if "=" not in spec:
        raise ValueError("Skill specification must look like 'Skill Name=Status'.")
    name, status = [part.strip() for part in spec.split("=", 1)]
    if not name:
        raise ValueError("Skill name cannot be empty.")
    if not status:
        raise ValueError("Skill status cannot be empty.")

    skills: List[Dict[str, Any]] = data.setdefault("skills", [])
    for skill in skills:
        if skill.get("name", "").lower() == name.lower():
            skill["status"] = status
            break
    else:
        skills.append({"name": name, "status": status})


def _remove_action(data: CharacterPayload, name: str) -> bool:
    actions: List[Dict[str, Any]] = data.get("actions", [])
    original_len = len(actions)
    data["actions"] = [action for action in actions if action.get("name", "").lower() != name.lower()]
    return len(data["actions"]) != original_len


def _add_action(data: CharacterPayload, spec: str) -> None:
    parts = [part.strip() for part in spec.split("|") if part.strip()]
    if len(parts) < 3:
        raise ValueError("Action spec must be 'Name|Type|Description' with optional '|keyword1,keyword2'.")
    name, action_type, description = parts[:3]
    keywords: List[str] = []
    if len(parts) > 3:
        keywords = [kw.strip() for kw in parts[3].split(",") if kw.strip()]

    actions: List[Dict[str, Any]] = data.setdefault("actions", [])
    actions.append(
        {
            "name": name,
            "type": action_type,
            "description": description,
            "keywords": keywords,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Modify a generated character JSON file.")
    parser.add_argument("file", type=Path, help="Character JSON file to modify")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. If omitted the input file is modified in place.",
    )
    parser.add_argument("--set-xp-total", type=int, help="Set the character's total XP")
    parser.add_argument("--set-xp-spent", type=int, help="Set the character's spent XP")
    parser.add_argument(
        "--set-skill",
        action="append",
        default=[],
        metavar="NAME=STATUS",
        help="Update a skill entry, e.g. 'Dodge=+10'. New skills are created if needed.",
    )
    parser.add_argument(
        "--add-action",
        action="append",
        default=[],
        metavar="NAME|TYPE|DESCRIPTION[|keywords]",
        help="Append an action. Example: 'Hunker Down|Half Action|Gain +20 to cover saves|Defensive,Utility'",
    )
    parser.add_argument(
        "--remove-action",
        action="append",
        default=[],
        metavar="NAME",
        help="Remove an action by name (case-insensitive).",
    )
    return parser


def apply_changes(data: CharacterPayload, args: argparse.Namespace) -> List[str]:
    messages: List[str] = []

    if args.set_xp_total is not None:
        data.setdefault("xp", {})["total"] = args.set_xp_total
        messages.append(f"XP total set to {args.set_xp_total}.")
    if args.set_xp_spent is not None:
        data.setdefault("xp", {})["spent"] = args.set_xp_spent
        messages.append(f"XP spent set to {args.set_xp_spent}.")

    for skill_spec in args.set_skill:
        _set_skill(data, skill_spec)
        messages.append(f"Skill updated: {skill_spec}.")

    for action_spec in args.add_action:
        _add_action(data, action_spec)
        messages.append(f"Action added: {action_spec.split('|', 1)[0].strip()}.")

    for name in args.remove_action:
        removed = _remove_action(data, name)
        if removed:
            messages.append(f"Action removed: {name}.")
        else:
            messages.append(f"No action named '{name}' found.")

    _ensure_xp_available(data)
    return messages


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    payload = _load(args.file)
    messages = apply_changes(payload, args)

    output_path = args.output or args.file
    _save(payload, output_path)

    print(f"Character saved to {output_path}.")
    for message in messages:
        print(f" - {message}")

    print("Updated actions list:")
    for action in payload.get("actions", []):
        print(f" * {action['name']} ({action.get('type', 'Unknown')}): {action.get('description', 'No description')}")


if __name__ == "__main__":
    main()
