import os
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv

import database
from resume_parser import extract_resume, ResumeParseError
from ai_scorer import analyze_resume, generate_optimized_resume, ScoringError

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB upload cap

database.init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    resume_file = request.files.get("resume")
    jd_text = (request.form.get("job_description") or "").strip()

    if not resume_file or resume_file.filename == "":
        flash("Please attach a resume PDF.", "error")
        return redirect(url_for("index"))

    if not resume_file.filename.lower().endswith(".pdf"):
        flash("Only PDF resumes are supported right now.", "error")
        return redirect(url_for("index"))

    if len(jd_text) < 30:
        flash("Paste the full job description for an accurate score.", "error")
        return redirect(url_for("index"))

    try:
        resume_text, layout_flags = extract_resume(resume_file.stream)
    except ResumeParseError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    try:
        result = analyze_resume(resume_text, jd_text, layout_flags)
    except ScoringError as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    check_id = database.save_check(resume_file.filename, resume_text, jd_text, result)
    return redirect(url_for("result", check_id=check_id))


@app.route("/result/<int:check_id>")
def result(check_id):
    check = database.get_check(check_id)
    if check is None:
        flash("That result doesn't exist anymore.", "error")
        return redirect(url_for("index"))
    return render_template("result.html", check=check)


@app.route("/optimize/<int:check_id>")
def optimize(check_id):
    check = database.get_check(check_id)
    if check is None:
        flash("That result doesn't exist anymore.", "error")
        return redirect(url_for("index"))

    regenerate = request.args.get("regenerate") == "1"

    if check["optimized_resume"] and not regenerate:
        return render_template("optimized.html", check=check)

    try:
        optimized_text = generate_optimized_resume(
            check["resume_text"],
            check["jd_text"],
            check["missing_keywords"],
            check["suggestions"],
        )
    except ScoringError as exc:
        flash(str(exc), "error")
        return redirect(url_for("result", check_id=check_id))

    database.save_optimized_resume(check_id, optimized_text)
    check["optimized_resume"] = optimized_text
    return render_template("optimized.html", check=check)


@app.route("/history")
def history():
    checks = database.get_history()
    return render_template("history.html", checks=checks)


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
