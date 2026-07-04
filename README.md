# Scanline — AI-Powered ATS Resume Checker

Upload a resume (PDF) + paste a job description, and get a holistic read on
how it'll do — not a literal keyword match, but a score weighted toward
actual experience depth, quantified impact, and how the resume stacks up
against current hiring standards for that role, researched live via Google
Search grounding. You can then generate a rewritten, ATS-safe version of the
resume tailored to the role, without it reading like AI wrote it.

## Setup

```bash
cd ats-checker
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Add your API key:

```bash
cp .env.example .env
```

Open `.env` and paste your key:

```
GEMINI_API_KEY=your-key-here
```

Get a key at https://aistudio.google.com/apikey — the key is only ever read
server-side in `ai_scorer.py` and never sent to the browser.

## Run

```bash
python3 app.py
```

Visit http://127.0.0.1:5000

## How scoring works

Each scan makes two Gemini calls (`ai_scorer.py`):

1. **Research call** — grounded with Google Search, looks up what a genuinely
   competitive resume looks like right now for this type of role (in-demand
   skills, how strong candidates present experience, recent shifts in what
   recruiters screen for). Best-effort: if it fails, scoring still proceeds
   using the model's own knowledge.
2. **Scoring call** — strict JSON output (schema-enforced) combining the
   resume, the job description, and the research from step 1. Keyword
   overlap is deliberately weighted at ~15% of the score; the rest comes
   from experience relevance, quantified impact, market fit, and formatting.

## Resume rewriter

From any result page, "Generate optimized resume" calls
`generate_optimized_resume()`, which rewrites the resume for the role under
strict rules: never invents employers, dates, degrees, or skills the person
doesn't have; only weaves in missing keywords the original experience
actually supports; and is explicitly instructed to avoid AI-sounding
buzzwords and repetitive bullet templates. Output is stored per-check in
SQLite so revisiting the result doesn't cost another API call — use
"Regenerate" on the output page to force a fresh version.

## Project structure

```
ats-checker/
├── app.py                Flask routes
├── database.py            SQLite (resume/JD text + score history)
├── resume_parser.py       PDF text + layout extraction (pdfplumber)
├── ai_scorer.py            Gemini API calls: research, scoring, rewriting
├── requirements.txt
├── .env.example            copy to .env, key stays empty in git
├── templates/
│   ├── base.html
│   ├── index.html          upload form
│   ├── result.html          score breakdown + market comparison
│   ├── optimized.html       rewritten resume output
│   └── history.html
└── static/
    ├── style.css
    ├── script.js            theme toggle
    └── upload.js            dropzone + form behavior
```

## Deploying it live (Render)

1. Push this folder to a GitHub repo (`.env` and `instance/*.db` are already
   gitignored, so your key and local history won't be committed).
2. On [render.com](https://render.com), New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt`
   Start command: `gunicorn app:app --bind 0.0.0.0:$PORT` (already in `Procfile`)
4. Under Environment, add `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`) —
   never commit these, set them in the dashboard.
5. Deploy. You'll get a `https://your-app.onrender.com` URL.

Free tier notes: the service sleeps after 15 minutes idle (first request
after that takes up to ~a minute to wake up), and the SQLite file resets on
redeploy/restart since free-tier disk isn't persistent — fine for a demo/
portfolio link, but don't rely on it to keep history long-term. If you want
that, upgrade to a Render persistent disk or move `checks` to a hosted
Postgres later.

## Notes

- Resumes must be text-based PDFs (not scanned images) — the app will tell
  you if it can't extract text.
- History (including full resume/JD text, for the rewrite feature) is stored
  locally in `instance/ats.db` (SQLite), no login system.
- Swap models by changing `GEMINI_MODEL` in `.env`. Note: `thinking_budget`
  is Gemini 2.5-series syntax; if you switch to a 3.x model, Google's newer
  `thinking_level` parameter may be needed instead.
- Upload cap is 8MB, set in `app.py` (`MAX_CONTENT_LENGTH`).
