"""
Generates per-move coaching notes using the Claude API.

Called only for moves classified as inaccuracy / mistake / blunder to keep
API costs low. Uses prompt caching so the large system prompt is only billed
once per batch of moves.
"""
import os
import anthropic
from classifier import MistakeLabel
from features import PositionFeatures, features_to_dict

_SYSTEM_PROMPT = """\
You are a chess coach giving concise, specific feedback on a single move.

You will receive:
- The move played (SAN notation)
- The classification: inaccuracy | mistake | blunder
- Centipawn loss (how many evaluation points were lost)
- The best move Stockfish recommended
- The primary structural category of the mistake
- The specific structural signals that changed (e.g. "created 1 isolated pawn")
- The board position in FEN notation before the move
- The board position in FEN notation after the move

Your job:
1. Write a 2–3 sentence coaching note explaining WHY this specific move was bad structurally.
2. Reference the exact structural signal (e.g. "your knight moved to the rim on h6, reducing its mobility from 6 to 2 squares").
3. Explain the strategic consequence if it isn't obvious (e.g. "the isolated pawn on d4 will now require constant defence").
4. Do NOT just say "this was a blunder" — explain the chess reason.
5. End with one short actionable tip (what to look for before making this type of move).

Keep your response under 80 words. No headings. Plain sentences only.
"""

_CATEGORY_LABELS = {
    "tactical": "Tactical blunder",
    "pawn_structure": "Pawn structure mistake",
    "piece_placement": "Piece placement error",
    "king_safety": "King safety weakened",
    "coordination": "Piece coordination loss",
}


def generate_coaching_note(
    san: str,
    classification: str,
    cp_loss: float,
    best_move_san: str | None,
    label: MistakeLabel,
    fen_before: str,
    fen_after: str,
    move_number: int,
    color: str,
) -> str:
    """
    Returns a coaching note string.
    Falls back to a rule-based note if the API key is not set or the call fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_note(san, classification, cp_loss, best_move_san, label)

    client = anthropic.Anthropic(api_key=api_key)

    signals_text = "\n".join(f"  - {s}" for s in label.signals) if label.signals else "  - No clear structural signal"
    best_move_text = best_move_san if best_move_san else "unknown"

    user_message = f"""\
Move {move_number} ({color}): {san}
Classification: {classification} ({cp_loss:.0f} centipawns lost)
Best move was: {best_move_text}
Primary mistake category: {_CATEGORY_LABELS.get(label.category, label.category)} (confidence: {label.confidence})
Structural signals:
{signals_text}

Position before move (FEN): {fen_before}
Position after move (FEN): {fen_after}
"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},  # cache the system prompt
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[coach] Claude API error: {e}")
        return _fallback_note(san, classification, cp_loss, best_move_san, label)


def _fallback_note(
    san: str,
    classification: str,
    cp_loss: float,
    best_move_san: str | None,
    label: MistakeLabel,
) -> str:
    """Rule-based fallback used when no API key is configured."""
    category_msg = {
        "tactical": f"{san} left a piece undefended or missed an immediate capture.",
        "pawn_structure": f"{san} damaged your pawn structure — look for isolated, doubled, or backward pawns created.",
        "piece_placement": f"{san} placed a piece on a poor square with limited mobility or activity.",
        "king_safety": f"{san} weakened your king's protection — avoid opening files toward your king.",
        "coordination": f"{san} reduced the harmony between your pieces.",
    }.get(label.category, f"{san} was a positional error.")

    best = f" Consider {best_move_san} instead." if best_move_san else ""
    signals = f" ({'; '.join(label.signals[:2])})" if label.signals else ""
    return f"{category_msg}{signals}{best}"


def generate_game_summary(
    coaching_notes: list[dict],
    player_color: str,
) -> str:
    """
    Generates a high-level game summary from all the per-move coaching notes.
    Used in the Improvement Plan tab.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not coaching_notes:
        return _fallback_summary(coaching_notes)

    client = anthropic.Anthropic(api_key=api_key)

    notes_text = "\n".join(
        f"Move {n['move_number']} ({n['color']}): {n['san']} — {n['category']} — {n['coaching_note']}"
        for n in coaching_notes
    )

    system = """\
You are a chess coach summarizing a student's game. Based on a list of annotated mistakes,
write a 3–5 sentence overall assessment identifying the 1–2 most important recurring themes.
Be specific: reference move numbers. End with the single most important thing to practise.
Keep it under 120 words.
"""
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Player color: {player_color}\n\nAnnotated mistakes:\n{notes_text}"}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[coach] Summary API error: {e}")
        return _fallback_summary(coaching_notes)


def _fallback_summary(coaching_notes: list[dict]) -> str:
    if not coaching_notes:
        return "No significant mistakes detected."
    categories = [n["category"] for n in coaching_notes]
    from collections import Counter
    top = Counter(categories).most_common(2)
    parts = [f"{_CATEGORY_LABELS.get(c, c)} ({count} time(s))" for c, count in top]
    return "Main issues: " + ", ".join(parts) + "."
