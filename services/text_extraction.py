import os
import io
import shutil
import logging
import subprocess
import tempfile
import numpy as np
from PIL import Image, ImageOps
from pypdf import PdfReader

logger = logging.getLogger(__name__)

class TextExtractionException(Exception):
    pass

# Initialize OCR engine lazily or globally
_rapid_ocr_engine = None

def get_ocr_engine():
    global _rapid_ocr_engine
    if _rapid_ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr_engine = RapidOCR()
            logger.info("RapidOCR engine initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize RapidOCR: {e}")
            _rapid_ocr_engine = False
    return _rapid_ocr_engine if _rapid_ocr_engine is not False else None

def is_tesseract_available() -> bool:
    """Checks whether the system tesseract binary is available on PATH."""
    return shutil.which("tesseract") is not None

def is_node_ocr_available() -> bool:
    """Checks whether Node.js and the local multilingual OCR runner are available."""
    runner_path = os.path.join(os.path.dirname(__file__), "ocr_runner.js")
    node_bin = shutil.which("node") or "/usr/local/bin/node"
    return bool(node_bin and os.path.exists(node_bin) and os.path.exists(runner_path))

def is_ocr_available() -> bool:
    """Checks if any OCR engine (Node/Tesseract.js, RapidOCR, or system Tesseract) is ready to use."""
    return is_node_ocr_available() or (get_ocr_engine() is not None) or is_tesseract_available()

def _count_script_characters(text: str) -> dict:
    """Counts Unicode characters for each supported script family."""
    ml = sum(1 for c in text if 0x0D00 <= ord(c) <= 0x0D7F)
    hi = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
    ta = sum(1 for c in text if 0x0B80 <= ord(c) <= 0x0BFF)
    en = sum(1 for c in text if ('a' <= c.lower() <= 'z'))
    return {"ml": ml, "hi": hi, "ta": ta, "en": en}

def _clean_ocr_text(text: str) -> str:
    """
    Cleans raw OCR output lines while strictly preserving Malayalam combining marks,
    viramas (chandrakkala), chillu characters, Hindi matras, and Tamil vowel signs.
    """
    if not text:
        return ""
    cleaned_lines = []
    for line in text.splitlines():
        trimmed = line.strip()
        # Discard 1-2 character non-alphanumeric noise fragments
        if len(trimmed) <= 2 and not any(c.isalnum() or (0x0900 <= ord(c) <= 0x0D7F) for c in trimmed):
            continue
        if trimmed:
            cleaned_lines.append(trimmed)
    return "\n".join(cleaned_lines).strip()

def _run_node_ocr(pil_img: Image.Image, lang: str = "mal+eng") -> str:
    """Executes the local Tesseract.js worker with verified language packs."""
    runner_path = os.path.join(os.path.dirname(__file__), "ocr_runner.js")
    node_bin = shutil.which("node") or "/usr/local/bin/node"
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_name = f.name
    try:
        pil_img.save(tmp_name, format="PNG")
        res = subprocess.run(
            [node_bin, runner_path, tmp_name, lang],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=25
        )
        if res.returncode == 0:
            return res.stdout.strip()
        else:
            logger.warning(f"Node OCR runner exited with code {res.returncode}: {res.stderr}")
            return ""
    except Exception as e:
        logger.warning(f"Node OCR invocation error: {e}")
        return ""
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass

