# ATS Resume Analyzer

Ever spent hours polishing your resume only to wonder if it's actually going to make it past the automated filters? Yeah, we've been there too. That's why we built this.

This tool takes your resume and a job description, runs them both through Google's Gemini AI, and gives you an honest, evidence-based breakdown of how well you match -- no fluff, no vague encouragement.

---

## What it actually does

- **Scores your resume** against a job description (0-100), with a clear explanation of *why* you got that score
- **Finds missing skills** -- the ones the JD wants that your resume doesn't show
- **Highlights matching skills** -- with direct quotes from your resume as proof
- **Calls out weaknesses** honestly, without softening the blow
- **Gives you actionable suggestions** -- specific edits, not generic advice like "make your resume better"

---

## Built with

- **Flask** -- lightweight Python web server
- **Google Gemini 3.5 Flash** -- the AI brain doing the heavy lifting
- **PyPDF2** -- for pulling text out of your PDF resume
- **Vanilla HTML/CSS/JS** -- clean, fast, no framework overhead

---

## Getting it running locally

You'll need Python 3.10+ and a Gemini API key. If you don't have one, grab it free from [Google AI Studio](https://aistudio.google.com/app/apikey).

```bash
# Clone the repo
git clone https://github.com/EshwarRam22/Ats-analyzer.git
cd Ats-analyzer

# Set up a virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create a .env file and add your API key
echo GEMINI_API_KEY=your_key_here > .env

# Start the server
python main.py
```

Then open your browser and go to `http://127.0.0.1:8000`. Drop in your resume PDF, paste a job description, and hit **Analyze**.

---

## A few things to know

- Only PDF resumes are supported (text-based, not scanned images)
- Maximum file size is 5 MB
- The job description needs to be at least 50 characters -- if it's too vague, the tool will tell you rather than give you a made-up score
- Analysis usually takes 10-20 seconds depending on Gemini's response time

---

## Project structure

```
ats-resume-analyzer/
|-- main.py              # Flask app and all the backend logic
|-- templates/
|   |-- index.html       # The entire frontend (single page)
|-- requirements.txt     # Python dependencies
|-- uploads/             # Temp storage for uploaded PDFs (gitignored)
|-- .env                 # Your API key (never committed)
```

---

## Why the scores are what they are

The AI is instructed to be strict. It won't give you a 90 because your resume *probably* has some relevant experience. Every matching skill needs to be traceable to actual text in your resume. Every missing skill needs to be something the JD explicitly asked for. If a job description is too vague to evaluate against, the tool will say so instead of guessing.

---

## License

MIT -- use it, fork it, do whatever you want with it.
