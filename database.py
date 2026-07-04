import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "instance" / "ats.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_filename TEXT NOT NULL,
    resume_text TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    ats_score INTEGER NOT NULL,
    matched_keywords TEXT NOT NULL,
    missing_keywords TEXT NOT NULL,
    formatting_issues TEXT NOT NULL,
    suggestions TEXT NOT NULL,
    market_comparison TEXT NOT NULL DEFAULT '',
    optimized_resume TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def save_check(resume_filename, resume_text, jd_text, result):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO checks
           (resume_filename, resume_text, jd_text, ats_score, matched_keywords,
            missing_keywords, formatting_issues, suggestions, market_comparison)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            resume_filename,
            resume_text,
            jd_text,
            result["ats_score"],
            json.dumps(result["matched_keywords"]),
            json.dumps(result["missing_keywords"]),
            json.dumps(result["formatting_issues"]),
            json.dumps(result["suggestions"]),
            result.get("market_comparison", ""),
        ),
    )
    conn.commit()
    check_id = cur.lastrowid
    conn.close()
    return check_id


def save_optimized_resume(check_id, optimized_text):
    conn = get_connection()
    conn.execute(
        "UPDATE checks SET optimized_resume = ? WHERE id = ?",
        (optimized_text, check_id),
    )
    conn.commit()
    conn.close()


def get_check(check_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


def get_history():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row):
    d = dict(row)
    d["matched_keywords"] = json.loads(d["matched_keywords"])
    d["missing_keywords"] = json.loads(d["missing_keywords"])
    d["formatting_issues"] = json.loads(d["formatting_issues"])
    d["suggestions"] = json.loads(d["suggestions"])
    return d
