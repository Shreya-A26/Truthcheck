import os
import re
import uuid
import logging
import concurrent.futures
from pathlib import Path
from flask import (
    Flask, render_template, request, redirect, url_for, flash, 
    jsonify, send_file, abort, Response
)
from werkzeug.utils import secure_filename

from config import Config
from services.model_service import ModelService
from services.article_extraction import (
    extract_article_from_url, SSRFException, ArticleExtractionException
)
from services.text_extraction import (
    extract_text_from_pdf, extract_text_from_image,
    TextExtractionException
)
from services.claim_verification import ClaimVerificationService, normalize_claim_text
from services.source_comparison import SourceComparisonService
from services.history_service import HistoryService
from services.multilingual_service import MultilingualService
from reports.report_generator import generate_pdf_report

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("truthlens")

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

# Initialize core services
logger.info("Initializing TruthLens backend services...")
model_service = ModelService(app.config['MODEL_PATH'], app.config['METADATA_PATH'])
claim_service = ClaimVerificationService(api_key=app.config.get('NEWS_API_KEY', ''))
comparison_service = SourceComparisonService()
history_service = HistoryService(app.config['DATABASE_PATH'])
multilingual_service = MultilingualService(
    enabled=app.config.get('ENABLE_MULTILINGUAL', True),
    timeout=app.config.get('TRANSLATION_TIMEOUT', 5)
)

# Security Headers middleware
@app.after_request
def set_security_headers(response: Response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "script-src 'self' 'unsafe-inline';"
    )
    return response

# --- Core Web Page Routes ---

@app.route('/')
def index():
    if request.args.get('view') == 'editorial' or request.args.get('home') == '1':
        return render_template('home.html')
    return render_template('index.html')

@app.route('/home')
@app.route('/editorial')
def home():
    return render_template('home.html')

@app.route('/analyze', methods=['GET'])
def analyze_workspace():
    return render_template('index.html')

@app.route('/about')
@app.route('/methodology')
def about():
    return render_template('about.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/performance')
def performance():
    metadata = model_service.get_metadata()
    return render_template('performance.html', metadata=metadata)

@app.route('/history')
def history():
    records = history_service.get_all(limit=50)
    return render_template('history.html', records=records)

@app.route('/history/delete/<record_id>', methods=['POST'])
def delete_history_route(record_id):
    history_service.delete_by_id(record_id)
    flash("Record removed from analysis history.", "info")
    return redirect(url_for('history'))

@app.route('/history/clear', methods=['POST'])
def clear_history_route():
    history_service.clear_all()
    flash("All analysis history has been permanently cleared.", "info")
    return redirect(url_for('history'))

@app.route('/result/<record_id>')
def view_result_record(record_id):
    rec = history_service.get_by_id(record_id)
    if not rec:
        flash("The requested analysis record could not be found.", "error")
        return redirect(url_for('history'))
        
    result_data = rec.get("result", {})
    return render_template('results.html', result=result_data)

# --- Analysis Handlers ---

