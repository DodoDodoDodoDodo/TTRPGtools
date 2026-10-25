"""Who may delete a character, the same in every game (Dodo, 2026-10-25): its own player, and takahe for any."""

from flask import abort, request

#: may delete anyone's character; everyone else only their own (characters without an owner: only these)
DELETE_ANY = {"takahe"}


def may_delete(owner: str | None) -> bool:
    user = request.headers.get("Remote-User")
    return bool(user) and (user in DELETE_ANY or (owner is not None and owner == user))


def require_delete(owner: str | None) -> None:
    if not may_delete(owner):
        abort(403, "Only the character's player can delete it.")
