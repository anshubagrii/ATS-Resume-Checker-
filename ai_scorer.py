import os
import json
import re
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

DEFAULT_MODEL = "gemini-2.5-flash"

RESEARCH_PROMPT_TEMPLATE = """Based on current job postings and hiring guidance you can find,
research what a genuinely competitive resume looks like right now for this role:

{jd_text}

Summarize in 5-8 short bullet points:
- Which skills/tools are actually in-demand for this role today (beyond what's literally in the JD)
- How strong candidates typically present experience for this kind of role (scope, metrics, seniority signals)
- Any recent shifts in what recruiters or ATS systems screen for in this field

Be concise and factual. Do not fabricate sources. Plain text bullets only, no headers."""

SCORING_SYSTEM_PROMPT = """You are an experienced technical recruiter and ATS auditor.
Score the resume against the job description AND against the current market context
you're given (real hiring standards for this type of role, not just this one JD).

Weight the score roughly like this — it should NOT be a keyword-matching score:
- Keyword / skill term overlap with the JD: ~15% of the score
- Depth and relevance of actual experience/projects vs what the role needs: ~30%
- Quality of impact — quantified, specific achievements vs vague duty-listing: ~25%
- How the resume stacks up against current market expectations for this role
  (using the market context provided): ~20%
- ATS-safe structure/formatting: ~10%

Return ONLY a JSON object, no preamble, no markdown fences, matching this exact shape:

{
  "ats_score": <integer 0-100, reflecting the holistic weighting above>,
  "matched_keywords": [<a SHORT list, 5-8 max, of the most important overlapping terms>],
  "missing_keywords": [<a SHORT list, 3-6 max, of the most important missing terms>],
  "formatting_issues": [<strings, ATS-unfriendly formatting found>],
  "suggestions": [<3 to 5 short, specific, actionable fixes, prioritizing experience/impact
                   over keyword-stuffing>],
  "market_comparison": "<2-4 sentences on how this resume compares to what's currently
                         competitive for this type of role, grounded in the market context>"
}

Be honest — do not inflate the score to be encouraging."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ats_score": {"type": "INTEGER"},
        "matched_keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "missing_keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "formatting_issues": {"type": "ARRAY", "items": {"type": "STRING"}},
        "suggestions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "market_comparison": {"type": "STRING"},
    },
    "required": [
        "ats_score",
        "matched_keywords",
        "missing_keywords",
        "formatting_issues",
        "suggestions",
        "market_comparison",
    ],
}

REWRITE_SYSTEM_PROMPT = """You are a senior resume writer who specializes in resumes that
pass ATS screening AND read as genuinely written by the candidate, not by AI.

Rewrite the resume to be a stronger match for the job description, using only what's true
in the original resume. Hard rules:

1. Never invent employers, job titles, dates, degrees, certifications, or tools the person
   never mentioned. You may sharpen and quantify existing bullet points, but don't fabricate
   metrics that aren't implied by the original content.
2. Only weave in a missing keyword if the original resume's actual experience/projects
   plausibly support it. Skip any that don't fit — do not force keyword stuffing.
3. Avoid AI-sounding writing: no "leverage," "utilize," "spearheaded," "dynamic,"
   "passionate," "results-driven," "synergy," "cutting-edge," "seamlessly," "robust,"
   "game-changer," or similar buzzword filler. Vary sentence length and structure between
   bullets — don't repeat the same "Verb + adjective + metric" template every line.
   Avoid stacking em dashes.
4. Keep it ATS-safe: single column, plain section headers (Summary, Skills, Experience,
   Projects, Education), reverse-chronological, plain "-" bullets, no tables, no graphics,
   no headers/footers, consistent date format.
5. Output plain text only — the exact resume content, ready to paste into a document.
   No commentary before or after it, no markdown formatting, no code fences."""


class ScoringError(Exception):
    pass


def analyze_resume(resume_text, jd_text, layout_flags):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ScoringError(
            "No API key configured. Add GEMINI_API_KEY to your .env file."
        )

    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    client = genai.Client(api_key=api_key)

    market_context = _research_market_context(client, model, jd_text)

    user_content = f"""JOB DESCRIPTION:
{jd_text.strip()}

