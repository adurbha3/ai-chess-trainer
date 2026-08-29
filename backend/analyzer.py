import chess
import chess.pgn
import chess.engine
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

from features import extract as extract_features, extract_relational, feature_delta, features_to_dict
from classifier import classify, MistakeLabel
from coach import generate_coaching_note, generate_game_summary

# Capture python-chess parse warnings
logging.basicConfig(level=logging.WARNING)

STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"
ANALYSIS_DEPTH = 14
MULTIPV = 2

BLUNDER_THRESHOLD = 300
MISTAKE_THRESHOLD = 100
INACCURACY_THRESHOLD = 50


@dataclass
class MoveAnnotation:
    move_number: int
    color: str
    san: str
    uci: str
    fen_before: str
    fen_after: str
    eval_before: Optional[float]
    eval_after: Optional[float]
    cp_loss: Optional[float]
    classification: str
    best_move_san: Optional[str]
    best_move_uci: Optional[str]
    best_move_eval: Optional[float]
    # Structural analysis fields
    mistake_category: Optional[str] = None     # tactical | pawn_structure | piece_placement | king_safety | coordination
    mistake_signals: list[str] = field(default_factory=list)
    coaching_note: Optional[str] = None
    features_before: Optional[dict] = None
    features_after: Optional[dict] = None


@dataclass
class GameAnalysis:
    game_index: int
    white: str
    black: str
    result: str
    date: str
    parse_error: str = ""
    moves: list[MoveAnnotation] = field(default_factory=list)
    blunder_count: int = 0
    mistake_count: int = 0
    inaccuracy_count: int = 0
    avg_cp_loss_white: float = 0.0
    game_summary: str = ""
    avg_cp_loss_black: float = 0.0


def _score_to_cp(score: chess.engine.Score, pov: chess.Color) -> Optional[float]:
    if score is None:
        return None
    relative = score.pov(pov)
    if relative.is_mate():
        return 10000 if relative.mate() > 0 else -10000
    return relative.score()


def _classify(cp_loss: float) -> str:
    if cp_loss >= BLUNDER_THRESHOLD:
        return "blunder"
    if cp_loss >= MISTAKE_THRESHOLD:
        return "mistake"
    if cp_loss >= INACCURACY_THRESHOLD:
        return "inaccuracy"
    return "good"


