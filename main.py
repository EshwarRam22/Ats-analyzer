import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from google import genai
import PyPDF2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================
# CONFIG
# =====================
UPLOAD_FOLDER = "uploads"
MAX_PDF_BYTES = 5 * 1024 * 1024  # 5 MB
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__, template_folder="templates")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# =====================
# PROMPT
# =====================
ANALYSIS_PROMPT = """You are a strict, evidence-based ATS and technical resume reviewer.
Your job is to be HONEST, not encouraging. Do not soften weaknesses.
Do not praise vaguely. Every statement you make must be traceable to
actual text in the resume or job description below — never invent,
assume, or guess.

Resume:
{resume_text}

Job Description:
{jd_text}

STEP 1 — Validate the job description first.
If the "Job Description" text does NOT contain identifiable job
requirements, responsibilities, or required skills (e.g. it's a random
sentence, a personal statement, or too short/vague to evaluate against),
you MUST set "valid_input" to false, set "match_score" to null, and
explain why in "validation_note". Do NOT attempt to score in this case.

STEP 2 — If valid, evaluate honestly using ONLY this JSON structure:
{{
  "valid_input": true,
  "validation_note": null,
  "match_score": <integer 0-100>,
  "score_reasoning": "<1-2 sentences explaining exactly why this score, referencing specific matched/missing requirements>",
  "matching_skills": [
    {{
      "skill": "<string>",
      "importance": "must-have" | "nice-to-have",
      "evidence": "<exact phrase or project/experience from the resume that proves this skill>"
    }}
  ],
  "missing_skills": [
    {{
      "skill": "<string>",
      "importance": "must-have" | "nice-to-have",
      "why_it_matters": "<specific reason this skill matters for THIS job, not a generic statement>"
    }}
  ],
  "weaknesses": [
    "<specific, concrete weakness tied to actual resume content>"
  ],
  "suggestions": [
    "<concrete, actionable instruction naming the EXACT section/bullet/skill and the EXACT change to make>"
  ]
}}

If valid_input is false, return:
{{
  "valid_input": false,
  "validation_note": "<reason the JD is invalid>",
  "match_score": null,
  "score_reasoning": null,
  "matching_skills": [],
  "missing_skills": [],
  "weaknesses": [],
  "suggestions": []
}}

STRICT RULES:
- Never use vague filler phrases: no "could be improved," "consider enhancing," "showcase your skills better."
- Every "evidence" field must quote or closely paraphrase something that actually appears in the resume.
- If you cannot find evidence for a skill, do not include it as matching.
- match_score must reflect ONLY what is demonstrable from the resume text — not assumed competence.
- match_score must be an integer, never a range, never a percentage sign.
- If a section has no relevant items, return an empty array, never null.
- Output must be valid JSON parseable by json.loads() with no markdown, no code fences, no text outside the JSON object."""


# =====================
# PDF TEXT EXTRACTION
# =====================
def extract_text_from_pdf(pdf_path):
    """Extract plain text from all pages of a PDF. Returns empty string on failure."""
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            if len(reader.pages) == 0:
                raise ValueError("PDF has no pages")
            for page in reader.pages:
                text += page.extract_text() or ""
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise ValueError(f"Could not read PDF: {e}") from e

    text = text.strip()
    if not text:
        raise ValueError(
            "No text could be extracted from this PDF. "
            "It may be image-based or scanned — try a text-based PDF."
        )
    return text


# =====================
# GEMINI CALL + PARSE
# =====================
def run_ats_analysis(resume_text: str, jd_text: str) -> dict:
    """
    Send resume + JD to Gemini and parse the strict JSON response.
    Returns the parsed dict or raises on failure.
    """
    prompt = ANALYSIS_PROMPT.format(resume_text=resume_text, jd_text=jd_text)

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )
    except Exception as e:
        logger.error("Gemini API call failed: %s", e)
        raise RuntimeError(f"AI service error: {e}") from e

    raw = response.text.strip()

    # Strip accidental code fences Gemini sometimes adds despite the prompt
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed. Raw response: %s", raw[:500])
        raise ValueError("AI returned an unexpected format. Please try again.") from e

    # Validate top-level required keys
    required = {
        "valid_input", "validation_note", "match_score", "score_reasoning",
        "matching_skills", "missing_skills", "weaknesses", "suggestions"
    }
    missing_keys = required - result.keys()
    if missing_keys:
        raise ValueError(f"AI response missing fields: {missing_keys}")

    # If JD was invalid, return early — no score to coerce
    if not result.get("valid_input"):
        return result

    # Coerce match_score to int (guard against Gemini returning a float/string)
    if result["match_score"] is not None:
        result["match_score"] = int(result["match_score"])

    return result


# =====================
# HOME
# =====================
@app.route("/")
def home():
    return render_template("index.html")


# =====================
# ATS ANALYSIS ROUTE
# =====================
@app.route("/analyze", methods=["POST"])
def analyze_resume():
    # --- Input validation ---
    if "resume" not in request.files:
        return jsonify({"error": "Resume PDF is required"}), 400

    resume_file = request.files["resume"]
    jd_text = request.form.get("job_description", "").strip()

    if not resume_file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not resume_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    if not jd_text:
        return jsonify({"error": "Job description is required"}), 400

    if len(jd_text) < 50:
        return jsonify({"error": "Job description seems too short — please paste the full text"}), 400

    # --- File size check (before saving) ---
    resume_file.seek(0, 2)  # seek to end
    file_size = resume_file.tell()
    resume_file.seek(0)
    if file_size > MAX_PDF_BYTES:
        return jsonify({"error": "PDF exceeds 5 MB limit"}), 400

    # --- Save + extract ---
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], resume_file.filename)
    resume_file.save(save_path)

    try:
        resume_text = extract_text_from_pdf(save_path)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422

    # --- Gemini analysis ---
    try:
        result = run_ats_analysis(resume_text, jd_text)
    except ValueError as e:
        return jsonify({"error": str(e)}), 502
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify(result), 200


# =====================
# RUN SERVER
# =====================
if __name__ == "__main__":
    app.run(debug=True, port=8000)