RESUME TEXT:
{resume_text.strip()}

KNOWN LAYOUT SIGNALS (from PDF parsing, factor into formatting_issues if relevant):
- Pages: {layout_flags['page_count']}
- Contains tables: {layout_flags['has_tables']}
- Multi-column layout detected: {layout_flags['multi_column']}

CURRENT MARKET CONTEXT (researched separately, use this to judge competitiveness —
if empty, score using your own knowledge of hiring standards instead):
{market_context if market_context else "(unavailable — use general knowledge)"}
"""

    try:
        response = client.models.generate_content(
            model=model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=SCORING_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                max_output_tokens=3000,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except genai_errors.ClientError as exc:
        if "API_KEY_INVALID" in str(exc) or "PERMISSION_DENIED" in str(exc):
            raise ScoringError("Invalid API key.") from exc
        if "RESOURCE_EXHAUSTED" in str(exc):
            raise ScoringError("Rate limit hit. Try again in a moment.") from exc
        raise ScoringError(f"Gemini API error: {exc}") from exc
    except genai_errors.ServerError as exc:
        raise ScoringError(f"Gemini API is unavailable right now: {exc}") from exc

    finish_reason = None
    if response.candidates:
        finish_reason = response.candidates[0].finish_reason

    if finish_reason == "MAX_TOKENS" or not response.text:
        raise ScoringError(
            "The model's response got cut off before finishing. "
            "Try a shorter job description, or raise max_output_tokens in ai_scorer.py."
        )
    if finish_reason == "SAFETY":
        raise ScoringError("The response was blocked by Gemini's safety filters.")

    return _parse_json_response(response.text)


def _research_market_context(client, model, jd_text):
    """Best-effort grounded research. Returns '' on any failure so scoring
    can still proceed without it."""
    try:
        response = client.models.generate_content(
            model=model,
            contents=RESEARCH_PROMPT_TEMPLATE.format(jd_text=jd_text.strip()[:3000]),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                max_output_tokens=800,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return (response.text or "").strip()
    except Exception:
        return ""


def generate_optimized_resume(resume_text, jd_text, missing_keywords, suggestions):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ScoringError(
            "No API key configured. Add GEMINI_API_KEY to your .env file."
        )

    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    client = genai.Client(api_key=api_key)

    user_content = f"""JOB DESCRIPTION:
{jd_text.strip()}

ORIGINAL RESUME:
{resume_text.strip()}

Keywords the original resume is missing (only include if truthfully supported by the
candidate's actual experience/projects above): {", ".join(missing_keywords) or "none"}

Fixes identified in the earlier review to incorporate: {"; ".join(suggestions) or "none"}
"""

    try:
        response = client.models.generate_content(
            model=model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=REWRITE_SYSTEM_PROMPT,
                max_output_tokens=3000,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                temperature=0.7,
            ),
        )
    except genai_errors.ClientError as exc:
        if "API_KEY_INVALID" in str(exc) or "PERMISSION_DENIED" in str(exc):
            raise ScoringError("Invalid API key.") from exc
        if "RESOURCE_EXHAUSTED" in str(exc):
            raise ScoringError("Rate limit hit. Try again in a moment.") from exc
        raise ScoringError(f"Gemini API error: {exc}") from exc
    except genai_errors.ServerError as exc:
        raise ScoringError(f"Gemini API is unavailable right now: {exc}") from exc

    finish_reason = None
    if response.candidates:
        finish_reason = response.candidates[0].finish_reason

    if finish_reason == "MAX_TOKENS" or not response.text:
        raise ScoringError(
            "The rewrite got cut off before finishing. Try again, or raise "
            "max_output_tokens in generate_optimized_resume()."
        )

    return response.text.strip()


def _parse_json_response(raw_text):
    cleaned = re.sub(r"```json|```", "", raw_text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ScoringError("Could not parse the model's response.") from exc

    required = {
        "ats_score",
        "matched_keywords",
        "missing_keywords",
        "formatting_issues",
        "suggestions",
        "market_comparison",
    }
    if not required.issubset(data.keys()):
        raise ScoringError("Model response was missing expected fields.")

    data["ats_score"] = max(0, min(100, int(data["ats_score"])))
    return data