def run_ocr_on_pil_image(pil_img: Image.Image) -> str:
    """
    Runs robust multilingual OCR (Malayalam, Hindi, Tamil, English) on a PIL image.
    Applies bounded dimension constraints, text region layout isolation, and clean fallback tiers.
    """
    # 1. Bounded dimensions check to prevent memory exhaustion
    max_dimension = 4096
    if max(pil_img.size) > max_dimension:
        scale = max_dimension / float(max(pil_img.size))
        new_w = max(1, int(pil_img.width * scale))
        new_h = max(1, int(pil_img.height * scale))
        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    if pil_img.mode not in ("L", "RGB"):
        pil_img = pil_img.convert("RGB")

    # 2. Multilingual Node.js Tesseract Runner
    if is_node_ocr_available():
        # Text detection & region isolation via RapidOCR text detector if available
        stacked_canvas = None
        try:
            engine = get_ocr_engine()
            if engine is not None and getattr(engine, 'use_text_det', True):
                img_arr = np.array(pil_img)
                dt_boxes, _ = engine.text_detector(img_arr)
                if dt_boxes is not None and len(dt_boxes) > 0:
                    dt_boxes = engine.sorted_boxes(dt_boxes)
                    raw_crops = engine.get_crop_img_list(img_arr, dt_boxes)
                    crops = []
                    for crop in raw_crops:
                        h, w = crop.shape[:2]
                        if w > 30 and h > 10:
                            pil_c = Image.fromarray(crop)
                            padded = ImageOps.expand(pil_c, border=14, fill="white")
                            crops.append(padded)
                    if crops:
                        max_w = max(c.width for c in crops) + 40
                        total_h = sum(c.height for c in crops) + (len(crops) * 20) + 40
                        stacked = Image.new("RGB", (max_w, total_h), "white")
                        y_off = 20
                        for c in crops:
                            stacked.paste(c, (20, y_off))
                            y_off += c.height + 20
                        stacked_canvas = stacked
        except Exception as e:
            logger.debug(f"Detector region isolation skipped: {e}")
            stacked_canvas = None

        target_img = stacked_canvas if stacked_canvas is not None else pil_img

        # Candidate language passes: evaluate Indic scripts to find the dominant language
        indic_candidates = {}
        for lang_code in ["mal+eng", "tam+eng", "hin+eng"]:
            raw_text = _run_node_ocr(target_img, lang=lang_code)
            cleaned = _clean_ocr_text(raw_text)
            counts = _count_script_characters(cleaned)
            indic_key = "ml" if "mal" in lang_code else ("ta" if "tam" in lang_code else "hi")
            indic_candidates[lang_code] = (cleaned, counts[indic_key])

        best_lang, (best_text, best_count) = max(indic_candidates.items(), key=lambda x: x[1][1])
        if best_count >= 6:
            return best_text

        # If no dominant Indic script, evaluate English pass
        eng_text = _clean_ocr_text(_run_node_ocr(target_img, lang="eng"))
        if eng_text and len(eng_text) >= 10:
            return eng_text

        # Fallback to full image pass if stacked canvas was attempted
        if stacked_canvas is not None:
            full_img_text = _clean_ocr_text(_run_node_ocr(pil_img, lang="mal+eng+hin+tam"))
            if full_img_text and len(full_img_text) >= 10:
                return full_img_text

    # 3. Fallback to RapidOCR if Node is unavailable
    engine = get_ocr_engine()
    if engine is not None:
        try:
            img_arr = np.array(pil_img)
            result, _ = engine(img_arr)
            if result:
                lines = [item[1].strip() for item in result if item and len(item) > 1 and item[1].strip()]
                extracted = "\n".join(lines).strip()
                if extracted:
                    return _clean_ocr_text(extracted)
        except Exception as e:
            logger.warning(f"RapidOCR inference error: {e}")

    # 4. Fallback to pytesseract if system binary is present
    if is_tesseract_available():
        try:
            import pytesseract
            text = pytesseract.image_to_string(pil_img).strip()
            if text:
                return _clean_ocr_text(text)
        except Exception as e:
            logger.warning(f"pytesseract error: {e}")

    return ""

def extract_text_from_pdf(file_path: str, max_pages: int = 15) -> str:
    """
    Extracts readable text from selectable PDF document up to max_pages.
    If the PDF contains scanned pages without selectable text, attempts OCR on embedded page images.
    """
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        logger.error(f"Error opening PDF: {e}")
        raise TextExtractionException("Uploaded PDF file is corrupted or unreadable.")

    try:
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise TextExtractionException("PDF is password protected or encrypted. Please upload an unencrypted document.")

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise TextExtractionException("PDF file contains no pages.")
            
        pages_to_read = min(total_pages, max_pages)
        extracted_chunks = []
        
        # Phase 1: Try native selectable text extraction
        for idx in range(pages_to_read):
            page = reader.pages[idx]
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_chunks.append(page_text.strip())
                
        full_text = "\n\n".join(extracted_chunks).strip()
        if full_text:
            return full_text

        # Phase 2: If no selectable text, check for scanned pages / embedded images
        ocr_chunks = []
        if is_ocr_available():
            for idx in range(min(pages_to_read, 5)):  # Cap scanned pages for responsiveness
                page = reader.pages[idx]
                try:
                    for img_obj in page.images:
                        try:
                            pil_img = Image.open(io.BytesIO(img_obj.data))
                            page_ocr = run_ocr_on_pil_image(pil_img)
                            if page_ocr:
                                ocr_chunks.append(page_ocr)
                        except Exception:
                            continue
                except Exception:
                    continue

        if ocr_chunks:
            full_ocr_text = "\n\n".join(ocr_chunks).strip()
            if full_ocr_text:
                return full_ocr_text

        raise TextExtractionException(
            "No selectable text found in PDF. This appears to be a scanned document or image-only PDF. "
            "Please ensure the document contains clear text, or upload an image screenshot of the news article."
        )

    except TextExtractionException:
        raise
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        raise TextExtractionException(f"Failed to read PDF document: {str(e)}")

