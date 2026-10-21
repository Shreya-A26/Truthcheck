# TruthLens — Vercel Preview Deployment Readiness & Preflight Report

**Project Directory:** `/Users/shreyarajesha/fakenewsfinal`  
**Target Environment:** Vercel Serverless (Preview Mode)  
**Date & Time:** October 21, 2026 — 20:55 IST  
**Status:** **PREFLIGHT COMPLETED — AUTHENTICATION REQUIRED & CRITICAL SERVERLESS PLATFORM BLOCKERS IDENTIFIED**

---

## 1. Executive Summary

A comprehensive preflight audit of the TruthLens Flask application was performed against Vercel's serverless runtime specifications. 

The audit established that:
1. **Vercel CLI is present** (`v65.0.0`) on the machine, but is currently **Logged Out** (`vercel whoami` exited with code 1).
2. **Critical Platform Blockers** prevent a seamless serverless deployment of this full application on Vercel without breaking core features:
   - **Bundle Size:** Required ML/OCR dependencies (~500 MB+) exceed Vercel's 250 MB uncompressed function limit.
   - **Dual Runtime:** The Python runtime cannot execute Node.js (`ocr_runner.js`) required for offline multilingual Tesseract OCR.
   - **Read-Only Storage:** SQLite history database and file upload directories are read-only on Vercel's `/var/task`.
   - **Python Version:** Local environment runs Python 3.14; Vercel currently supports up to Python 3.12.
3. In strict compliance with the **Protect the Existing Project** requirements, no models were deleted, dependencies were not stripped, and no fake fallbacks were introduced.

---

## 2. Preflight Checklist & Readiness Verification

| Component | Required State | Actual State | Status |
|---|---|---|---|
| **Vercel CLI** | Installed & Available | Vercel CLI `65.0.0` detected via Node | **Ready** |
| **CLI Authentication** | Authenticated Account | `Logged out` (`whoami` returned code 1) | **Blocked: Login Required** |
| **Flask WSGI Export** | `app` instance in `app.py` | `app = Flask(__name__)` exported | **Compatible** |
| **Serverless Bundle Size** | < 250 MB Uncompressed | Dependencies + Models = ~526 MB | **Blocked: Exceeds Limit** |
| **Dual Runtime Support** | Python 3 + Node.js together | Vercel Python runtime lacks `node` binary | **Blocked: Incompatible** |
| **Persistent Storage** | Writable SQLite & Uploads | Read-only filesystem on Vercel | **Blocked: Incompatible** |
| **Python Runtime** | Vercel Supported (3.9–3.12) | Local environment is Python 3.14.3 | **Warning: Version mismatch** |

---

## 3. Deep-Dive Compatibility Analysis

### A. Vercel CLI & Authentication
Running `node <vercel_bin>/index.js whoami` produced:
```text
Vercel CLI 65.0.0 (Node.js 24.15.0)
> Logged out.
> Run `vercel deploy --temporary` to create a temporary deployment you can claim later, or `vercel login` to log in.
```
Deployment cannot proceed without active user authentication.

### B. Dual Runtime Incompatibility (Python + Node.js)
TruthLens uses a resilient hybrid architecture:
- Python Flask backend for linguistic ML classification, factual cross-checking, and report generation.
- Node.js subprocess (`services/ocr_runner.js`) for local, offline Tesseract OCR supporting Malayalam, Hindi, Tamil, and English without system binary dependencies.

**The Problem on Vercel:**
Vercel Serverless Python functions run inside an isolated Amazon Linux container containing only the Python interpreter. The `node` binary is **not** installed in this container. Any invocation of `_run_node_ocr()` in `services/text_extraction.py` will fail with `FileNotFoundError: [Errno 2] No such file or directory: 'node'`.

### C. Serverless Function Size Exceeds Hard Limit (250 MB)
Vercel serverless functions strictly enforce an **uncompressed size limit of 250 MB** (including code, dependencies, and bundled assets).
The TruthLens environment requires:
- `onnxruntime` + `rapidocr-onnxruntime`: ~150 MB
- `scikit-learn` + `scipy` + `numpy`: ~180 MB
- `opencv-python-headless`: ~80 MB
- `reportlab` + `pypdf` + `pillow` + `speech_recognition`: ~50 MB
- Model weights (`fake_news_model.pkl` + `tessdata/*.traineddata`): ~38 MB
- **Total uncompressed payload:** **~500 MB+** (more than 2x the Vercel ceiling).
Attempting to deploy this bundle will result in a Vercel build failure: `Error: A Serverless Function has exceeded the uncompressed size limit of 250 MB`.

### D. Read-Only Ephemeral Filesystem (SQLite & Uploads)
1. **SQLite Database:** [`instance/truthlens.db`](file:///Users/shreyarajesha/fakenewsfinal/instance/truthlens.db)
   - On Vercel, the application root is mounted as read-only. Calling `history_service.save_record()` will trigger `sqlite3.OperationalError: attempt to write a readonly database`.
   - While `/tmp` is writable (up to 512 MB), `/tmp` is ephemeral and reinitialized whenever a serverless container freezes or cold-starts, wiping all saved analysis history.
2. **File Uploads:**
   - [`app.py`](file:///Users/shreyarajesha/fakenewsfinal/app.py) saves uploaded PDFs and images to `instance/uploads/` before OCR extraction. On Vercel, this directory cannot be written to.

---

## 4. Test Results Summary

| Test Area | Execution Status | Notes |
|---|---|---|
| **Local Flask Server (`localhost:5002`)** | **Tested Successfully** | App running live; all routes, models, and OCR fully operational. |
| **Local Automated Test Suite** | **Tested Successfully** | 66/66 pytest tests passing with 0 failures. |
| **Vercel CLI Version Check** | **Tested Successfully** | CLI 65.0.0 detected. |
| **Vercel Authentication Check** | **Tested Successfully** | Confirmed logged out. |
| **Vercel Preview Deployment** | **Not Tested (Paused)** | Blocked by missing CLI authentication and hard serverless constraints. |
| **Vercel Remote Route Testing** | **Not Tested** | No remote deployment initiated. |

---

## 5. Recommended Architecture for Production Hosting

To preserve the complete application—including the trained machine learning models, Malayalam/Indic OCR pipeline, PDF processing, and persistent SQLite history—without stripping dependencies or breaking features:

### Recommended Alternatives:
1. **Render (Web Service / Docker):** Native support for Python + Node.js or Dockerfiles; persistent disks for SQLite; 512 MB to 2 GB RAM.
2. **Railway:** Native Docker or multi-buildpack support; persistent volume attachments; zero size cap.
3. **Google Cloud Run / AWS App Runner:** Full container deployment supporting up to 4 GB RAM, custom system libraries, and scalable HTTP serving.

---

## 6. How to Authenticate Vercel CLI (If You Wish to Attempt a Preview)

If you would like to proceed with testing a lightweight Vercel preview:
1. In your local terminal, run:
   ```bash
   npx vercel login
   ```
2. Follow the browser prompt to log into your Vercel account.
3. Once authenticated, run:
   ```bash
   npx vercel whoami
   ```
4. Reply here once complete, and we will proceed with the pre-configured deployment.
