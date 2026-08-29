"use client";

import { useState } from "react";
import Upload from "@/components/Upload";
import GameReview from "@/components/GameReview";
import ImprovementPlan from "@/components/ImprovementPlan";
import type { AnalysisResult, GameAnalysis } from "@/types";

type Tab = "review" | "plan";

const API = "http://localhost:8000";

export default function Home() {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("review");
  const [selectedGame, setSelectedGame] = useState(0);

  async function runAnalysis(fetchFn: () => Promise<Response>, msg: string) {
    setLoading(true);
    setLoadingMsg(msg);
    setError(null);
    setResult(null);
    try {
      const res = await fetchFn();
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analysis failed");
      }
      const data: AnalysisResult = await res.json();
      setResult(data);
      setSelectedGame(0);
      setActiveTab("review");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function handleUpload(file: File, playerColor: string) {
    const form = new FormData();
    form.append("file", file);
    runAnalysis(
      () => fetch(`${API}/analyze?player_color=${playerColor}`, { method: "POST", body: form }),
      "Analyzing with Stockfish — this may take 1–3 minutes for a full game…"
    );
  }

  function handleSample(playerColor: string) {
    runAnalysis(
      () => fetch(`${API}/sample?player_color=${playerColor}`),
      "Loading sample game…"
    );
  }

  function handlePaste(pgn: string, playerColor: string) {
    runAnalysis(
      () =>
        fetch(`${API}/analyze-text?player_color=${playerColor}`, {
          method: "POST",
          headers: { "Content-Type": "text/plain" },
          body: pgn,
        }),
      "Analyzing pasted PGN…"
    );
  }

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
        <span className="text-2xl">♟</span>
        <h1 className="text-xl font-bold tracking-tight">Chess Trainer</h1>
        {result && (
          <span className="ml-auto text-sm text-gray-400">
            {result.games.length} game{result.games.length !== 1 ? "s" : ""} analyzed
          </span>
        )}
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {!result && !loading && (
          <Upload onUpload={handleUpload} onSample={handleSample} onPaste={handlePaste} />
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-32 gap-4">
            <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-400 text-sm text-center max-w-sm">{loadingMsg}</p>
          </div>
        )}

        {error && (
          <div className="max-w-lg mx-auto mt-12 p-4 bg-red-950 border border-red-800 rounded-lg text-red-300 text-sm">
            <strong>Error:</strong> {error}
            <button
              className="ml-4 underline text-red-400 hover:text-red-200"
              onClick={() => setError(null)}
            >
              Try again
            </button>
          </div>
        )}

        {result && (
          <>
            {result.games.length > 1 && (
              <div className="flex gap-2 mb-4 flex-wrap">
                {result.games.map((g: GameAnalysis, i: number) => (
                  <button
                    key={i}
                    onClick={() => setSelectedGame(i)}
                    className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                      selectedGame === i
                        ? "bg-blue-600 border-blue-500 text-white"
                        : "border-gray-700 text-gray-400 hover:border-gray-500"
                    }`}
                  >
                    Game {i + 1}: {g.white} vs {g.black}
                  </button>
                ))}
              </div>
            )}

            <div className="flex gap-1 mb-6 border-b border-gray-800">
              {(["review", "plan"] as Tab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
                    activeTab === tab
                      ? "border-blue-500 text-blue-400"
                      : "border-transparent text-gray-500 hover:text-gray-300"
                  }`}
                >
                  {tab === "review" ? "Game Review" : "Improvement Plan"}
                </button>
              ))}
            </div>

            {activeTab === "review" && (
              <GameReview game={result.games[selectedGame]} />
            )}
            {activeTab === "plan" && (
              <ImprovementPlan
                patterns={result.patterns}
                topics={result.study_topics}
                accuracy={result.overall_accuracy}
                worstPhase={result.worst_phase}
                gameSummary={result.games[selectedGame]?.game_summary}
              />
            )}

            <div className="mt-6 text-center">
              <button
                onClick={() => { setResult(null); setError(null); }}
                className="text-sm text-gray-500 hover:text-gray-300 underline"
              >
                Upload another game
              </button>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
