"use client";

import type { Pattern, StudyTopic } from "@/types";

const SEVERITY_COLORS = {
  high: "border-red-700 bg-red-950/40",
  medium: "border-yellow-700 bg-yellow-950/30",
  low: "border-green-800 bg-green-950/20",
};

const PRIORITY_BADGE = {
  high: "bg-red-800 text-red-200",
  medium: "bg-yellow-800 text-yellow-200",
  low: "bg-green-800 text-green-200",
};

const CATEGORY_ICONS: Record<string, string> = {
  tactical:        "⚡",
  pawn_structure:  "♟",
  piece_placement: "♞",
  king_safety:     "♔",
  coordination:    "⚙",
};

const PHASE_ICONS: Record<string, string> = {
  opening:     "♟",
  middlegame:  "⚔",
  endgame:     "♛",
};

const CATEGORY_LABELS: Record<string, string> = {
  tactical:        "Tactical errors",
  pawn_structure:  "Pawn structure",
  piece_placement: "Piece placement",
  king_safety:     "King safety",
  coordination:    "Piece coordination",
};

interface Props {
  patterns: Pattern[];
  topics: StudyTopic[];
  accuracy: number;
  worstPhase: string;
  gameSummary?: string;
}

export default function ImprovementPlan({ patterns, topics, accuracy, worstPhase, gameSummary }: Props) {
  const accuracyColor =
    accuracy >= 90 ? "text-green-400" : accuracy >= 75 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="flex flex-col gap-8 max-w-3xl">
      {/* Game summary (AI coaching) */}
      {gameSummary && (
        <div className="bg-blue-950/30 border border-blue-800 rounded-xl p-4">
          <p className="text-xs font-semibold text-blue-400 mb-1.5 uppercase tracking-wide">Coach's Summary</p>
          <p className="text-gray-200 text-sm leading-relaxed">{gameSummary}</p>
        </div>
      )}

      {/* Summary stats */}
      <div className="flex gap-6 flex-wrap">
        <div className="flex flex-col items-center bg-gray-900 rounded-xl px-8 py-4">
          <span className={`text-4xl font-bold ${accuracyColor}`}>{accuracy}%</span>
          <span className="text-sm text-gray-400 mt-1">Overall Accuracy</span>
        </div>
        <div className="flex flex-col items-center bg-gray-900 rounded-xl px-8 py-4">
          <span className="text-4xl">{PHASE_ICONS[worstPhase] ?? "?"}</span>
          <span className="text-sm text-gray-400 mt-1">
            Weakest phase: <span className="text-white capitalize">{worstPhase}</span>
          </span>
        </div>
      </div>

      {/* Patterns */}
      {patterns.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3">Detected Patterns</h2>
          <div className="flex flex-col gap-3">
            {patterns.map((p, i) => {
              const cat = p.category ?? (p.phase ? "pawn_structure" : "tactical");
              const icon = CATEGORY_ICONS[cat] ?? "◆";
              const label = CATEGORY_LABELS[cat] ?? cat;
              return (
                <div
                  key={i}
                  className={`rounded-lg border p-4 ${SEVERITY_COLORS[p.severity]}`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-base leading-none">{icon}</span>
                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-300">
                      {label}
                    </span>
                    <span
                      className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_BADGE[p.severity]}`}
                    >
                      {p.severity}
                    </span>
                  </div>

                  <p className="text-sm text-gray-200 mb-2">{p.description}</p>

                  {/* Move number chips */}
                  {p.move_numbers && p.move_numbers.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {p.move_numbers.slice(0, 8).map((mn) => (
                        <span
                          key={mn}
                          className="text-xs px-1.5 py-0.5 rounded bg-gray-900/70 text-gray-400 font-mono"
                        >
                          move {mn}
                        </span>
                      ))}
                      {p.move_numbers.length > 8 && (
                        <span className="text-xs text-gray-500">
                          +{p.move_numbers.length - 8} more
                        </span>
                      )}
                    </div>
                  )}

                  {p.avg_cp_loss !== undefined && (
                    <p className="text-xs text-gray-500">
                      Avg cp loss: {p.avg_cp_loss}
                      {p.blunder_count !== undefined && ` · Blunders: ${p.blunder_count}`}
                      {p.mistake_count !== undefined && ` · Mistakes: ${p.mistake_count}`}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Study Topics */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Study Plan</h2>
        <div className="flex flex-col gap-4">
          {topics.map((t, i) => (
            <div key={i} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
              <div className="flex items-start justify-between gap-3 mb-2">
                <h3 className="font-semibold text-gray-100">{t.topic}</h3>
                <span
                  className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_BADGE[t.priority]}`}
                >
                  {t.priority} priority
                </span>
              </div>
              <p className="text-sm text-gray-400 mb-3">{t.reason}</p>
              <ul className="flex flex-col gap-1">
                {t.resources.map((r, j) => (
                  <li key={j} className="flex items-start gap-2 text-sm text-gray-300">
                    <span className="text-blue-400 mt-0.5 shrink-0">→</span>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
