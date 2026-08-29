"use client";

import { useState, useRef, DragEvent } from "react";

interface Props {
  onUpload: (file: File, playerColor: string) => void;
  onSample: (playerColor: string) => void;
  onPaste: (pgn: string, playerColor: string) => void;
}

type Mode = "file" | "paste";

export default function Upload({ onUpload, onSample, onPaste }: Props) {
  const [mode, setMode] = useState<Mode>("file");
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [pgnText, setPgnText] = useState("");
  const [playerColor, setPlayerColor] = useState("both");
  const inputRef = useRef<HTMLInputElement>(null);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.name.endsWith(".pgn")) setFile(dropped);
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0];
    if (picked?.name.endsWith(".pgn")) setFile(picked);
  }

  const colorButtons = [
    { value: "white", label: "White" },
    { value: "black", label: "Black" },
    { value: "both", label: "Both" },
  ];

  const canSubmit = mode === "file" ? !!file : pgnText.trim().length > 10;

  function handleSubmit() {
    if (mode === "file" && file) onUpload(file, playerColor);
    else if (mode === "paste" && pgnText.trim()) onPaste(pgnText.trim(), playerColor);
  }

  return (
    <div className="max-w-xl mx-auto mt-16 flex flex-col gap-6">
      <div className="text-center">
        <h2 className="text-2xl font-semibold mb-2">Upload your PGN file</h2>
        <p className="text-gray-400 text-sm">
          Analyze your chess games with Stockfish and get a personalized improvement plan.
        </p>
      </div>

      {/* Mode toggle */}
      <div className="flex rounded-lg bg-gray-900 p-1 gap-1">
        {(["file", "paste"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex-1 py-1.5 text-sm rounded-md transition-colors font-medium ${
              mode === m ? "bg-gray-700 text-white" : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {m === "file" ? "Upload File" : "Paste PGN"}
          </button>
        ))}
      </div>

      {mode === "file" ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
            dragging
              ? "border-blue-500 bg-blue-950/30"
              : file
              ? "border-green-600 bg-green-950/20"
              : "border-gray-700 hover:border-gray-500"
          }`}
        >
          <input ref={inputRef} type="file" accept=".pgn" className="hidden" onChange={handleFile} />
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <span className="text-3xl">✓</span>
              <p className="font-medium text-green-400">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 text-gray-500">
              <span className="text-4xl">♟</span>
              <p className="text-sm">Drag & drop a .pgn file or click to browse</p>
            </div>
          )}
        </div>
      ) : (
        <textarea
          className="w-full h-40 bg-gray-900 border border-gray-700 rounded-xl p-3 text-sm font-mono text-gray-200 resize-none focus:outline-none focus:border-blue-500"
          placeholder={'Paste your PGN here...\n\n[Event "My Game"]\n[White "Me"]\n[Black "Opponent"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 ...'}
          value={pgnText}
          onChange={(e) => setPgnText(e.target.value)}
        />
      )}

      {/* Player color */}
      <div className="flex flex-col gap-2">
        <label className="text-sm text-gray-400 font-medium">Analyze as</label>
        <div className="flex gap-2">
          {colorButtons.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setPlayerColor(opt.value)}
              className={`flex-1 py-2 px-3 rounded-lg border text-sm transition-colors ${
                playerColor === opt.value
                  ? "border-blue-500 bg-blue-600 text-white"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <button
        disabled={!canSubmit}
        onClick={handleSubmit}
        className="py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-30 disabled:cursor-not-allowed font-semibold transition-colors"
      >
        Analyze Game
      </button>

      <div className="text-center">
        <button
          onClick={() => onSample(playerColor)}
          className="text-sm text-gray-500 hover:text-blue-400 underline transition-colors"
        >
          Or try a sample game →
        </button>
      </div>
    </div>
  );
}
