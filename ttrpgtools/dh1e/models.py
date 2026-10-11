"""Domain models for DH1e character management.

Careers are loaded from the real rulebook data in ``database/career_advances.json``,
``database/career_ranks.json``, and ``database/career_characteristic_advances.json``
(see ``ttrpgtools/career_scheme_parser.py``) rather than a flat, career-agnostic
advance pool -- a character can only purchase advances that actually appear on
their own career's table, at a rank they've actually reached.

Rank charts are real trees, not just XP thresholds
---------------------------------------------------
``database/career_ranks.json`` is a hand-verified, per-career tree (each rank
lists its ``previous``/``next`` rank(s) and an ``xp_range``) -- this is the
authoritative source for rank structure. A career's ranks form a branching path:
most ranks have exactly one ``next``, but at some ranks a player must choose
between several -- e.g. Tech-Priest's "Tech-Priest" rank branches into
"Technomancer" or "Mech-Deacon". Sibling ranks (same parent) are mutually
exclusive alternatives, NOT simply "any rank at the same XP threshold" -- two
ranks can share a threshold without being reachable from the same parent (e.g.
Guardsman's "Shock Trooper"/"Captain"/"Marksman" all sit at the same XP tier but
are three unrelated, already-committed continuations of three different
tier-3 branches, not a three-way choice at that tier).

A character's ``career_path`` (see ``Character``) records the ordered sequence of
ranks actually chosen/reached, starting from the career's single root rank.
Advances can only be purchased from ranks already in ``career_path`` -- this is
what actually enforces "no buying Rank-5 talents without having gotten there".

Some ranks have zero recoverable advances (their table didn't survive text
extraction at all, e.g. Tech-Priest's "Mech-Wright") -- they still exist as real
path steps with nothing purchasable, rather than being silently dropped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from dataclasses import replace as dataclasses_replace
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

_DATABASE_DIR = Path(__file__).resolve().parent / "database"
_ADVANCES_PATH = _DATABASE_DIR / "career_advances.json"
_RANKS_PATH = _DATABASE_DIR / "career_ranks.json"
_CHARACTERISTIC_COSTS_PATH = _DATABASE_DIR / "career_characteristic_advances.json"


def _slugify_career(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _rank_key(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


CHARACTERISTIC_TIERS: Sequence[str] = ("simple", "intermediate", "trained", "expert")

#: Maps the short codes used in prerequisite text (e.g. "BS 40") to the full
#: characteristic names used on a character sheet.
CHARACTERISTIC_SHORT_CODES: Dict[str, str] = {
    "ws": "Weapon Skill",
    "bs": "Ballistic Skill",
    "s": "Strength",
    "t": "Toughness",
    "ag": "Agility",
    "int": "Intelligence",
    "per": "Perception",
    "wp": "Willpower",
    "fel": "Fellowship",
}

_CHARACTERISTIC_PREREQ = re.compile(
    r"^(WS|BS|Ag|Int|Per|WP|Fel|S|T)\s+(\d+)$", re.IGNORECASE
)

#: Per-tier free power grants from the core rulebook's "PSY RATING N" talent
#: text -- (grants_minor, grants_discipline, forced_choice) where forced_choice
#: is "new" (must pick a new discipline, gain 1 power from it) or None (player
#: chooses between "known" -- gain N powers from any discipline(s) already
#: known -- or "new", for tiers 4+). N for minor/discipline counts is
#: ceil(Willpower Bonus / 2), computed at purchase time -- "if your WP bonus
#: later increases, you do not retroactively gain additional powers" (verbatim).
_PSY_RATING_GRANTS: Dict[int, tuple[bool, bool, str | None]] = {
    1: (True, False, None),
    2: (True, False, None),
    3: (True, True, "new"),
    4: (True, True, None),  # "known" OR "new" -- player's choice
    5: (False, True, None),
    6: (True, True, None),
}

_PSY_RATING_ADVANCE = re.compile(r"^Psy Rating (\d+)$")


def psy_rating_grant_info(rating: int) -> tuple[bool, bool, str | None]:
    """(grants_minor, grants_discipline, forced_choice) for a Psy Rating tier --
    see ``Character.purchase_psy_rating``. Ranges outside 1-6 grant nothing."""
    return _PSY_RATING_GRANTS.get(rating, (False, False, None))


def psy_rating_tier(advance_name: str) -> int | None:
    """The tier number if ``advance_name`` is a "Psy Rating N" advance, else
    None -- lets callers (e.g. the web GUI) route it through
    ``Character.purchase_psy_rating`` instead of a plain purchase."""
    match = _PSY_RATING_ADVANCE.match(advance_name)
    return int(match.group(1)) if match else None


class PrerequisiteError(ValueError):
    """Raised when an advance or characteristic increase cannot be purchased."""


@dataclass(frozen=True)
class RankAdvance:
    """A skill or talent advance available to a career, generally at one specific
    rank -- except a handful of generic "pick a specific X" slots (Minor Psychic
    Power, Psychic Power, ...) that recur verbatim across several ranks, each
    occurrence a genuinely separate purchasable slot rather than a duplicate.
    ``rank``/``cost`` reflect the cheapest/earliest occurrence (for display and
    XP cost); ``available_ranks`` lists every rank it can be bought from."""

    name: str
    cost: int
    type: str  # "advance" or "talent"
    prerequisites: Sequence[str] = field(default_factory=tuple)
    repeatable: bool = False
    rank: str = ""
    available_ranks: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CharacteristicCost:
    """Cumulative XP cost to raise one characteristic through DH1e's four tiers."""

    characteristic: str
    tier_costs: Dict[str, int | None]  # tier name -> cost, or None when unavailable

    def cost_for(self, tier: str) -> int | None:
        return self.tier_costs[tier.lower()]


