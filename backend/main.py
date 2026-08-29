from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import traceback
import pathlib

from analyzer import analyze_pgn
from patterns import detect_patterns

SAMPLE_PGN_PATH = pathlib.Path(__file__).parent.parent / "test.pgn"

app = FastAPI(title="Chess Trainer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    pgn: str
    player_color: Optional[str] = "both"  # "white" | "black" | "both"


def _build_response(games, player_color: str):
    pattern_report = detect_patterns(games, player_color=player_color)
    games_out = []
    for g in games:
        moves_out = [
            {
                "move_number": m.move_number,
                "color": m.color,
                "san": m.san,
                "uci": m.uci,
                "fen_before": m.fen_before,
                "fen_after": m.fen_after,
                "eval_before": m.eval_before,
                "eval_after": m.eval_after,
                "cp_loss": m.cp_loss,
                "classification": m.classification,
                "best_move_san": m.best_move_san,
                "best_move_uci": m.best_move_uci,
                "mistake_category": m.mistake_category,
                "mistake_signals": m.mistake_signals,
                "coaching_note": m.coaching_note,
                "features_before": m.features_before,
                "features_after": m.features_after,
            }
            for m in g.moves
        ]
        games_out.append({
            "game_index": g.game_index,
            "parse_error": g.parse_error,
            "white": g.white,
            "black": g.black,
            "result": g.result,
            "date": g.date,
            "moves": moves_out,
            "blunder_count": g.blunder_count,
            "mistake_count": g.mistake_count,
            "inaccuracy_count": g.inaccuracy_count,
            "avg_cp_loss_white": g.avg_cp_loss_white,
            "avg_cp_loss_black": g.avg_cp_loss_black,
            "game_summary": g.game_summary,
        })
    return {
        "games": games_out,
        "patterns": pattern_report.patterns,
        "study_topics": pattern_report.study_topics,
        "overall_accuracy": pattern_report.overall_accuracy,
        "worst_phase": pattern_report.worst_phase,
    }


@app.get("/sample")
async def analyze_sample(player_color: str = "both"):
    pgn_text = SAMPLE_PGN_PATH.read_text()
    try:
        games = analyze_pgn(pgn_text)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    return _build_response(games, player_color)


@app.post("/analyze-text")
async def analyze_text(pgn: str = Body(..., media_type="text/plain"), player_color: str = "both"):
    if not pgn.strip():
        raise HTTPException(status_code=400, detail="PGN is empty")
    try:
        games = analyze_pgn(pgn)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    if not games:
        raise HTTPException(status_code=400, detail="No valid games found in PGN")
    return _build_response(games, player_color)


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), player_color: str = "both"):
    if not file.filename.endswith(".pgn"):
        raise HTTPException(status_code=400, detail="File must be a .pgn file")

    content = await file.read()
    pgn_text = content.decode("utf-8")

    if not pgn_text.strip():
        raise HTTPException(status_code=400, detail="PGN file is empty")

    try:
        games = analyze_pgn(pgn_text)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    if not games:
        raise HTTPException(status_code=400, detail="No valid games found in PGN file")

    return _build_response(games, player_color)


@app.get("/health")
def health():
    return {"status": "ok"}
