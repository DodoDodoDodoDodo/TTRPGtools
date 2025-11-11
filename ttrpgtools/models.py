"""Domain models for TTRPG character management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence


class PrerequisiteError(ValueError):
    """Raised when an advance cannot be purchased."""


@dataclass(frozen=True)
class Advance:
    """Represents an advance available to a career."""

    name: str
    xp_cost: int
    page: int
    prerequisites: Sequence[str] = field(default_factory=tuple)

    def missing_prerequisites(self, owned_advances: Iterable[str]) -> List[str]:
        """Return prerequisites that are not in ``owned_advances``."""
        owned_set = {name.lower() for name in owned_advances}
        return [name for name in self.prerequisites if name.lower() not in owned_set]


@dataclass(frozen=True)
class AdvancePurchase:
    """Represents a purchased advance recorded on a character sheet."""

    name: str
    xp_cost: int
    page: int


@dataclass
class Career:
    """A career that defines a list of advances."""

    name: str
    advances: Dict[str, Advance]

    def get_advance(self, advance_name: str) -> Advance:
        try:
            return self.advances[advance_name.lower()]
        except KeyError as exc:
            raise KeyError(f"Advance '{advance_name}' not found for career '{self.name}'.") from exc

    @classmethod
    def from_advances(cls, name: str, advances: Sequence[Advance]) -> "Career":
        return cls(name=name, advances={adv.name.lower(): adv for adv in advances})


@dataclass
class Character:
    """A character with XP accounting and advance purchases."""

    name: str
    career: Career
    xp_total: int = 0
    purchases: List[AdvancePurchase] = field(default_factory=list)

    def has_advance(self, advance_name: str) -> bool:
        return any(purchase.name.lower() == advance_name.lower() for purchase in self.purchases)

    @property
    def xp_spent(self) -> int:
        return sum(purchase.xp_cost for purchase in self.purchases)

    @property
    def xp_available(self) -> int:
        return self.xp_total - self.xp_spent

    def _validate_purchase(self, advance: Advance) -> None:
        if self.has_advance(advance.name):
            raise PrerequisiteError(f"Advance '{advance.name}' has already been purchased.")

        missing = advance.missing_prerequisites(purchase.name for purchase in self.purchases)
        if missing:
            raise PrerequisiteError(
                "Missing prerequisites: " + ", ".join(missing)
            )

        if advance.xp_cost > self.xp_available:
            raise PrerequisiteError(
                f"Not enough XP. Cost: {advance.xp_cost}, available: {self.xp_available}."
            )

    def purchase_advance(self, advance_name: str, *, page_override: int | None = None) -> AdvancePurchase:
        advance = self.career.get_advance(advance_name)
        self._validate_purchase(advance)

        recorded_page = page_override if page_override is not None else advance.page
        purchase = AdvancePurchase(name=advance.name, xp_cost=advance.xp_cost, page=recorded_page)
        self.purchases.append(purchase)
        return purchase

    def to_summary(self) -> str:
        lines = [
            f"Name: {self.name}",
            f"Career: {self.career.name}",
            f"XP Total: {self.xp_total}",
            f"XP Spent: {self.xp_spent}",
            f"XP Available: {self.xp_available}",
            "Advances:",
        ]
        if not self.purchases:
            lines.append("  (none)")
        else:
            for purchase in self.purchases:
                lines.append(
                    f"  - {purchase.name} (XP {purchase.xp_cost}, page {purchase.page})"
                )
        return "\n".join(lines)


CAREERS: Dict[str, Career] = {}


def register_career(career: Career) -> None:
    CAREERS[career.name.lower()] = career


def get_career(name: str) -> Career:
    try:
        return CAREERS[name.lower()]
    except KeyError as exc:
        raise KeyError(f"Career '{name}' is not registered.") from exc


# Built-in sample careers
register_career(
    Career.from_advances(
        "Soldier",
        [
            Advance("Basic Training", xp_cost=100, page=45),
            Advance("Shield Wall", xp_cost=150, page=47, prerequisites=["Basic Training"]),
            Advance(
                "Battlefield Commander",
                xp_cost=300,
                page=52,
                prerequisites=["Shield Wall"],
            ),
        ],
    )
)

register_career(
    Career.from_advances(
        "Acolyte",
        [
            Advance("Initiate's Blessing", xp_cost=100, page=78),
            Advance(
                "Sacred Ward",
                xp_cost=200,
                page=82,
                prerequisites=["Initiate's Blessing"],
            ),
            Advance(
                "Miracle Worker",
                xp_cost=400,
                page=90,
                prerequisites=["Sacred Ward"],
            ),
        ],
    )
)