def _run_full_credibility_pipeline(text: str, input_type: str, article_title: str = "", source_info: dict = None) -> dict:
    """Helper to run ML model, claim extraction, external verification, and source comparison."""
    if not source_info:
        source_info = {
            "domain": "Direct Input",
            "author": "Not specified",
            "publication_date": "Not available",
            "original_url": ""
        }

    # 0. Consistent Input Normalization
    text_normalized = normalize_claim_text(text)
    logger.info(f"[PIPELINE-START] Input Type: {input_type} | Normalized Input: '{text_normalized[:120]}'")

    # Multilingual Language Detection (Isolated Modular Layer)
    lang_info = {"code": "en", "name": "English", "is_english": True}
    if multilingual_service.enabled:
        lang_info = multilingual_service.detect_language(text_normalized)

    is_multilingual = not lang_info["is_english"]
    translated_text = ""
    verification_text = text_normalized

    # Extract and normalize derived title early
    derived_title = article_title
    if not derived_title:
        first_line = text_normalized.split('\n')[0].strip()
        derived_title = (first_line[:110] + '...') if len(first_line) > 110 else first_line
    derived_title = normalize_claim_text(derived_title)
    if not derived_title:
        derived_title = "Untitled Article Submission"

    search_title = derived_title

    # Multilingual Processing Path (Malayalam, Hindi, Tamil)
    if is_multilingual:
        logger.info(f"[MULTILINGUAL-INPUT] Detected language: {lang_info['name']} ({lang_info['code']})")
        trans_res = multilingual_service.translate_to_english(text_normalized, lang_info["code"])
        
        # If translation fails, gracefully return cautious unverified response
        if not trans_res.get("success"):
            logger.warning(f"[MULTILINGUAL-FAILED] Translation unavailable for {lang_info['code']}: {trans_res.get('error')}")
            cautious_dossier = {
                "id": str(uuid.uuid4()),
                "created_at": history_service._get_connection().execute("SELECT datetime('now')").fetchone()[0] + " UTC",
                "article_title": derived_title,
                "input_type": input_type,
                "source_info": source_info,
                "prediction_label": "NOT YET VERIFIED",
                "confidence": 50.0,
                "probabilities": {"fake": 50.0, "real": 50.0},
                "word_count": len(text_normalized.split()),
                "explanation": (
                    f"This article was submitted in {lang_info['name']}. External translation and multilingual "
                    f"verification services are currently unreachable. Independent confirmation from authoritative "
                    f"regional news sources is recommended."
                ),
                "feature_contributions": [],
                "status_badge": "warning",
                "model_type": model_service.metadata.get("model_type", "TF-IDF + Logistic Regression"),
                "test_accuracy": model_service.metadata.get("test_accuracy", 0.9908),
                "verification": {"available": False, "claims": [], "overall_verdict": "UNAVAILABLE"},
                "comparison": {"sources": []},
                "top_sources": [],
                "language": lang_info["code"],
                "language_name": lang_info["name"],
                "original_text": text_normalized,
                "translated_text": ""
            }
            history_service.save_analysis(
                title=derived_title,
                input_type=input_type,
                prediction="NOT YET VERIFIED",
                confidence=50.0,
                verification_status="Translation Unavailable",
                result_data=cautious_dossier
            )
            return cautious_dossier

        translated_text = trans_res["translated_text"]
        verification_text = translated_text
        search_title = (translated_text.split('\n')[0].strip()[:110] + '...') if len(translated_text.split('\n')[0].strip()) > 110 else translated_text.split('\n')[0].strip()
        logger.info(f"[MULTILINGUAL-TRANSLATED] {lang_info['code']} -> en: '{translated_text[:120]}'")

    # 1. Model inference on verification text
    ml_result = model_service.analyze_text(verification_text)
    logger.info(f"[ML-EVAL] Raw: {ml_result['raw_label']} ({ml_result['prediction_label']}) | Confidence: {ml_result['confidence']:.2f}% | Probabilities: {ml_result['probabilities']}")

    # 2. Extract claims and run verification and source comparison concurrently for high efficiency
    claims = claim_service.extract_claims(verification_text, max_claims=3)
    logger.info(f"[CLAIMS-EXTRACTED] Count: {len(claims)} | Claims: {claims}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_verify = executor.submit(claim_service.verify_claims, claims)
        future_compare = executor.submit(comparison_service.compare_sources, search_title, 4)
        verification_res = future_verify.result()
        comparison_res = future_compare.result()

    # Reconcile ML stylistic model with factual evidence verification
    overall_verdict = verification_res.get("overall_verdict", "UNAVAILABLE")
    contra_reasons = [c.get("summary") for c in verification_res.get("claims", []) if c.get("evidence_status") == "CONTRADICTED"]
    supp_reasons = [c.get("summary") for c in verification_res.get("claims", []) if c.get("evidence_status") == "SUPPORTED"]

    # Gather 2-3 relevant real sources
    top_sources = []
    for c in verification_res.get("claims", []):
        for ev in c.get("evidence", []):
            if ev.get("url") and ev.get("title") and ev not in top_sources:
                top_sources.append(ev)
                if len(top_sources) >= 3:
                    break
        if len(top_sources) >= 3:
            break
    # Only supplement with external comparison sources if claim was not disproven and items are semantically relevant
    if len(top_sources) < 3 and comparison_res.get("sources") and overall_verdict != "FALSE_CLAIM":
        claim_tokens = {w.lower() for w in re.findall(r'\b[A-Za-z0-9]{3,}\b', search_title) if w.lower() not in (
            "that", "this", "with", "from", "have", "been", "were", "said", "about", "their", "there", "news", "report"
        )}
        for cs in comparison_res.get("sources", []):
            head = cs.get("headline", "")
            head_tokens = {w.lower() for w in re.findall(r'\b[A-Za-z0-9]{3,}\b', head)}
            # Must share at least 2 key terms with derived title to avoid unrelated keyword drift
            if len(claim_tokens.intersection(head_tokens)) >= 2:
                item = {
                    "title": cs.get("headline"),
                    "publisher": cs.get("publisher"),
                    "url": cs.get("url"),
                    "pub_date": cs.get("pub_date"),
                    "excerpt": cs.get("coverage_note", "")
                }
                if item not in top_sources:
                    top_sources.append(item)
                    if len(top_sources) >= 3:
                        break

    # Determine primary label and badge: LIKELY TRUE, LIKELY FALSE, MISLEADING, NOT YET VERIFIED, CONFLICTING RESULTS
    if overall_verdict == "FALSE_CLAIM":
        prediction_label = "LIKELY FALSE"
        status_badge = "error"
        confidence = 97.5
        verdict_rule = "Factual Contradiction Override (Authoritative public record contradicts claim)"
        reason_text = contra_reasons[0] if contra_reasons else "Contradicted by authoritative records."
        if ml_result["raw_label"] == 1:
            explanation = (
                f"{reason_text} Note: While this statement is phrased in formal reporting language, "
                f"authoritative public records disprove the factual assertion."
            )
        else:
            explanation = f"This claim is contradicted by official records and verified fact-checking sources: {reason_text}"

    elif overall_verdict == "SUPPORTED":
        prediction_label = "LIKELY TRUE"
        status_badge = "success"
        confidence = 96.0
        verdict_rule = "Factual Corroboration (Authoritative record or multi-newsroom reporting verifies event)"
        reason_text = supp_reasons[0] if supp_reasons else "Corroborated by independent reporting and official records."
        if ml_result["raw_label"] == 0:
            explanation = (
                f"{reason_text} Note: The linguistic classifier flagged rhetorical or sensational phrasing, "
                f"but independent records verify the underlying event."
            )
        else:
            explanation = f"This report is corroborated by independent news coverage and verified public records: {reason_text}"

    elif overall_verdict == "CONFLICTING_EVIDENCE":
        # Only report genuinely conflicting evidence when the retrieved evidence itself contains a material disagreement that cannot be resolved
        prediction_label = "CONFLICTING RESULTS"
        status_badge = "warning"
        confidence = 65.0
        verdict_rule = "Conflicting Evidence (Material disagreement between monitored reports)"
        reason_text = contra_reasons[0] if contra_reasons else (supp_reasons[0] if supp_reasons else "Differing accounts from monitored publishers.")
        explanation = (
            f"Conflicting evidence: Credible reporting and official sources present conflicting assertions on this subject ({reason_text}). "
            f"A definitive factual conclusion cannot be confirmed until reports are reconciled."
        )

    elif overall_verdict == "MIXED":
        prediction_label = "MISLEADING"
        status_badge = "error"
        confidence = 88.0
        verdict_rule = "Mixed Evidence (Partially misleading assertions)"
        reason_text = contra_reasons[0] if contra_reasons else "Discrepancy between supported and unsupported elements."
        explanation = (
            f"Partially misleading: While certain background details appear in public records, "
            f"key assertions are contradicted or unsupported ({reason_text})."
        )

    else:
        # INSUFFICIENT_EVIDENCE, UNAVAILABLE, or UNVERIFIED
        if ml_result["raw_label"] == 0 and ml_result["confidence"] >= 55.0:
            prediction_label = "MISLEADING"
            status_badge = "error"
            confidence = ml_result["confidence"]
            verdict_rule = "ML Deceptive Pattern Flag + Unverified (Statistical linguistic model detected deceptive pattern, unsupported by evidence)"
            explanation = (
                f"{ml_result['explanation']} Furthermore, no authoritative reports confirming this assertion "
                f"were found in monitored news databases."
            )
        elif ml_result["raw_label"] == 1 and ml_result["confidence"] >= 75.0 and len(text_normalized.split()) >= 10:
            prediction_label = "LIKELY TRUE"
            status_badge = "success"
            confidence = ml_result["confidence"]
            verdict_rule = "ML Credible Pattern (Statistical linguistic model identified authentic journalistic report; uncorroborated by live breaking feeds)"
            explanation = (
                f"{ml_result['explanation']} While this specific event was not retrieved in current live breaking news feeds, "
                f"the text exhibits high linguistic markers of authentic journalism."
            )
        else:
            prediction_label = "NOT YET VERIFIED"
            status_badge = "warning"
            verdict_rule = "Insufficient Evidence Fallback (No authoritative evidence confirmed or refuted claim)"
            # Calibrated confidence - not fabricated high confidence
            confidence = min(max(ml_result["confidence"], 50.0), 65.0)
            if not verification_res.get("available"):
                explanation = (
                    "This news could not be independently cross-referenced because external verification services are currently unreachable. "
                    "The statistical language model provided an initial stylistic pattern assessment only."
                )
            else:
                explanation = (
                    "No authoritative external evidence was found to confirm or refute this assertion in monitored public news records. "
                    "Independent confirmation from primary sources is recommended before trusting or sharing."
                )

    # For multilingual submissions, contextualize the assessment explanation
    if is_multilingual:
        if overall_verdict in ("INSUFFICIENT_EVIDENCE", "UNAVAILABLE", "UNVERIFIED"):
            prediction_label = "NOT YET VERIFIED"
            status_badge = "warning"
            confidence = 52.0
            explanation = (
                f"[Submission Language: {lang_info['name']}] No authoritative public records were found to "
                f"independently corroborate or refute this assertion. Because the machine-learning classifier is trained "
                f"on English journalistic prose, independent confirmation from primary {lang_info['name']} news sources "
                f"is recommended before drawing conclusions."
            )
        else:
            explanation = f"[Submission Language: {lang_info['name']}] " + explanation

    logger.info(f"[FINAL-VERDICT] Verdict: {prediction_label} | Rule: '{verdict_rule}' | Confidence: {confidence:.2f}% | Top Sources: {len(top_sources)}")

    # Assemble structured payload
    full_dossier = {
        "id": str(uuid.uuid4()),
        "created_at": history_service._get_connection().execute("SELECT datetime('now')").fetchone()[0] + " UTC",
        "article_title": derived_title,
        "input_type": input_type,
        "source_info": source_info,
        "prediction_label": prediction_label,
        "confidence": confidence,
        "probabilities": ml_result["probabilities"],
        "word_count": len(text_normalized.split()),
        "explanation": explanation,
        "feature_contributions": ml_result["feature_contributions"],
        "status_badge": status_badge,
        "model_type": ml_result["model_type"],
        "test_accuracy": ml_result["test_accuracy"],
        "verification": verification_res,
        "comparison": comparison_res,
        "top_sources": top_sources[:3],
        "language": lang_info["code"],
        "language_name": lang_info["name"],
        "original_text": text_normalized,
        "translated_text": translated_text
    }

    # Save to history
    history_service.save_analysis(
        title=derived_title,
        input_type=input_type,
        prediction=prediction_label,
        confidence=confidence,
        verification_status="Evidence Checked" if verification_res.get("available") else "ML Only",
        result_data=full_dossier
    )

    return full_dossier

@app.route('/check', methods=['POST'])
def check_news_route():
    query = request.form.get('news_input', '').strip()
    input_type = request.form.get('input_type', '').strip().lower() or 'text'
    article_title = request.form.get('article_title', '').strip()
    
    if not query:
        flash("Please paste news text or enter a news URL to check.", "error")
        return redirect(url_for('index'))
    
    # Check if URL
    if query.startswith(('http://', 'https://', 'www.')) or ('.' in query and ' ' not in query and len(query.split('\n')[0]) < 250):
        url_to_fetch = query if query.startswith(('http://', 'https://')) else f"https://{query}"
        try:
            extracted = extract_article_from_url(url_to_fetch)
            source_info = {
                "domain": extracted["domain"],
                "author": extracted["author"],
                "publication_date": extracted["publication_date"],
                "original_url": extracted["original_url"]
            }
            dossier = _run_full_credibility_pipeline(
                text=extracted["body_text"],
                input_type="URL",
                article_title=extracted["title"],
                source_info=source_info
            )
            return redirect(url_for('view_result_record', record_id=dossier['id']))
        except (SSRFException, ArticleExtractionException) as e:
            flash(f"Could not retrieve news URL: {str(e)}", "error")
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"URL fetch failure: {e}", exc_info=True)
            flash("An unexpected error occurred while fetching the URL.", "error")
            return redirect(url_for('index'))
    else:
        # Regular text or reviewed media text
        if len(query) < 15:
            flash("Please enter at least 15 characters to analyze news.", "error")
            return redirect(url_for('index'))
        if len(query) > Config.MAX_TEXT_LENGTH:
            flash(f"Submitted text exceeds maximum allowed length of {Config.MAX_TEXT_LENGTH:,} characters.", "error")
            return redirect(url_for('index'))
        try:
            safe_input_type = input_type if input_type in ('text', 'pdf', 'image') else 'text'
            source_info = None
            if safe_input_type in ('pdf', 'image'):
                source_info = {
                    "domain": f"Uploaded {safe_input_type.upper()}",
                    "author": "Reviewed Media Submission",
                    "publication_date": "Present",
                    "original_url": ""
                }
            dossier = _run_full_credibility_pipeline(
                text=query, 
                input_type=safe_input_type,
                article_title=article_title,
                source_info=source_info
            )
            return redirect(url_for('view_result_record', record_id=dossier['id']))
        except Exception as e:
            logger.error(f"Text analysis failure: {e}", exc_info=True)
            flash(f"An unexpected error occurred: {str(e)}", "error")
            return redirect(url_for('index'))