def extract_text_from_image(file_path: str) -> str:
    """
    Extracts visible text from an image using OCR.
    Handles missing OCR binaries gracefully.
    """
    try:
        with Image.open(file_path) as img:
            img.verify()
    except Exception:
        raise TextExtractionException("Uploaded file is not a valid or readable image. Supported formats: JPG, JPEG, PNG, WEBP.")

    if not is_ocr_available():
        raise TextExtractionException(
            "OCR text recognition engine is currently unavailable on the server. "
            "Please paste the news article text directly into the Text input workspace."
        )

    try:
        with Image.open(file_path) as img:
            extracted_text = run_ocr_on_pil_image(img)
            clean_text = extracted_text.strip()
            if not clean_text:
                raise TextExtractionException(
                    "No readable text could be recognized in the uploaded image. "
                    "Ensure the image is clear, high-contrast, and contains visible headlines or paragraphs."
                )
            return clean_text
    except TextExtractionException:
        raise
    except Exception as e:
        logger.error(f"OCR processing failure: {e}")
        raise TextExtractionException(f"Image text recognition failed: {str(e)}")

def extract_audio_and_transcribe(video_path: str, max_duration_sec: int = 60) -> str:
    """
    Extracts audio track from video and transcribes speech using SpeechRecognition.
    Returns transcript string or empty string if no speech detected / audio unsupported.
    """
    import speech_recognition as sr

    temp_wav = None
    try:
        # Create temp file for 16-bit linear PCM WAV
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_wav = f.name

        conversion_success = False

        # Method 1: Check ffmpeg
        if shutil.which("ffmpeg"):
            cmd = [
                "ffmpeg", "-y", "-i", video_path, 
                "-t", str(max_duration_sec),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                temp_wav
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
            if res.returncode == 0 and os.path.getsize(temp_wav) > 1000:
                conversion_success = True

        # Method 2: Check macOS afconvert
        if not conversion_success and os.path.exists("/usr/bin/afconvert"):
            cmd = ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@16000", video_path, temp_wav]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
            if res.returncode == 0 and os.path.getsize(temp_wav) > 1000:
                conversion_success = True

        if not conversion_success or not os.path.exists(temp_wav) or os.path.getsize(temp_wav) < 1000:
            logger.info("Audio track extraction not supported or no audio stream found in video.")
            return ""

        # Run speech recognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_wav) as source:
            # Record up to max_duration_sec
            audio_data = recognizer.record(source, duration=max_duration_sec)
            try:
                transcript = recognizer.recognize_google(audio_data)
                return transcript.strip()
            except sr.UnknownValueError:
                logger.info("No recognizable speech detected in video audio stream.")
                return ""
            except sr.RequestError as e:
                logger.warning(f"Speech recognition service unreachable: {e}")
                return ""
            except Exception as e:
                logger.warning(f"Speech recognition error: {e}")
                return ""

    except Exception as e:
        logger.warning(f"Audio transcription pipeline warning: {e}")
        return ""
    finally:
        if temp_wav and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except OSError:
                pass

def extract_text_from_video(file_path: str, max_frames: int = 10, max_duration_sec: int = 60) -> str:
    """
    Extracts text from a supported video file by:
    1. Transcribing speech from the audio stream (via speech recognition).
    2. Sampling key frames and performing OCR on visible news graphics, chyrons, and headlines.
    3. Combining both sources for verification.
    """
    try:
        import cv2
    except ImportError:
        raise TextExtractionException("Video processing module is not installed on this server.")

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise TextExtractionException("Unable to open or decode the video file. Supported formats: MP4, MOV, AVI, MKV.")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = frame_count / fps if fps > 0 else 0

        if duration > max_duration_sec:
            raise TextExtractionException(
                f"Video exceeds the {max_duration_sec}-second processing limit (detected duration: {int(duration)}s)."
            )

        # 1. Extract audio speech transcript
        spoken_transcript = extract_audio_and_transcribe(file_path, max_duration_sec=max_duration_sec)

        # 2. Extract onscreen text via Keyframe OCR
        onscreen_texts = []
        if is_ocr_available() and frame_count > 0:
            step = max(1, int(frame_count / (max_frames + 1)))
            sample_indices = [i * step for i in range(1, max_frames + 1) if (i * step) < frame_count]

            for frame_idx in sample_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb_frame)
                frame_text = run_ocr_on_pil_image(pil_img)
                if frame_text and len(frame_text) > 8:
                    # Deduplicate similar lines
                    if not any(frame_text in existing or existing in frame_text for existing in onscreen_texts):
                        onscreen_texts.append(frame_text)

        combined_sections = []
        if spoken_transcript:
            combined_sections.append(f"Spoken News Transcript:\n{spoken_transcript}")

        if onscreen_texts:
            onscreen_joined = "\n".join(onscreen_texts)
            combined_sections.append(f"On-Screen Headlines & Captions:\n{onscreen_joined}")

        full_extracted = "\n\n".join(combined_sections).strip()
        if not full_extracted:
            raise TextExtractionException(
                "No readable speech or visible news text could be detected in this video. "
                "Please upload a clearer video clip with clear audio or visible headlines, "
                "or upload an article screenshot or text transcript instead."
            )

        return full_extracted
    finally:
        cap.release()