@dataclass
class Career:
    """A DH1e career: its per-rank advance tables, rank tree, and
    characteristic-advance costs."""

    name: str
    advances: Dict[str, RankAdvance]
    characteristic_costs: Dict[str, CharacteristicCost]
    rank_previous: Dict[str, List[str]] = field(default_factory=dict)
    rank_next: Dict[str, List[str]] = field(default_factory=dict)
    rank_xp_range: Dict[str, Tuple[int, int]] = field(default_factory=dict)

    def get_advance(self, advance_name: str) -> RankAdvance:
        try:
            return self.advances[advance_name.lower()]
        except KeyError as exc:
            raise KeyError(
                f"Advance '{advance_name}' is not on career '{self.name}''s advance table."
            ) from exc

    def get_characteristic_cost(self, characteristic: str) -> CharacteristicCost:
        try:
            return self.characteristic_costs[characteristic.lower()]
        except KeyError as exc:
            raise KeyError(
                f"Characteristic '{characteristic}' is not tracked for career '{self.name}'."
            ) from exc

    def root_ranks(self) -> List[str]:
        """Ranks with no prerequisite rank -- where every character starts."""
        return [rank for rank, previous in self.rank_previous.items() if not previous]

    def rank_sort_key(self, rank: str) -> tuple[bool, int]:
        """Sort key for ordering ranks by XP threshold; unknown-threshold ranks
        (data the rulebook text didn't preserve cleanly) sort last."""
        xp_range = self.rank_xp_range.get(rank)
        return (xp_range is None, xp_range[0] if xp_range else 0)

    def sibling_ranks(self, rank: str) -> List[str]:
        """Other ranks reachable from the same parent(s) as ``rank`` -- the real
        branch alternatives a player chooses between, not just ranks that happen
        to share an XP tier (two ranks can share a tier without being reachable
        from the same parent -- see the module docstring)."""
        siblings: set[str] = set()
        for parent in self.rank_previous.get(rank, []):
            siblings.update(self.rank_next.get(parent, []))
        siblings.discard(rank)
        return sorted(siblings)

    @classmethod
    def from_data(
        cls,
        name: str,
        advance_rows: Iterable[dict],
        characteristic_rows: Iterable[dict],
        rank_tree: dict | None = None,
    ) -> "Career":
        rank_tree = rank_tree or {}
        slug_to_name = {slug: info["name"] for slug, info in rank_tree.items()}
        rank_previous = {
            info["name"]: [slug_to_name[p] for p in info.get("previous", []) if p in slug_to_name]
            for info in rank_tree.values()
        }
        rank_next = {
            info["name"]: [slug_to_name[n] for n in info.get("next", []) if n in slug_to_name]
            for info in rank_tree.values()
        }
        rank_xp_range = {
            info["name"]: tuple(info["xp_range"]) for info in rank_tree.values() if info.get("xp_range")
        }

        # The advance-table heading walk and the hand-authored rank tree read the
        # same rank names through two different lenses (OCR'd table headings vs.
        # a clean source) and don't always agree on punctuation/spacing (e.g.
        # "Cyber Seer" vs "Cyber-Seer"). Remap each advance row's rank onto its
        # tree equivalent via normalised-letters-only matching so purchase-gating
        # (which keys off the tree's rank names) actually recognises them; a row
        # whose rank can't be matched keeps its original name and simply won't be
        # reachable via career_path (better than silently dropping the advance).
        tree_keys = {_rank_key(rank_name): rank_name for rank_name in rank_previous}

        def canonical_rank(raw: str) -> str:
            key = _rank_key(raw)
            if key in tree_keys:
                return tree_keys[key]
            for other_key, rank_name in tree_keys.items():
                if key and (key in other_key or other_key in key):
                    return rank_name
            return raw

        def rank_depth(rank: str) -> int:
            xp_range = rank_xp_range.get(rank)
            return xp_range[0] if xp_range else 10**9

        advances: Dict[str, RankAdvance] = {}
        for row in advance_rows:
            rank = canonical_rank(row.get("rank", ""))
            existing = advances.get(row["name"].lower())
            if existing is None:
                advances[row["name"].lower()] = RankAdvance(
                    name=row["name"],
                    cost=row["cost"],
                    type=row["type"],
                    prerequisites=tuple(row.get("prerequisites", [])),
                    repeatable=row.get("repeatable", False),
                    rank=rank,
                    available_ranks=(rank,),
                )
                continue
            # The same name recurring across ranks is usually a duplicate listing
            # (e.g. re-printed after a page break) -- but for a handful of generic
            # "pick a specific X" slots (Minor Psychic Power, Psychic Power, ...)
            # each occurrence is a genuinely separate purchasable slot, available
            # again at each rank it's listed at. Union rather than overwrite:
            # cheapest/lowest-tier occurrence wins for display cost, repeatable
            # is true if ANY occurrence says so, and every rank it appears at
            # becomes a place it can be bought from.
            available_ranks = existing.available_ranks + (rank,) if rank not in existing.available_ranks else existing.available_ranks
            repeatable = existing.repeatable or row.get("repeatable", False)
            if rank_depth(rank) < rank_depth(existing.rank):
                advances[row["name"].lower()] = RankAdvance(
                    name=row["name"],
                    cost=row["cost"],
                    type=row["type"],
                    prerequisites=tuple(row.get("prerequisites", [])),
                    repeatable=repeatable,
                    rank=rank,
                    available_ranks=available_ranks,
                )
            else:
                advances[row["name"].lower()] = dataclasses_replace(
                    existing, repeatable=repeatable, available_ranks=available_ranks
                )

        characteristic_costs = {
            row["characteristic"].lower(): CharacteristicCost(
                characteristic=row["characteristic"],
                tier_costs={tier: (None if row[tier] == "N/A" else row[tier]) for tier in CHARACTERISTIC_TIERS},
            )
            for row in characteristic_rows
        }
        return cls(
            name=name,
            advances=advances,
            characteristic_costs=characteristic_costs,
            rank_previous=rank_previous,
            rank_next=rank_next,
            rank_xp_range=rank_xp_range,
        )