@app.route('/extract', methods=['POST'])
def extract_media_route():
    """
    AJAX extraction endpoint for PDF and Image uploads.
    Extracts text to enable client-side review and editing before verification.
    """
    file_type = request.form.get('file_type', '').lower().strip()
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file was uploaded."}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"success": False, "error": "Please select a file to extract."}), 400

    filename = secure_filename(file.filename)
    if not filename:
        filename = f"upload_{file_type}"
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # Check if video was attempted
    video_exts = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv'}
    if file_type == 'video' or ext in video_exts:
        return jsonify({
            "success": False,
            "error": "Video verification is not supported. Please submit claims via text, PDF document, or image screenshot."
        }), 400

    # Validate extensions
    if file_type == 'pdf' and ext not in app.config['ALLOWED_EXTENSIONS_DOC']:
        return jsonify({"success": False, "error": "Invalid file format. Please upload a PDF document (.pdf)."}), 400
    elif file_type == 'image' and ext not in app.config['ALLOWED_EXTENSIONS_IMAGE']:
        return jsonify({"success": False, "error": "Invalid image format. Supported formats: PNG, JPG, JPEG, WebP."}), 400
    elif file_type not in ('pdf', 'image'):
        return jsonify({"success": False, "error": "Unsupported media type. Supported formats: PDF, Image."}), 400

    # Ephemeral storage
    temp_name = f"{uuid.uuid4().hex}_{filename}"
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_name)
    file.save(temp_path)

    try:
        if file_type == 'pdf':
            extracted_text = extract_text_from_pdf(temp_path, max_pages=app.config['MAX_PDF_PAGES'])
        elif file_type == 'image':
            extracted_text = extract_text_from_image(temp_path)

        return jsonify({
            "success": True,
            "file_type": file_type,
            "filename": filename,
            "extracted_text": extracted_text,
            "char_count": len(extracted_text),
            "word_count": len(extracted_text.split())
        }), 200

    except TextExtractionException as e:
        logger.warning(f"AJAX extraction failed on {filename}: {e}")
        return jsonify({"success": False, "error": str(e)}), 422
    except Exception as e:
        logger.error(f"AJAX extraction failure: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to process the uploaded file due to a server error."}), 500
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@app.route('/analyze/text', methods=['POST'])
def analyze_text_route():
    news_text = request.form.get('news_text', '').strip()
    if not news_text:
        flash("Please paste or type news text to begin credibility analysis.", "error")
        return redirect(url_for('index'))
    if len(news_text) < 15:
        flash("The submitted text is too short for linguistic credibility analysis (minimum 15 characters).", "error")
        return redirect(url_for('index'))
    if len(news_text) > Config.MAX_TEXT_LENGTH:
        flash(f"Submitted text exceeds maximum allowed length of {Config.MAX_TEXT_LENGTH:,} characters.", "error")
        return redirect(url_for('index'))

    try:
        dossier = _run_full_credibility_pipeline(news_text, input_type="text")
        return redirect(url_for('view_result_record', record_id=dossier['id']))
    except Exception as e:
        logger.error(f"Text analysis failure: {e}", exc_info=True)
        flash(f"An unexpected error occurred during analysis: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/analyze/url', methods=['POST'])
def analyze_url_route():
    news_url = request.form.get('news_url', '').strip()
    if not news_url:
        flash("Please enter a valid news article URL.", "error")
        return redirect(url_for('index'))

    try:
        extracted = extract_article_from_url(news_url)
        source_info = {
            "domain": extracted["domain"],
            "author": extracted["author"],
            "publication_date": extracted["publication_date"],
            "original_url": extracted["original_url"]
        }
        dossier = _run_full_credibility_pipeline(
            text=extracted["body_text"],
            input_type="URL",
            article_title=extracted["title"],
            source_info=source_info
        )
        return redirect(url_for('view_result_record', record_id=dossier['id']))
    except (SSRFException, ArticleExtractionException) as e:
        logger.warning(f"URL extraction refused or failed: {e}")
        flash(f"Could not retrieve news URL: {str(e)}", "error")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"URL processing failure: {e}", exc_info=True)
        flash("An unexpected error occurred while fetching the URL.", "error")
        return redirect(url_for('index'))

