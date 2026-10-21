# TruthLens — AI-Based News Credibility Analysis Platform

> **“Look Beyond the Headline.”**  
> *Understand the claim. Examine the evidence. Make an informed decision.*

TruthLens is a digital platform designed to help ordinary citizens, researchers, and journalists investigate news before believing or sharing it. Combining an evaluated statistical natural language processing model with transparent linear coefficient explainability, external evidence retrieval, and printable editorial dossiers, TruthLens emphasizes human judgment rather than algorithmic black-box dictation.

---

## Key Features

1. **Multi-Modal News Input Workspace**
   - **Paste Text:** Clean, accessible text area with live token and character counters.
   - **News URL:** Secure, SSRF-protected extraction of remote web articles, publisher metadata, author attribution, and publication dates.
   - **PDF Document Upload:** Selectable PDF document parsing up to 15 pages via `pypdf`.
   - **Image OCR:** Visible text extraction from news screenshots via `pytesseract` and Pillow.
   - **Video Frame OCR:** Sampled frame processing (up to 10 frames) to read onscreen news tickers and headlines using OpenCV.

2. **Evaluated Machine Learning Pipeline**
   - **Architecture:** Sublinear TF-IDF (unigrams & bigrams, max 50,000 features) + L2-regularized Logistic Regression.
   - **Empirical Accuracy:** 99.08% test accuracy on held-out evaluation splits.
   - **Transparent Explainability:** Direct mathematical extraction of individual word and phrase coefficient weights for each specific submission.
   - **Documented Uncertainty Bounds:** Explicit abstention rule returning *Uncertain* when classification probabilities fall within borderline bands (45%–55%) or on insufficient text.

3. **Investigative Dossiers & Reporting**
   - **Editorial Analysis View:** Clear visual hierarchy presenting the model prediction (*Likely Credible*, *Likely Misleading*, or *Uncertain*), confidence percentage, processed word count, and plain-language explanation.
   - **Independent Claim Verification:** Splits articles into key assertions and queries real news feeds for corroborating or debunking coverage without fabrication.
   - **Cross-Source Comparison:** Shows related coverage across distinct publishers.
   - **Downloadable PDF Reports:** Editorial-grade printable dossiers generated in-memory via ReportLab.

4. **History & Ephemeral Privacy**
   - **SQLite Analysis History:** Minimal structured records retained for reader review, with full capability to delete single items or purge history.
   - **Ephemeral Processing:** Uploaded PDFs, images, and videos are processed in temporary memory and deleted immediately after text extraction.

5. **Defense-in-Depth Security**
   - **SSRF Defense:** Comprehensive DNS resolution and IP address validation blocking loopback (`127.0.0.0/8`, `::1`), private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local/cloud metadata (`169.254.169.254`), and non-HTTP/HTTPS schemes.
   - **File Validation:** Size limits (15 MB docs, 25 MB video), extension allowlisting, and secure filename sanitization.
   - **Security Headers:** Strict CSP, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and `X-XSS-Protection`.

---

## Project Structure

```
fakenewsfinal/
├── app.py                      # Flask application entry point & routes
├── config.py                   # Central configuration & security limits
├── requirements.txt            # Pinned Python dependencies
├── .env.example                # Example environment configuration
├── .gitignore                  # Git ignore rules
├── README.md                   # Project documentation
├── models/
│   ├── fake_news_model.pkl     # Pre-trained TF-IDF + Logistic Regression pipeline
│   └── metadata.json           # Model metadata & evaluation metrics
├── services/
│   ├── model_service.py        # Model loading, inference, uncertainty, feature weights
│   ├── article_extraction.py   # SSRF-protected URL fetching & BeautifulSoup parsing
│   ├── text_extraction.py      # PDF, Image OCR, and Video frame text extraction
│   ├── claim_verification.py   # Claim isolation and live news corroboration
│   ├── source_comparison.py    # Cross-source publisher comparison
│   └── history_service.py      # SQLite persistence & deletion management
├── reports/
│   └── report_generator.py     # ReportLab editorial PDF dossier generator
├── templates/
│   ├── base.html               # Master layout, SVG logo, navigation, footer
│   ├── index.html              # Homepage with 5-tab workspace & methodology overview
│   ├── results.html            # Investigative dossier report view
│   ├── history.html            # Saved assessment log
│   ├── performance.html        # Academic performance benchmarks & confusion matrix
│   ├── about.html              # Brand philosophy & methodology guide
│   └── privacy.html            # Privacy disclosures & technical boundaries
├── static/
│   ├── css/style.css           # Editorial design system, typography, accessibility
│   └── js/app.js               # Tab controls, drag-and-drop zones, word counters
└── tests/
    ├── test_model.py           # Model loading, predictions, and term influence tests
    ├── test_routes.py          # Web routes, submission flows, and PDF generation tests
    ├── test_security.py        # SSRF IP blacklisting and URL scheme validation tests
    └── test_extraction.py      # PDF parsing and corrupt file handling tests
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+ (tested through Python 3.14)
- Virtual environment support
- *(Optional)* Tesseract OCR for image text extraction (`brew install tesseract` on macOS or `sudo apt-get install tesseract-ocr` on Linux)

### 1. Clone & Enter Directory
```bash
cd /Users/shreyarajesha/fakenewsfinal
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify Model Files
Ensure the model files are present in `models/`:
- `models/fake_news_model.pkl`
- `models/metadata.json`

---

## Running the Application

### Development Server
```bash
python3 app.py
```
Open [http://127.0.0.1:5002](http://127.0.0.1:5002) in your browser.

### Production Server (Gunicorn)
```bash
gunicorn --workers 3 --bind 0.0.0.0:5002 app:app
```

---

## Running the Automated Test Suite

TruthLens includes a full test suite covering model inference, SSRF protection, routing, extraction, and PDF generation:

```bash
PYTHONPATH=. pytest tests/ -v
```

All 20 tests pass with 100% success.

---

## System Boundaries & Ethical Disclaimers

1. **Statistical Correlation vs. Absolute Truth:** Machine learning classifications reflect lexical and stylistic proximity to known datasets. A prediction of *Likely Credible* indicates journalistic formatting and vocabulary patterns; it does not constitute legal or factual verification.
2. **OCR Boundaries:** Image and video processing extracts visible text. It does not certify photography metadata, detect Photoshop manipulation, or detect deepfakes.
3. **External News Verification:** When public news search feeds are reachable, TruthLens extracts genuine headlines from established newsrooms. When unavailable, it transparently indicates that external corroboration could not be retrieved rather than fabricating sources.

---

## License
Created for academic and public news credibility research. All rights reserved.