def _load_careers(
    advances_path: Path = _ADVANCES_PATH,
    characteristic_costs_path: Path = _CHARACTERISTIC_COSTS_PATH,
    ranks_path: Path = _RANKS_PATH,
) -> Dict[str, Career]:
    if not advances_path.exists() or not characteristic_costs_path.exists():
        return {}

    advance_rows = json.loads(advances_path.read_text())
    characteristic_rows = json.loads(characteristic_costs_path.read_text())
    rank_trees_by_slug = json.loads(ranks_path.read_text()) if ranks_path.exists() else {}

    advances_by_career: Dict[str, list] = {}
    for row in advance_rows:
        advances_by_career.setdefault(row["career"], []).append(row)

    characteristics_by_career: Dict[str, list] = {}
    for row in characteristic_rows:
        characteristics_by_career.setdefault(row["career"], []).append(row)

    return {
        career_name.lower(): Career.from_data(
            career_name,
            advances_by_career.get(career_name, []),
            rows,
            rank_trees_by_slug.get(_slugify_career(career_name), {}).get("ranks", {}),
        )
        for career_name, rows in characteristics_by_career.items()
    }


CAREERS: Dict[str, Career] = _load_careers()


def register_career(career: Career) -> None:
    CAREERS[career.name.lower()] = career


