export interface MoveAnnotation {
  move_number: number;
  color: "white" | "black";
  san: string;
  uci: string;
  fen_before: string;
  fen_after: string;
  eval_before: number | null;
  eval_after: number | null;
  cp_loss: number | null;
  classification: "brilliant" | "good" | "inaccuracy" | "mistake" | "blunder";
  best_move_san: string | null;
  best_move_uci: string | null;
  mistake_category: string | null;
  mistake_signals: string[];
  coaching_note: string | null;
  features_before: Record<string, number> | null;
  features_after: Record<string, number> | null;
}

export interface GameAnalysis {
  game_index: number;
  parse_error: string;
  white: string;
  black: string;
  result: string;
  date: string;
  game_summary: string;
  moves: MoveAnnotation[];
  blunder_count: number;
  mistake_count: number;
  inaccuracy_count: number;
  avg_cp_loss_white: number;
  avg_cp_loss_black: number;
}

export interface Pattern {
  type: string;
  // structural pattern fields (new)
  category?: string;
  move_numbers?: number[];
  count?: number;
  blunder_count?: number;
  mistake_count?: number;
  inaccuracy_count?: number;
  avg_cp_loss?: number;
  // legacy phase/piece fields
  phase?: string;
  piece?: string;
  severity: "high" | "medium" | "low";
  description: string;
}

export interface StudyTopic {
  topic: string;
  reason: string;
  resources: string[];
  priority: "high" | "medium" | "low";
}

export interface AnalysisResult {
  games: GameAnalysis[];
  patterns: Pattern[];
  study_topics: StudyTopic[];
  overall_accuracy: number;
  worst_phase: string;
}
