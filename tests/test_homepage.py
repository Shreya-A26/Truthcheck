import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_editorial_homepage_route(client):
    resp = client.get('/home')
    assert resp.status_code == 200
    content = resp.data.decode('utf-8')

    # Brand & Theme
    assert "TruthLens" in content
    assert "The News Credibility Lab" in content

    # Section 01: Hero
    assert "Every story deserves a" in content
    assert "closer look." in content
    assert "Explore the claims behind the headlines" in content
    assert "Analyze News" in content
    assert "Explore How It Works" in content
    assert "TEXT" in content.upper()
    assert "DOCUMENTS" in content.upper()
    assert "IMAGES" in content.upper()
    assert "MULTILINGUAL ANALYSIS" in content.upper()

    # Confirmed REMOVED Section: The Anatomy of a Claim
    assert "The anatomy of a claim" not in content
    assert "Demonstration Assertion" not in content
    assert "Layer One" not in content

    # Confirmed REMOVED Section: From Headline to Evidence
    assert "From headline to evidence" not in content
    assert "Analytical Progression" not in content

    # Retained Editorial Perspective Section
    assert "A convincing headline is not the same as convincing evidence" in content
    assert "Documentary Audit Ledger" in content

    # Confirmed REMOVED Section: Four ways to examine the record
    assert "Four ways to examine the record" not in content
    assert "Supported Input Formats" not in content
    assert "Format 01" not in content

    # Section: Final Editorial Statement
    assert "Pause at the headline" in content
    assert "Look closer at the evidence" in content
    assert "Start with a claim. Explore the analysis. Make room for context." in content

    # CTAs link to news-analysis workbench
    assert 'href="/"' in content or 'href="/analyze"' in content or 'href="http://localhost:5002/"' in content

def test_editorial_alias_route(client):
    resp = client.get('/editorial')
    assert resp.status_code == 200
    assert b"Every story deserves a" in resp.data

def test_analyze_workspace_alias(client):
    resp = client.get('/analyze')
    assert resp.status_code == 200
    assert b"How would you like to verify the news?" in resp.data

def test_existing_analysis_page_preserved(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b"TruthLens" in resp.data
    assert b"How would you like to verify the news?" in resp.data
    assert b"data-tab=\"pdf\"" in resp.data
    assert b"data-tab=\"image\"" in resp.data