@app.route('/analyze/file', methods=['POST'])
def analyze_file_route():
    file_type = request.form.get('file_type', '').lower()
    if 'file' not in request.files:
        flash("No file was uploaded.", "error")
        return redirect(url_for('index'))

    file = request.files['file']
    if not file or file.filename == '':
        flash("Please select a file to upload.", "error")
        return redirect(url_for('index'))

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # Check if video was attempted
    video_exts = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv'}
    if file_type == 'video' or ext in video_exts:
        flash("Video verification is not supported. Please submit claims via text, PDF document, or image screenshot.", "error")
        return redirect(url_for('index'))

    # Validate extensions
    if file_type == 'pdf' and ext not in app.config['ALLOWED_EXTENSIONS_DOC']:
        flash("Invalid file format. Please upload a PDF document (.pdf).", "error")
        return redirect(url_for('index'))
    elif file_type == 'image' and ext not in app.config['ALLOWED_EXTENSIONS_IMAGE']:
        flash("Invalid image format. Supported formats: PNG, JPG, JPEG, WebP.", "error")
        return redirect(url_for('index'))

    # Save to ephemeral location
    temp_name = f"{uuid.uuid4().hex}_{filename}"
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_name)
    file.save(temp_path)

    try:
        if file_type == 'pdf':
            extracted_text = extract_text_from_pdf(temp_path, max_pages=app.config['MAX_PDF_PAGES'])
            display_title = f"Document: {filename}"
        elif file_type == 'image':
            extracted_text = extract_text_from_image(temp_path)
            display_title = f"Image OCR: {filename}"
        else:
            flash("Unsupported file upload mode.", "error")
            return redirect(url_for('index'))

        source_info = {
            "domain": f"Uploaded {file_type.upper()}",
            "author": "Local Upload",
            "publication_date": "Present",
            "original_url": ""
        }
        dossier = _run_full_credibility_pipeline(
            text=extracted_text,
            input_type=file_type,
            article_title=display_title,
            source_info=source_info
        )
        return redirect(url_for('view_result_record', record_id=dossier['id']))

    except TextExtractionException as e:
        logger.warning(f"Text extraction failed on {filename}: {e}")
        flash(str(e), "error")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"File pipeline failure: {e}", exc_info=True)
        flash(f"Failed to process uploaded file: {str(e)}", "error")
        return redirect(url_for('index'))
    finally:
        # Ephemeral cleanup
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

