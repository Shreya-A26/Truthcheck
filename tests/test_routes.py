import io
import pytest
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from app import app, history_service

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_homepage_route(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b"TruthLens" in resp.data
    assert b"Know the Facts. Trust the News." in resp.data
    assert b"Check News" in resp.data
    assert b"Verify before you believe." in resp.data
    assert b"How would you like to verify the news?" in resp.data
    assert b"data-tab=\"pdf\"" in resp.data
    assert b"data-tab=\"image\"" in resp.data
    assert b"data-tab=\"video\"" not in resp.data
    assert b"Extract News from Video" not in resp.data

def test_about_route(client):
    resp = client.get('/about')
    assert resp.status_code == 200
    assert b"Look Beyond the Headline." in resp.data

def test_performance_route(client):
    resp = client.get('/performance')
    assert resp.status_code == 200
    assert b"99.08%" in resp.data

def test_history_route(client):
    resp = client.get('/history')
    assert resp.status_code == 200
    assert b"Analysis History" in resp.data

def test_empty_check_submission(client):
    resp = client.post('/check', data={'news_input': '   '}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Please paste news text or enter a news URL to check" in resp.data

def test_short_check_submission(client):
    resp = client.post('/check', data={'news_input': 'Too short'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"at least 15 characters" in resp.data

def test_valid_check_flow(client):
    sample_text = (
        "WASHINGTON (Reuters) - The U.S. Senate passed bipartisan legislation on clean energy infrastructure "
        "following intensive floor negotiations on Thursday morning."
    )
    resp = client.post('/check', data={'news_input': sample_text}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"LIKELY TRUE" in resp.data
    assert b"Check Another News" in resp.data
    assert b"Read More" in resp.data

def test_check_with_reviewed_image_input(client):
    reviewed_ocr_text = (
        "WASHINGTON (Reuters) - The U.S. Senate passed bipartisan legislation on clean energy infrastructure "
        "following intensive floor negotiations on Thursday morning."
    )
    resp = client.post('/check', data={
        'news_input': reviewed_ocr_text,
        'input_type': 'image',
        'article_title': 'Image OCR: senate_clean_energy.png'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"LIKELY TRUE" in resp.data
    assert b"Image OCR: senate_clean_energy.png" in resp.data
    assert b"Check Another News" in resp.data

def test_extract_ajax_video_rejection(client):
    dummy_video = io.BytesIO(b"dummy mp4 video bytes")
    data = {
        'file_type': 'video',
        'file': (dummy_video, 'broadcast.mp4')
    }
    resp = client.post('/extract', data=data, content_type='multipart/form-data')
    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload['success'] is False
    assert "Video verification is not supported" in payload['error']

def test_analyze_file_video_rejection(client):
    dummy_video = io.BytesIO(b"dummy mp4 video bytes")
    data = {
        'file_type': 'video',
        'file': (dummy_video, 'broadcast.mp4')
    }
    resp = client.post('/analyze/file', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    assert b"Video verification is not supported" in resp.data



def test_extract_ajax_pdf(client):
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer)
    c.drawString(100, 750, "Headline: Central Bank Holds Policy Interest Rates")
    c.drawString(100, 730, "Monetary policymakers voted to maintain rates as core inflation eased.")
    c.save()
    pdf_buffer.seek(0)

    data = {
        'file_type': 'pdf',
        'file': (pdf_buffer, 'monetary_statement.pdf')
    }
    resp = client.post('/extract', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['success'] is True
    assert 'Central Bank Holds' in payload['extracted_text']

def test_extract_ajax_image(client):
    img = Image.new('RGB', (600, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 35), "Breaking: Peace Talks Conclude in Cairo With Ceasefire Accord", fill=(0, 0, 0))
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    data = {
        'file_type': 'image',
        'file': (img_buffer, 'news_scan.png')
    }
    resp = client.post('/extract', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['success'] is True
    assert len(payload['extracted_text']) > 10

def test_extract_ajax_unsupported_file_extension(client):
    dummy = io.BytesIO(b"executable code or bad format")
    data = {
        'file_type': 'image',
        'file': (dummy, 'malicious.exe')
    }
    resp = client.post('/extract', data=data, content_type='multipart/form-data')
    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload['success'] is False
    assert "Invalid image format" in payload['error']

def test_extract_ajax_no_file(client):
    resp = client.post('/extract', data={'file_type': 'pdf'})
    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload['success'] is False

def test_api_health_endpoint(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True
    assert data["test_accuracy"] == 0.9908

def test_pdf_report_download(client):
    records = history_service.get_all(limit=1)
    if records:
        rec_id = records[0]["id"]
        resp = client.get(f'/report/pdf/{rec_id}')
        assert resp.status_code == 200
        assert resp.content_type == 'application/pdf'
        assert len(resp.data) > 1000
