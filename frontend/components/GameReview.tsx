"use client";

import { useState, useEffect, useCallback } from "react";
import { Chessboard } from "react-chessboard";
import type { GameAnalysis, MoveAnnotation } from "@/types";

const CLASS_COLORS: Record<string, string> = {
  brilliant: "text-cyan-400",
  good: "text-green-400",
  inaccuracy: "text-yellow-400",
  mistake: "text-orange-400",
  blunder: "text-red-400",
};

const CLASS_BG: Record<string, string> = {
  brilliant: "bg-cyan-900/40 border-cyan-700",
  good: "bg-green-900/20 border-green-800",
  inaccuracy: "bg-yellow-900/30 border-yellow-700",
  mistake: "bg-orange-900/30 border-orange-700",
  blunder: "bg-red-900/40 border-red-700",
};

const CLASS_SYMBOLS: Record<string, string> = {
  brilliant: "!!",
  good: "",
  inaccuracy: "?!",
  mistake: "?",
  blunder: "??",
};

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

function EvalBar({ cp }: { cp: number | null }) {
  if (cp === null) return null;
  const clamped = Math.max(-1000, Math.min(1000, cp));
  const whitePercent = 50 + (clamped / 1000) * 50;
  const label = Math.abs(cp) >= 10000 ? "M" : (cp / 100).toFixed(1);
  return (
    <div className="flex flex-col items-center gap-1 w-5 shrink-0">
      <span className="text-xs text-gray-500 font-mono leading-none">{label}</span>
      <div className="w-3 flex-1 bg-gray-800 rounded overflow-hidden flex flex-col-reverse min-h-[200px]">
        <div
          className="bg-white transition-all duration-300"
          style={{ height: `${whitePercent}%` }}
        />
      </div>
    </div>
  );
}

interface Props {
  game: GameAnalysis;
}