def analyze_pgn(pgn_text: str) -> list[GameAnalysis]:
    pgn_io = io.StringIO(pgn_text)
    results = []
    game_index = 0

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        while True:
            # Capture any parse errors from python-chess
            parse_errors: list[str] = []

            class ErrorCapture(chess.pgn.GameBuilder):
                def handle_error(self, error: Exception) -> None:
                    parse_errors.append(str(error))

            game = chess.pgn.read_game(pgn_io, Visitor=ErrorCapture)
            if game is None:
                break

            headers = game.headers
            analysis = GameAnalysis(
                game_index=game_index,
                white=headers.get("White", "Unknown"),
                black=headers.get("Black", "Unknown"),
                result=headers.get("Result", "*"),
                date=headers.get("Date", ""),
                parse_error="; ".join(parse_errors) if parse_errors else "",
            )

            # Count expected moves from the raw PGN before Stockfish
            mainline_nodes = list(game.mainline())
            print(f"[Game {game_index}] {analysis.white} vs {analysis.black} — "
                  f"{len(mainline_nodes)} mainline nodes found"
                  + (f" | parse errors: {parse_errors}" if parse_errors else ""))

            if not mainline_nodes:
                print(f"[Game {game_index}] WARNING: No mainline moves found. Skipping Stockfish analysis.")
                results.append(analysis)
                game_index += 1
                continue

            board = game.board()
            move_number = 1

            for node in mainline_nodes:
                move = node.move
                color = "white" if board.turn == chess.WHITE else "black"
                fen_before = board.fen()

                try:
                    # Extract structural features BEFORE the move
                    moving_color = board.turn
                    feats_before = extract_features(board, moving_color)
                    rel_before = extract_relational(board, moving_color)

                    info_before = engine.analyse(board, chess.engine.Limit(depth=ANALYSIS_DEPTH), multipv=MULTIPV)
                    eval_before = _score_to_cp(info_before[0]["score"], board.turn)
                    best_move = info_before[0].get("pv", [None])[0]
                    best_move_san = board.san(best_move) if best_move else None
                    best_move_uci = best_move.uci() if best_move else None

                    board.push(move)
                    fen_after = board.fen()

                    # Extract structural features AFTER the move (from same color's perspective)
                    feats_after = extract_features(board, moving_color)
                    rel_after = extract_relational(board, moving_color)

                    info_after = engine.analyse(board, chess.engine.Limit(depth=ANALYSIS_DEPTH), multipv=1)
                    eval_after_opponent = _score_to_cp(info_after[0]["score"], board.turn)
                    eval_after = -eval_after_opponent if eval_after_opponent is not None else None

                    cp_loss: Optional[float] = None
                    classification = "good"
                    if eval_before is not None and eval_after is not None:
                        cp_loss = max(0, eval_before - eval_after)
                        classification = _classify(cp_loss)

                    # Structural classification + coaching note (only for significant errors)
                    mistake_category = None
                    mistake_signals: list[str] = []
                    coaching_note = None
                    if classification in ("inaccuracy", "mistake", "blunder") and cp_loss is not None:
                        label = classify(feats_before, feats_after, cp_loss, rel_before, rel_after)
                        mistake_category = label.category
                        mistake_signals = label.signals
                        coaching_note = generate_coaching_note(
                            san=node.san(),
                            classification=classification,
                            cp_loss=cp_loss,
                            best_move_san=best_move_san,
                            label=label,
                            fen_before=fen_before,
                            fen_after=fen_after,
                            move_number=move_number,
                            color=color,
                        )

                    annotation = MoveAnnotation(
                        move_number=move_number,
                        color=color,
                        san=node.san(),
                        uci=move.uci(),
                        fen_before=fen_before,
                        fen_after=fen_after,
                        eval_before=eval_before,
                        eval_after=eval_after,
                        cp_loss=cp_loss,
                        classification=classification,
                        best_move_san=best_move_san,
                        best_move_uci=best_move_uci,
                        best_move_eval=eval_before,
                        mistake_category=mistake_category,
                        mistake_signals=mistake_signals,
                        coaching_note=coaching_note,
                        features_before=features_to_dict(feats_before),
                        features_after=features_to_dict(feats_after),
                    )
                    analysis.moves.append(annotation)

                    if classification == "blunder":
                        analysis.blunder_count += 1
                    elif classification == "mistake":
                        analysis.mistake_count += 1
                    elif classification == "inaccuracy":
                        analysis.inaccuracy_count += 1

                except Exception as e:
                    print(f"[Game {game_index}] Error on move {move_number} ({color}): {e}")
                    board.push(move)  # still advance the board

                # Increment after black's move (one full chess move = white + black)
                if color == "black":
                    move_number += 1

            white_losses = [m.cp_loss for m in analysis.moves if m.color == "white" and m.cp_loss is not None]
            black_losses = [m.cp_loss for m in analysis.moves if m.color == "black" and m.cp_loss is not None]
            analysis.avg_cp_loss_white = sum(white_losses) / len(white_losses) if white_losses else 0.0
            analysis.avg_cp_loss_black = sum(black_losses) / len(black_losses) if black_losses else 0.0

            # Game-level coaching summary from all notable mistakes
            notable = [
                {
                    "move_number": m.move_number,
                    "color": m.color,
                    "san": m.san,
                    "category": m.mistake_category or "unknown",
                    "coaching_note": m.coaching_note or "",
                }
                for m in analysis.moves
                if m.classification in ("mistake", "blunder") and m.coaching_note
            ]
            analysis.game_summary = generate_game_summary(notable, player_color="both")

            print(f"[Game {game_index}] Analysis complete: {len(analysis.moves)} moves analyzed.")
            results.append(analysis)
            game_index += 1

    return results