def get_career(name: str) -> Career:
    try:
        return CAREERS[name.lower()]
    except KeyError as exc:
        raise KeyError(f"Career '{name}' is not registered.") from exc


@dataclass(frozen=True)
class AdvancePurchase:
    """A single entry in a character's purchase history, in the order it was bought.

    ``direct`` marks an entry that was appended without going through
    ``purchase_advance``/``purchase_characteristic_advance`` (a free Psy Rating
    power grant, or an unchecked import via ``add_advance_unchecked``) -- on
    reload, ``storage.character_from_dict`` must replay these by direct append
    too, not by re-running the normal purchase path (which would re-validate
    rank-gating they were deliberately exempted from, or re-charge XP that was
    actually free).
    """

    name: str
    xp_cost: int
    type: str  # "advance", "talent", or "characteristic"
    order: int
    direct: bool = False


@dataclass(frozen=True)
class Wounds:
    current: int
    max: int


@dataclass(frozen=True)
class FatePoints:
    current: int
    max: int


@dataclass
class Character:
    """A DH1e character: characteristics, XP accounting, and purchase history."""

    name: str
    career: Career
    characteristics: Dict[str, int] = field(default_factory=dict)
    xp_total: int = 0
    wounds: Wounds | None = None
    fate_points: FatePoints | None = None
    insanity_points: int = 0
    corruption_points: int = 0
    homeworld: str | None = None
    divination: str | None = None
    equipment: List[str] = field(default_factory=list)
    armour: Dict[str, dict] = field(default_factory=dict)
    advance_history: List[AdvancePurchase] = field(default_factory=list)
    career_path: List[str] = field(default_factory=list)
    known_disciplines: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.career_path:
            roots = self.career.root_ranks()
            if len(roots) == 1:
                self.career_path = [roots[0]]

    @property
    def current_rank(self) -> str:
        """The deepest rank in ``career_path`` -- the last one actually chosen."""
        return self.career_path[-1] if self.career_path else ""

    def available_next_ranks(self) -> List[str]:
        """Ranks reachable from the current rank whose XP threshold is met --
        what a "choose your next rank" dropdown should offer. Empty once a
        terminal rank is reached, or if total XP hasn't hit the next tier yet."""
        if not self.career_path:
            return []
        candidates = self.career.rank_next.get(self.current_rank, [])
        return [
            rank
            for rank in candidates
            if (self.career.rank_xp_range.get(rank) or (0, 0))[0] <= self.xp_total
        ]

    def advance_to_rank(self, rank_name: str) -> None:
        """Commit to one of ``available_next_ranks()`` -- a DH1e rank-up choice.
        Free (ranks aren't purchased with XP; reaching the threshold is enough),
        but permanent: the sibling ranks not chosen become unreachable."""
        options = self.available_next_ranks()
        if rank_name not in options:
            raise PrerequisiteError(
                f"'{rank_name}' is not reachable from '{self.current_rank}' right now "
                f"(options: {', '.join(options) or 'none'})."
            )
        self.career_path.append(rank_name)

    @property
    def talents(self) -> List[str]:
        """Talent names purchased so far, derived from the purchase history."""
        return [purchase.name for purchase in self.advance_history if purchase.type == "talent"]

    @property
    def skill_advances(self) -> List[str]:
        """Skill advance names purchased so far, derived from the purchase history."""
        return [purchase.name for purchase in self.advance_history if purchase.type == "advance"]

    def has_advance(self, advance_name: str) -> bool:
        return any(purchase.name.lower() == advance_name.lower() for purchase in self.advance_history)

    def _purchase_count(self, advance_name: str) -> int:
        """Count purchases of ``advance_name``, including ones recorded with a
        choice suffix (e.g. "Minor Psychic Power (Healer)") -- see
        ``purchase_advance``'s ``choice`` parameter."""
        prefix = advance_name.lower()
        return sum(
            1
            for purchase in self.advance_history
            if purchase.name.lower() == prefix or purchase.name.lower().startswith(prefix + " (")
        )

    @property
    def xp_spent(self) -> int:
        return sum(purchase.xp_cost for purchase in self.advance_history)

    @property
    def xp_available(self) -> int:
        return self.xp_total - self.xp_spent

    def _owned_tiers(self, characteristic: str) -> int:
        return sum(
            1
            for purchase in self.advance_history
            if purchase.type == "characteristic" and purchase.name.rsplit(" ", 1)[0] == characteristic
        )

    def effective_characteristic(self, characteristic: str) -> int:
        """The characteristic's current value: its base (rolled/edited) value plus
        +5 for every tier of Characteristic Advance purchased so far.

        Purchased tiers are derived from ``advance_history`` rather than stored
        directly on ``characteristics`` -- that dict holds only the base value, so
        reloading a saved character (which replays its history) can't double-apply
        the same +5 bump on top of an already-bumped stored value.
        """
        return self.characteristics.get(characteristic, 0) + 5 * self._owned_tiers(characteristic)

    def characteristic_bonus(self, characteristic: str) -> int:
        """The tens digit of the effective characteristic -- what DH1e actually
        rolls tests and derived stats (Fatigue, Movement, ...) against."""
        return self.effective_characteristic(characteristic) // 10

    @property
    def effective_wounds_max(self) -> int:
        """Stored ``wounds.max`` is the one-time chargen roll (base); DH1e's only
        post-chargen source of extra Wounds is the "Sound Constitution" talent
        (+1 Wound per purchase) -- there's no Toughness->Wounds formula in the
        raw rules, so Toughness changes deliberately don't affect this."""
        base = self.wounds.max if self.wounds else 0
        bonus = sum(1 for p in self.advance_history if p.name.lower() == "sound constitution")
        return base + bonus

    @property
    def fatigue_threshold(self) -> int:
        """Toughness Bonus -- how many levels of Fatigue a character can take
        before collapsing unconscious (core rulebook: "A character can take a
        number of levels of Fatigue equal to his Toughness Bonus"). Always
        computed live from current characteristics, never stored."""
        return self.characteristic_bonus("Toughness")

    @property
    def movement(self) -> Dict[str, int]:
        """Half/Full/Charge/Run movement in metres, derived from Agility Bonus.
        Always computed live, never stored."""
        agility_bonus = self.characteristic_bonus("Agility")
        return {
            "half": agility_bonus,
            "full": agility_bonus * 2,
            "charge": agility_bonus * 3,
            "run": agility_bonus * 6,
        }

    def missing_prerequisites(self, prerequisites: Sequence[str]) -> List[str]:
        """Return prerequisites the character doesn't meet.

        Each prerequisite is either a characteristic threshold (e.g. "BS 40") or
        the name of a previously-purchased advance/talent.
        """
        owned = {purchase.name.lower() for purchase in self.advance_history}
        missing = []
        for prerequisite in prerequisites:
            match = _CHARACTERISTIC_PREREQ.match(prerequisite.strip())
            if match:
                code, threshold = match.groups()
                full_name = CHARACTERISTIC_SHORT_CODES[code.lower()]
                if self.effective_characteristic(full_name) < int(threshold):
                    missing.append(prerequisite)
                continue
            if prerequisite.lower() not in owned:
                missing.append(prerequisite)
        return missing

    def purchase_advance(self, advance_name: str, choice: str | None = None) -> AdvancePurchase:
        """Purchase a skill/talent advance from the character's own career table.

        ``choice`` names the specific pick for a generic slot advance (e.g.
        "Minor Psychic Power" bought with ``choice="Healer"`` is recorded as
        "Minor Psychic Power (Healer)") -- required to tell apart repeated
        purchases of the same repeatable slot in ``advance_history``/the GUI.
        """
        try:
            advance = self.career.get_advance(advance_name)
        except KeyError as exc:
            raise PrerequisiteError(
                f"'{advance_name}' is not on {self.career.name}'s advance table."
            ) from exc

        if not advance.repeatable and self._purchase_count(advance.name) >= 1:
            raise PrerequisiteError(f"Advance '{advance.name}' has already been purchased.")

        # Rank-gating only applies when this career actually has tree data loaded
        # (every real career does; a hand-built test career with no rank_tree
        # argument falls back to the old permissive behaviour rather than
        # rejecting everything).
        reachable = set(advance.available_ranks) or {advance.rank}
        if self.career.rank_previous and not reachable & set(self.career_path):
            raise PrerequisiteError(
                f"'{advance.name}' requires reaching one of [{', '.join(reachable)}] "
                f"(career_path: {', '.join(self.career_path) or 'none'})."
            )

        missing = self.missing_prerequisites(advance.prerequisites)
        if missing:
            raise PrerequisiteError("Missing prerequisites: " + ", ".join(missing))

        if advance.cost > self.xp_available:
            raise PrerequisiteError(f"Not enough XP. Cost: {advance.cost}, available: {self.xp_available}.")

        display_name = f"{advance.name} ({choice})" if choice else advance.name
        purchase = AdvancePurchase(
            name=display_name, xp_cost=advance.cost, type=advance.type, order=len(self.advance_history) + 1
        )
        self.advance_history.append(purchase)
        return purchase
    def purchase_psy_rating(
        self,
        rating: int,
        *,
        new_discipline: str | None = None,
        discipline_powers: Sequence[str] = (),
        minor_powers: Sequence[str] = (),
    ) -> AdvancePurchase:
        """Buy "Psy Rating N" (XP cost/prereqs/rank-gating via ``purchase_advance``,
        same as any other advance) and record its free power grant.

        Per the core rulebook, each tier grants some combination of Minor
        Psychic Powers and/or Discipline Powers for free (see
        ``_PSY_RATING_GRANTS``); tiers 4+ let the player choose between "more
        powers in a Discipline you know" or "one new Discipline, one power from
        it" instead. Pass ``new_discipline`` to take the latter option. Callers
        may take fewer than the maximum grant (a character sheet need not record
        every power a player was ever entitled to) but not more.

        Psy Rating 1 is a free starting grant ("All starting Psykers begin with
        Psy Rating 1") rather than a purchasable catalog entry, so it's recorded
        directly instead of going through ``purchase_advance``.
        """
        if rating == 1:
            purchase = self.add_advance_unchecked("Psy Rating 1", xp_cost=0, type="talent")
        else:
            purchase = self.purchase_advance(f"Psy Rating {rating}")

        grants_minor, grants_discipline, forced_choice = _PSY_RATING_GRANTS.get(rating, (False, False, None))
        wp_bonus = self.characteristic_bonus("Willpower")
        max_count = -(-wp_bonus // 2)  # ceil

        if len(minor_powers) > (max_count if grants_minor else 0):
            raise PrerequisiteError(f"Psy Rating {rating} grants at most {max_count} Minor Psychic Powers.")

        taking_new_discipline = bool(new_discipline)
        if forced_choice == "new" and not taking_new_discipline:
            raise PrerequisiteError(f"Psy Rating {rating} requires choosing a new Discipline.")
        if taking_new_discipline:
            if len(discipline_powers) > 1:
                raise PrerequisiteError("Choosing a new Discipline grants only 1 power from it.")
            self.known_disciplines.append(new_discipline)
        elif grants_discipline and len(discipline_powers) > max_count:
            raise PrerequisiteError(f"Psy Rating {rating} grants at most {max_count} Discipline Powers.")
        elif discipline_powers and not grants_discipline:
            raise PrerequisiteError(f"Psy Rating {rating} does not grant Discipline Powers.")

        for power in minor_powers:
            self.advance_history.append(
                AdvancePurchase(
                    name=f"Minor Psychic Power ({power})",
                    xp_cost=0,
                    type="talent",
                    order=len(self.advance_history) + 1,
                    direct=True,
                )
            )
        for power in discipline_powers:
            self.advance_history.append(
                AdvancePurchase(
                    name=f"Psychic Power ({power})",
                    xp_cost=0,
                    type="talent",
                    order=len(self.advance_history) + 1,
                    direct=True,
                )
            )
        return purchase

    def purchase_characteristic_advance(self, characteristic: str) -> AdvancePurchase:
        """Purchase the next tier of a characteristic advance (Simple -> Expert, in order)."""
        try:
            cost = self.career.get_characteristic_cost(characteristic)
        except KeyError as exc:
            raise PrerequisiteError(str(exc)) from exc

        owned_tiers = self._owned_tiers(cost.characteristic)
        if owned_tiers >= len(CHARACTERISTIC_TIERS):
            raise PrerequisiteError(f"'{cost.characteristic}' is already at its maximum tier for this career.")

        tier = CHARACTERISTIC_TIERS[owned_tiers]
        tier_cost = cost.cost_for(tier)
        if tier_cost is None:
            raise PrerequisiteError(f"'{cost.characteristic}' cannot be advanced for career '{self.career.name}'.")
        if tier_cost > self.xp_available:
            raise PrerequisiteError(f"Not enough XP. Cost: {tier_cost}, available: {self.xp_available}.")

        purchase = AdvancePurchase(
            name=f"{cost.characteristic} {tier.title()}",
            xp_cost=tier_cost,
            type="characteristic",
            order=len(self.advance_history) + 1,
        )
        self.advance_history.append(purchase)
        return purchase

    def undo_last_purchase(self) -> AdvancePurchase:
        """Reverse the most recent purchase (advance history is a stack, not a log).

        Characteristic advances need no reverse mutation here: their +5 is derived
        from ``advance_history`` on demand (see ``effective_characteristic``), never
        stored, so popping the history entry is the whole undo.
        """
        if not self.advance_history:
            raise PrerequisiteError("No purchases to undo.")
        return self.advance_history.pop()

    def add_advance_unchecked(self, name: str, *, xp_cost: int = 0, type: str = "advance") -> AdvancePurchase:
        """Record an advance/talent WITHOUT rank-gating, prerequisite, cost, or
        catalog-membership checks -- an explicit escape hatch for importing a
        pre-existing character whose real purchase history/rank path can't be
        reliably reconstructed from the parsed rulebook data (which has known
        gaps -- see career_scheme_parser.py). Never use this for normal
        gameplay purchases; it exists so an import can be honest about what's
        verified vs. trusted-as-reported, not to bypass validation generally."""
        purchase = AdvancePurchase(
            name=name, xp_cost=xp_cost, type=type, order=len(self.advance_history) + 1, direct=True
        )
        self.advance_history.append(purchase)
        return purchase

    def to_summary(self) -> str:
        lines = [
            f"Name: {self.name}",
            f"Career: {self.career.name}",
            f"Rank path: {' -> '.join(self.career_path) or '(none)'}",
            f"XP Total: {self.xp_total}",
            f"XP Spent: {self.xp_spent}",
            f"XP Available: {self.xp_available}",
            "Advance history:",
        ]
        if not self.advance_history:
            lines.append("  (none)")
        else:
            for purchase in self.advance_history:
                lines.append(f"  {purchase.order}. {purchase.name} ({purchase.type}, XP {purchase.xp_cost})")
        return "\n".join(lines)