export default function GameReview({ game }: Props) {
  // -1 = starting position; 0..N-1 = position after that move
  const [moveIdx, setMoveIdx] = useState(-1);

  const current: MoveAnnotation | undefined =
    moveIdx >= 0 ? game.moves[moveIdx] : undefined;

  const fen =
    moveIdx === -1
      ? (game.moves[0]?.fen_before ?? START_FEN)
      : (current?.fen_after ?? START_FEN);

  const evalCp = moveIdx === -1 ? null : (current?.eval_after ?? null);

  const totalMoves = game.moves.length;

  const goBack = useCallback(() => setMoveIdx((i) => Math.max(-1, i - 1)), []);
  const goForward = useCallback(
    () => setMoveIdx((i) => Math.min(totalMoves - 1, i + 1)),
    [totalMoves]
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft") goBack();
      if (e.key === "ArrowRight") goForward();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goBack, goForward]);

  const arrows: { startSquare: string; endSquare: string; color: string }[] = [];
  if (
    current?.best_move_uci &&
    current.classification !== "good" &&
    current.classification !== "brilliant"
  ) {
    arrows.push({
      startSquare: current.best_move_uci.slice(0, 2),
      endSquare: current.best_move_uci.slice(2, 4),
      color: "rgb(0,150,255)",
    });
  }

  const stats = [
    { label: "Blunders", value: game.blunder_count, color: "text-red-400" },
    { label: "Mistakes", value: game.mistake_count, color: "text-orange-400" },
    { label: "Inaccuracies", value: game.inaccuracy_count, color: "text-yellow-400" },
    { label: "Avg ±cp (W)", value: game.avg_cp_loss_white.toFixed(0), color: "text-gray-300" },
    { label: "Avg ±cp (B)", value: game.avg_cp_loss_black.toFixed(0), color: "text-gray-300" },
  ];

  return (
    <div className="flex gap-4" style={{ minHeight: 0 }}>
      {/* Left: board + eval bar */}
      <div className="flex gap-2 items-start shrink-0">
        <EvalBar cp={evalCp} />
        <div style={{ width: 320 }}>
          <Chessboard
            options={{
              position: fen,
              boardStyle: { width: "320px" },
              allowDragging: false,
              arrows,
              boardOrientation: "white",
            }}
          />
        </div>
      </div>

      {/* Right: everything else */}
      <div className="flex flex-col gap-3 flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between text-sm text-gray-400">
          <span className="font-medium text-gray-200">
            {game.white} <span className="text-gray-500">vs</span> {game.black}
          </span>
          <span>{game.result} · {game.date}</span>
        </div>

        {/* Stats */}
        <div className="flex gap-2 flex-wrap">
          {stats.map((s) => (
            <div
              key={s.label}
              className="flex flex-col items-center bg-gray-900 rounded-lg px-3 py-1.5 min-w-[64px]"
            >
              <span className={`text-base font-bold ${s.color}`}>{s.value}</span>
              <span className="text-xs text-gray-500">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Annotation panel */}
        <div className="min-h-[52px]">
          {current && current.classification !== "good" ? (
            <div className={`rounded-lg border p-3 text-sm ${CLASS_BG[current.classification]}`}>
              {/* Header row */}
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className={`font-bold ${CLASS_COLORS[current.classification]}`}>
                  {current.classification.toUpperCase()} {CLASS_SYMBOLS[current.classification]}
                </span>
                {current.mistake_category && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-300 capitalize">
                    {current.mistake_category.replace("_", " ")}
                  </span>
                )}
                <span className="text-gray-400 text-xs ml-auto">
                  Move {current.move_number} · {current.cp_loss?.toFixed(0)} cp lost
                </span>
              </div>

              {/* Coaching note (Claude or fallback) */}
              {current.coaching_note ? (
                <p className="text-gray-200 text-xs leading-relaxed mb-1.5">
                  {current.coaching_note}
                </p>
              ) : (
                <p className="text-gray-300 text-xs mb-1.5">
                  <span className="font-mono">{current.san}</span> lost{" "}
                  <span className="font-semibold">{current.cp_loss?.toFixed(0)} cp</span>.
                  {current.best_move_san && (
                    <> Best was <span className="font-mono text-blue-300">{current.best_move_san}</span>.</>
                  )}
                </p>
              )}

              {/* Structural signals */}
              {current.mistake_signals && current.mistake_signals.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {current.mistake_signals.map((s, i) => (
                    <span key={i} className="text-xs px-1.5 py-0.5 rounded bg-gray-900/60 text-gray-400">
                      {s}
                    </span>
                  ))}
                </div>
              )}

              {/* Best move hint */}
              {current.best_move_san && (
                <p className="text-xs text-blue-400 mt-1.5">
                  Best: <span className="font-mono">{current.best_move_san}</span> (shown with blue arrow)
                </p>
              )}
            </div>
          ) : current ? (
            <div className="rounded-lg border border-green-900 bg-green-950/20 p-2.5 text-xs text-green-400">
              Good move — {current.san}
            </div>
          ) : (
            <div className="rounded-lg border border-gray-800 p-2.5 text-xs text-gray-500">
              Starting position — use ▶ or click a move to begin
            </div>
          )}
        </div>

        {/* Move count badge — always visible for debugging */}
        <div className="text-xs text-gray-500">
          {totalMoves > 0
            ? `${totalMoves} moves analyzed`
            : game.parse_error
            ? <span className="text-red-400">PGN parse error: {game.parse_error}</span>
            : <span className="text-yellow-400">No moves found in this game's main line. Try uploading <code>test.pgn</code> to verify the app works.</span>
          }
        </div>

        {/* Move list */}
        <div className="bg-gray-900 rounded-xl p-2.5 overflow-y-auto" style={{ maxHeight: 200, minHeight: 48 }}>
          {totalMoves === 0 ? (
            <p className="text-xs text-gray-500 text-center py-2">
              No moves to display.{" "}
              {game.parse_error
                ? "The PGN could not be parsed correctly."
                : "The PGN was read but contained no mainline moves."}
            </p>
          ) : (
            <div className="flex flex-wrap gap-0.5">
              {game.moves.map((m, i) => {
                const sym = CLASS_SYMBOLS[m.classification] ?? "";
                const isActive = i === moveIdx;
                return (
                  <button
                    key={i}
                    onClick={() => setMoveIdx(i)}
                    title={m.cp_loss != null ? `cp loss: ${m.cp_loss.toFixed(0)}` : ""}
                    className={`px-1.5 py-0.5 rounded text-xs font-mono transition-colors ${
                      isActive
                        ? "bg-blue-600 text-white"
                        : m.classification !== "good"
                        ? `${CLASS_COLORS[m.classification]} hover:bg-gray-800`
                        : "text-gray-400 hover:bg-gray-800"
                    }`}
                  >
                    {m.color === "white" ? `${m.move_number}.` : ""}
                    {m.san}{sym}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex gap-2 items-center">
          <button
            onClick={() => setMoveIdx(-1)}
            disabled={moveIdx === -1}
            className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-30 text-sm"
            title="Start"
          >⏮</button>
          <button
            onClick={() => setMoveIdx((i) => Math.max(-1, i - 1))}
            disabled={moveIdx === -1}
            className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-30 text-sm"
            title="Previous"
          >◀</button>
          <button
            onClick={() => setMoveIdx((i) => Math.min(totalMoves - 1, i + 1))}
            disabled={moveIdx === totalMoves - 1}
            className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-30 text-sm"
            title="Next"
          >▶</button>
          <button
            onClick={() => setMoveIdx(totalMoves - 1)}
            disabled={moveIdx === totalMoves - 1}
            className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-30 text-sm"
            title="End"
          >⏭</button>
          <span className="ml-auto text-xs text-gray-500">
            {moveIdx === -1 ? "Start" : `${moveIdx + 1} / ${totalMoves}`}
          </span>
        </div>
      </div>
    </div>
  );
}
