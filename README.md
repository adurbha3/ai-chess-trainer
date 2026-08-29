# AI Chess Trainer

Upload a PGN and get move-by-move analysis, mistake classification, and an
improvement plan powered by Stockfish.

- **Frontend** — Next.js app for uploading games, reviewing moves on a
  board, and viewing the improvement plan (`frontend/`).
- **Backend** — FastAPI service that parses PGNs, runs Stockfish
  evaluations, classifies mistakes, and generates coaching notes
  (`backend/`).

## Prerequisites

- Node.js 18+
- Python 3.10+
- [Stockfish](https://stockfishchess.org/) installed locally

By default the backend expects Stockfish at `/opt/homebrew/bin/stockfish`
(see `STOCKFISH_PATH` in [backend/analyzer.py](backend/analyzer.py)). Update
that path if your install lives elsewhere, e.g. via Homebrew:

```bash
brew install stockfish
```

## Setup

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

## Running

From the project root, start both servers at once:

```bash
./start.sh
```

Or run them individually:

```bash
# Backend (http://localhost:8000)
cd backend && .venv/bin/uvicorn main:app --reload --port 8000

# Frontend (http://localhost:3000)
cd frontend && npm run dev
```

## API

- `POST /analyze` — upload a PGN file for analysis
- `POST /analyze-text` — analyze a PGN passed as raw text
- `GET /sample` — analyze the bundled `test.pgn`
- `GET /health` — health check

## Project structure

```
backend/
  main.py         FastAPI app and routes
  analyzer.py     PGN parsing + Stockfish evaluation
  classifier.py   Move/mistake classification
  patterns.py     Recurring pattern detection across games
  coach.py        Coaching note generation
  features.py     Position feature extraction

frontend/
  app/            Next.js app router pages
  components/     Upload, GameReview, ImprovementPlan
  types/          Shared TypeScript types
```
