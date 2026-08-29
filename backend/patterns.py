"""
Detects recurring error patterns across multiple analyzed games, grouped by
structural category with specific move number references.
"""
from dataclasses import dataclass, field
from collections import defaultdict
from analyzer import GameAnalysis, MoveAnnotation


@dataclass
class PatternReport:
    patterns: list[dict] = field(default_factory=list)
    study_topics: list[dict] = field(default_factory=list)
    overall_accuracy: float = 0.0
    worst_phase: str = ""


def _move_phase(move_number: int) -> str:
    if move_number <= 10:
        return "opening"
    if move_number <= 30:
        return "middlegame"
    return "endgame"


_CATEGORY_LABELS = {
    "tactical":        "Tactical errors",
    "pawn_structure":  "Pawn structure",
    "piece_placement": "Piece placement",
    "king_safety":     "King safety",
    "coordination":    "Piece coordination",
}

_CATEGORY_DESCRIPTIONS = {
    "tactical":        "Missed captures or left pieces undefended",
    "pawn_structure":  "Damaged pawn structure (isolated, doubled, or backward pawns)",
    "piece_placement": "Pieces moved to poorly-placed squares (rim knights, trapped rooks, bad bishops)",
    "king_safety":     "Weakened king pawn shield or opened files toward your king",
    "coordination":    "Lost piece harmony and mobility without a clear structural cause",
}

_CATEGORY_STUDY_RESOURCES = {
    "tactical": [
        "Daily tactics puzzles on Lichess or Chess.com (15 min/day)",
        "Hanging piece patterns: always ask 'can they capture for free?'",
        "Before every move, check if your pieces are attacked",
    ],
    "pawn_structure": [
        "Study typical pawn structures for your openings",
        "Practice isolated pawn positions — learn when to trade vs. when to hold",
        "Silman's 'How to Reassess Your Chess' — chapters on imbalances",
    ],
    "piece_placement": [
        "Knights belong in the center — avoid a, b, g, h files when possible",
        "Rooks should contest open files and 7th rank",
        "Bad bishop positions — practice trading bad bishops for good ones",
    ],
    "king_safety": [
        "Never advance pawns in front of your castled king without compensation",
        "Study king attack patterns: Greek gift sacrifice, f7 attacks, etc.",
        "Lichess study: 'King Safety' — recognize danger signals early",
    ],
    "coordination": [
        "Aim for every piece to have a clear purpose before launching an attack",
        "Study 'prophylaxis' — anticipate your opponent's plan and neutralize it",
        "Nimzowitsch's 'My System' — piece coordination fundamentals",
    ],
}


def detect_patterns(games: list[GameAnalysis], player_color: str = "both") -> PatternReport:
    report = PatternReport()

    # Collect all bad moves with their categories and move numbers
    category_moves: dict[str, list[MoveAnnotation]] = defaultdict(list)
    phase_losses: dict[str, list[float]] = {"opening": [], "middlegame": [], "endgame": []}
    total_moves = 0
    total_bad = 0

    for game in games:
        for m in game.moves:
            if player_color != "both" and m.color != player_color:
                continue
            phase = _move_phase(m.move_number)
            if m.cp_loss is not None:
                phase_losses[phase].append(m.cp_loss)
            total_moves += 1
            if m.classification in ("blunder", "mistake", "inaccuracy"):
                total_bad += 1
                cat = m.mistake_category or "coordination"
                category_moves[cat].append(m)

    # Overall accuracy
    report.overall_accuracy = round(100 * (1 - total_bad / total_moves), 1) if total_moves > 0 else 100.0

    # Worst phase by average cp loss
    avg_phase = {
        p: (sum(ls) / len(ls) if ls else 0) for p, ls in phase_losses.items()
    }
    report.worst_phase = max(avg_phase, key=lambda p: avg_phase[p])

    # Build pattern entries, one per category that has errors
    patterns = []
    for cat, moves in sorted(category_moves.items(), key=lambda x: -len(x[1])):
        move_numbers = sorted({m.move_number for m in moves})
        blunders = [m for m in moves if m.classification == "blunder"]
        mistakes = [m for m in moves if m.classification == "mistake"]
        inaccuracies = [m for m in moves if m.classification == "inaccuracy"]
        avg_cp = (
            sum(m.cp_loss for m in moves if m.cp_loss is not None) /
            max(1, sum(1 for m in moves if m.cp_loss is not None))
        )

        # Build a description with move references and the best available signal
        move_refs = _format_move_refs(move_numbers)
        best_signal = _pick_best_signal(moves)

        description_parts = [
            f"{len(moves)} error(s) at move(s) {move_refs}."
        ]
        if best_signal:
            description_parts.append(best_signal)
        else:
            description_parts.append(_CATEGORY_DESCRIPTIONS[cat])

        severity = (
            "high" if len(blunders) >= 2 or avg_cp > 150
            else "medium" if len(blunders) >= 1 or avg_cp > 80
            else "low"
        )

        patterns.append({
            "type": "structural",
            "category": cat,
            "move_numbers": move_numbers,
            "count": len(moves),
            "blunder_count": len(blunders),
            "mistake_count": len(mistakes),
            "inaccuracy_count": len(inaccuracies),
            "avg_cp_loss": round(avg_cp, 1),
            "severity": severity,
            "description": " ".join(description_parts),
        })

    report.patterns = patterns

    # Build targeted study topics
    topics = []
    found_cats = set(category_moves.keys())

    for cat in ("tactical", "king_safety", "pawn_structure", "piece_placement", "coordination"):
        if cat not in found_cats:
            continue
        moves = category_moves[cat]
        blunders = sum(1 for m in moves if m.classification == "blunder")
        avg_cp = sum(m.cp_loss for m in moves if m.cp_loss is not None) / max(1, len(moves))
        priority = (
            "high" if blunders >= 2 or avg_cp > 150
            else "medium" if blunders >= 1 or avg_cp > 80
            else "low"
        )

        move_refs = _format_move_refs(sorted({m.move_number for m in moves}))
        reason = (
            f"{len(moves)} {cat.replace('_', ' ')} error(s) at move(s) {move_refs} "
            f"(avg {round(avg_cp, 0):.0f} cp loss, {blunders} blunder(s))."
        )

        topics.append({
            "topic": _CATEGORY_LABELS[cat],
            "reason": reason,
            "resources": _CATEGORY_STUDY_RESOURCES[cat],
            "priority": priority,
        })

    if not topics:
        topics.append({
            "topic": "General Tactical Sharpness",
            "reason": "No major recurring errors detected — keep practicing tactics to stay sharp.",
            "resources": [
                "Daily puzzles on Lichess",
                "Analyze your games with an engine once a week",
            ],
            "priority": "low",
        })

    report.study_topics = topics
    return report


def _format_move_refs(move_numbers: list[int]) -> str:
    """Format a list of move numbers into a compact string like '5, 12, 18–20'."""
    if not move_numbers:
        return "—"
    if len(move_numbers) <= 5:
        return ", ".join(str(n) for n in move_numbers)
    # Show first 4 and count remainder
    shown = ", ".join(str(n) for n in move_numbers[:4])
    return f"{shown} (+{len(move_numbers) - 4} more)"


def _pick_best_signal(moves: list[MoveAnnotation]) -> str:
    """Return the most specific relational signal across all moves, if any."""
    # Prefer signals from blunders, then mistakes, then inaccuracies
    for cls in ("blunder", "mistake", "inaccuracy"):
        for m in moves:
            if m.classification == cls and m.mistake_signals:
                return m.mistake_signals[0]
    return ""
