"""
Classifies the primary reason a move was bad, based on structural feature deltas
and relational signals from the position.

Categories:
  tactical         — hanging piece or immediate capture missed
  pawn_structure   — weakened pawn skeleton (isolated, doubled, backward)
  piece_placement  — moved piece to a bad square (knight rim, low mobility)
  king_safety      — weakened king pawn shield or opened files toward king
  coordination     — lost overall piece harmony / mobility
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

from features import PositionFeatures, feature_delta

if TYPE_CHECKING:
    from features import RelationalSignals


@dataclass
class MistakeLabel:
    category: str                 # primary category
    confidence: str               # "high" | "medium" | "low"
    signals: list[str]            # human-readable reason strings
    delta: dict                   # raw feature deltas for transparency


# Weighted "badness" scores for each delta field (higher = this delta matters more)
_WEIGHTS = {
    "hanging_pieces":       10.0,
    "king_open_files":       4.0,
    "king_pawn_shield":     -3.5,   # negative weight: decrease is bad
    "isolated_pawns":        3.0,
    "pawn_islands":          2.5,
    "doubled_pawns":         2.0,
    "backward_pawns":        2.0,
    "knight_on_rim":         3.0,
    "knight_mobility_avg":  -2.5,   # decrease is bad
    "bishop_mobility_avg":  -2.0,   # decrease is bad
    "total_mobility":       -1.5,   # decrease is bad
    "rooks_on_open_files":  -1.5,   # decrease is bad
    "pawn_mobility":        -1.0,
    "passed_pawns":         -1.0,   # losing a passed pawn is bad
}

_CATEGORY_MAP = {
    "hanging_pieces":       "tactical",
    "king_open_files":      "king_safety",
    "king_pawn_shield":     "king_safety",
    "isolated_pawns":       "pawn_structure",
    "pawn_islands":         "pawn_structure",
    "doubled_pawns":        "pawn_structure",
    "backward_pawns":       "pawn_structure",
    "pawn_mobility":        "pawn_structure",
    "passed_pawns":         "pawn_structure",
    "knight_on_rim":        "piece_placement",
    "knight_mobility_avg":  "piece_placement",
    "bishop_mobility_avg":  "piece_placement",
    "rooks_on_open_files":  "piece_placement",
    "total_mobility":       "coordination",
}

_SIGNAL_DESCRIPTIONS = {
    "hanging_pieces":      lambda d: f"left {d} piece(s) undefended",
    "king_open_files":     lambda d: f"opened {d} file(s) toward the king",
    "king_pawn_shield":    lambda d: f"lost {abs(d)} king pawn shield square(s)",
    "isolated_pawns":      lambda d: f"created {d} isolated pawn(s)",
    "pawn_islands":        lambda d: f"increased pawn islands by {d}",
    "doubled_pawns":       lambda d: f"created {d} doubled pawn(s)",
    "backward_pawns":      lambda d: f"created {d} backward pawn(s)",
    "knight_on_rim":       lambda d: f"moved {d} knight(s) to the rim (bad square)",
    "knight_mobility_avg": lambda d: f"reduced average knight mobility by {abs(d):.1f} squares",
    "bishop_mobility_avg": lambda d: f"reduced average bishop mobility by {abs(d):.1f} squares",
    "rooks_on_open_files": lambda d: f"rook(s) no longer on open file(s)",
    "total_mobility":      lambda d: f"reduced total piece mobility by {abs(d)} squares",
    "passed_pawns":        lambda d: f"lost {abs(d)} passed pawn(s)",
    "pawn_mobility":       lambda d: f"restricted own pawn advances by {abs(d)} square(s)",
}


def _categorize_relational(signal: str) -> str:
    """Infer category from the text content of a relational signal."""
    s = signal.lower()
    if any(x in s for x in ["pinned", "overloaded"]):
        return "tactical"
    if any(x in s for x in ["king", "castled", "shield", "pawn cover"]):
        return "king_safety"
    if any(x in s for x in ["isolated pawn", "passed pawn", "bad bishop", "diagonal"]):
        return "pawn_structure"
    if any(x in s for x in ["knight", "rook trapped", "back rank"]):
        return "piece_placement"
    if "bishop" in s:
        return "piece_placement"
    return "coordination"


def classify(
    before: PositionFeatures,
    after: PositionFeatures,
    cp_loss: float,
    rel_before: "RelationalSignals | None" = None,
    rel_after: "RelationalSignals | None" = None,
) -> MistakeLabel:
    delta = feature_delta(before, after)

    # --- Relational signals: prefer these when they exist in the position after the move ---
    # New signals (present after but not before) are most indicative; fall back to all after-signals.
    if rel_after is not None and rel_after.signals:
        before_set = set(rel_before.signals) if rel_before else set()
        new_signals = [s for s in rel_after.signals if s not in before_set]
        # Use new signals if available, otherwise use all after-signals (position still has problems)
        primary_signals = new_signals if new_signals else rel_after.signals

        # Tally categories across all after-signals to find the dominant one
        cat_counts: dict[str, int] = {}
        for s in rel_after.signals:
            cat = _categorize_relational(s)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        primary_cat = max(cat_counts, key=lambda c: cat_counts[c])
        confidence = "high" if new_signals else "medium"

        return MistakeLabel(
            category=primary_cat,
            confidence=confidence,
            signals=primary_signals[:3],
            delta=delta,
        )

    # --- Fallback: scalar feature delta approach ---
    category_scores: dict[str, float] = {
        "tactical": 0.0,
        "pawn_structure": 0.0,
        "piece_placement": 0.0,
        "king_safety": 0.0,
        "coordination": 0.0,
    }
    active_signals: list[str] = []

    for field, weight in _WEIGHTS.items():
        d = delta.get(field, 0)
        if weight > 0:
            badness = d * weight
        else:
            badness = (-d) * abs(weight)

        if badness > 0.5:
            cat = _CATEGORY_MAP.get(field, "coordination")
            category_scores[cat] += badness
            desc_fn = _SIGNAL_DESCRIPTIONS.get(field)
            if desc_fn:
                active_signals.append(desc_fn(d))

    total_badness = sum(category_scores.values())
    if total_badness < 1.0:
        if cp_loss >= 300:
            return MistakeLabel("tactical", "low", ["large evaluation drop with no clear structural cause"], delta)
        return MistakeLabel("coordination", "low", ["subtle positional error"], delta)

    primary = max(category_scores, key=lambda c: category_scores[c])
    primary_score = category_scores[primary]
    ratio = primary_score / total_badness
    confidence = "high" if ratio > 0.6 else "medium" if ratio > 0.4 else "low"

    return MistakeLabel(
        category=primary,
        confidence=confidence,
        signals=active_signals[:3],
        delta=delta,
    )