@app.route('/report/pdf/<record_id>')
def download_pdf_report(record_id):
    rec = history_service.get_by_id(record_id)
    if not rec:
        abort(404)
        
    result_data = rec.get("result", {})
    pdf_buffer = generate_pdf_report(result_data)
    
    clean_id = record_id[:8]
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"TruthLens-Credibility-Report-{clean_id}.pdf"
    )

# --- REST API Endpoints ---

@app.route('/api/analyze/text', methods=['POST'])
def api_analyze_text():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    if not text or len(text) < 15:
        return jsonify({"error": "Text must be at least 15 characters long."}), 400
    if len(text) > Config.MAX_TEXT_LENGTH:
        return jsonify({"error": f"Text exceeds maximum allowed length of {Config.MAX_TEXT_LENGTH} characters."}), 400

    dossier = _run_full_credibility_pipeline(text, input_type="api_text")
    return jsonify(dossier), 200

@app.route('/api/health')
def api_health():
    return jsonify({
        "status": "healthy",
        "model_loaded": model_service.is_loaded,
        "model_type": model_service.get_metadata().get("model_type"),
        "test_accuracy": model_service.get_metadata().get("test_accuracy"),
        "multilingual_enabled": multilingual_service.enabled,
        "supported_languages": list(multilingual_service.SUPPORTED_LANGUAGES.keys())
    }), 200

@app.route('/api/metrics')
def api_metrics():
    return jsonify(model_service.get_metadata()), 200

# --- Error Handlers ---

@app.errorhandler(404)
def not_found_error(error):
    return render_template('base.html'), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    flash("The uploaded file exceeds our maximum size limit (30 MB).", "error")
    return redirect(url_for('index')), 413

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    flash("A temporary server error occurred. Please try again.", "error")
    return redirect(url_for('index')), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=False)
