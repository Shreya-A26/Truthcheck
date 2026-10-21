import io
import pytest
import numpy as np
import cv2
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from pypdf import PdfWriter
from services.text_extraction import (
    extract_text_from_pdf, extract_text_from_image, extract_text_from_video,
    TextExtractionException
)

def test_extract_text_from_pdf(tmp_path):
    pdf_path = tmp_path / "sample_news.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Headline: Climate Summit Concludes With Renewable Accord")
    c.drawString(100, 730, "Delegates from 190 nations approved a comprehensive clean energy timetable.")
    c.save()

    extracted = extract_text_from_pdf(str(pdf_path))
    assert "Climate Summit Concludes" in extracted
    assert "clean energy timetable" in extracted

def test_extract_text_from_corrupt_file(tmp_path):
    corrupt_path = tmp_path / "corrupt.pdf"
    corrupt_path.write_bytes(b"Not a real PDF stream")

    with pytest.raises(TextExtractionException):
        extract_text_from_pdf(str(corrupt_path))

def test_extract_text_from_image_ocr(tmp_path):
    img_path = tmp_path / "news_headline.png"
    img = Image.new('RGB', (600, 120), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 30), "Breaking: World Health Assembly Approves Pandemic Treaty", fill=(0, 0, 0))
    d.text((20, 65), "Member states voted overwhelmingly to adopt the historic accord.", fill=(20, 20, 20))
    img.save(str(img_path))

    extracted = extract_text_from_image(str(img_path))
    assert len(extracted) > 15
    assert "Health Assembly" in extracted or "Pandemic" in extracted

def test_extract_text_from_blank_image(tmp_path):
    img_path = tmp_path / "blank.png"
    img = Image.new('RGB', (300, 100), color=(255, 255, 255))
    img.save(str(img_path))

    with pytest.raises(TextExtractionException) as exc_info:
        extract_text_from_image(str(img_path))
    assert "No readable text" in str(exc_info.value)

def test_extract_text_from_corrupt_image(tmp_path):
    corrupt_img = tmp_path / "fake.png"
    corrupt_img.write_bytes(b"Invalid image binary data")

    with pytest.raises(TextExtractionException):
        extract_text_from_image(str(corrupt_img))

def test_extract_text_from_video_keyframes(tmp_path):
    video_path = tmp_path / "news_broadcast.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (480, 120))
    
    for _ in range(20):
        frame = np.ones((120, 480, 3), dtype=np.uint8) * 255
        cv2.putText(
            frame, 
            "SPECIAL REPORT: Treaty Signed in Geneva", 
            (15, 60), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.6, 
            (0, 0, 0), 
            2
        )
        out.write(frame)
    out.release()

    extracted = extract_text_from_video(str(video_path), max_frames=5)
    assert len(extracted) > 10
    assert "Treaty Signed" in extracted or "Geneva" in extracted

def test_extract_text_from_video_exceeding_duration(tmp_path):
    video_path = tmp_path / "long_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    # 10 fps, 100 frames = 10s duration. Set max_duration_sec=3 to trigger duration limit
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (200, 100))
    for _ in range(60):
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    with pytest.raises(TextExtractionException) as exc_info:
        extract_text_from_video(str(video_path), max_duration_sec=2)
    assert "exceeds" in str(exc_info.value).lower()

def test_extract_text_from_malayalam_news_poster():
    import os
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "malayalam_news_poster.png")
    assert os.path.exists(fixture_path), "Malayalam news poster fixture must exist"

    extracted = extract_text_from_image(fixture_path)
    assert len(extracted) > 20
    # Must preserve Malayalam Unicode codepoints (U+0D00 - U+0D7F)
    ml_chars = sum(1 for c in extracted if 0x0D00 <= ord(c) <= 0x0D7F)
    assert ml_chars >= 10, f"Expected Malayalam characters, got: {extracted}"
    # Verify key tokens extracted from poster headline
    assert any(term in extracted for term in ["കിട്ടിയതിന്റെ", "ക്രെഡിറ്റിൽ", "തർക്കം", "കൊടിക്കുന്നിലും", "വിസ്ഡം", "പ്രേമചന്ദ്രനും"])

def test_extract_text_from_hindi_image(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    import os
    font_path = "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc"
    if not os.path.exists(font_path):
        pytest.skip("Devanagari system font not present on macOS host")

    img_path = tmp_path / "hindi_headline.png"
    font = ImageFont.truetype(font_path, 28)
    img = Image.new("RGB", (650, 100), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 30), "ताज़ा समाचार: संसद का विशेष सत्र संपन्न हुआ", fill="black", font=font)
    img.save(str(img_path))

    extracted = extract_text_from_image(str(img_path))
    assert len(extracted) > 10
    hi_chars = sum(1 for c in extracted if 0x0900 <= ord(c) <= 0x097F)
    assert hi_chars >= 8, f"Expected Devanagari characters, got: {extracted}"

def test_extract_text_from_tamil_image(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    import os
    font_path = "/System/Library/Fonts/Supplemental/Tamil Sangam MN.ttc"
    if not os.path.exists(font_path):
        pytest.skip("Tamil system font not present on macOS host")

    img_path = tmp_path / "tamil_headline.png"
    font = ImageFont.truetype(font_path, 28)
    img = Image.new("RGB", (650, 100), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 30), "முக்கிய செய்தி: புதிய திட்டம் தொடங்கப்பட்டது", fill="black", font=font)
    img.save(str(img_path))

    extracted = extract_text_from_image(str(img_path))
    assert len(extracted) > 5
    ta_chars = sum(1 for c in extracted if 0x0B80 <= ord(c) <= 0x0BFF)
    assert ta_chars >= 5, f"Expected Tamil characters, got: {extracted}"

def test_extract_text_from_oversized_image(tmp_path):
    """Verifies that oversized dimensions (> 4096px) are scaled down safely without crashing."""
    img_path = tmp_path / "large_news.png"
    img = Image.new("RGB", (4800, 400), "white")
    d = ImageDraw.Draw(img)
    d.text((50, 150), "GLOBAL SUMMIT: Leaders Reach Comprehensive Carbon Reduction Pact in Berlin", fill=(0, 0, 0))
    img.save(str(img_path))

    extracted = extract_text_from_image(str(img_path))
    assert len(extracted) > 10
    assert "SUMMIT" in extracted or "Leaders" in extracted or "Berlin" in extracted

