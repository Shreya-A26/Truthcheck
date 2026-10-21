import hashlib
import pytest
from app import app, _run_full_credibility_pipeline, model_service, multilingual_service
from services.multilingual_service import MultilingualService

EXPECTED_MODEL_SHA256 = "2ebbdef8ebd1ff3a8660dcd4ccd3fa6cc633aedd80f16901444edda7377ce3ed"
EXPECTED_METADATA_SHA256 = "9424b5839848e6966b3281a5a69c944033af0aff70fa1a40ecd016d8b356a461"

def hash_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def test_model_artifacts_integrity():
    """Verify that existing ML model artifacts remain 100% unaltered."""
    actual_model_hash = hash_file('models/fake_news_model.pkl')
    actual_meta_hash = hash_file('models/metadata.json')
    assert actual_model_hash == EXPECTED_MODEL_SHA256, "CRITICAL: fake_news_model.pkl was modified!"
    assert actual_meta_hash == EXPECTED_METADATA_SHA256, "CRITICAL: metadata.json was modified!"

def test_language_detection():
    """Verify deterministic language detection for English, Malayalam, Hindi, and Tamil."""
    ms = MultilingualService()
    
    # English
    en_res = ms.detect_language("WASHINGTON (Reuters) - The U.S. Federal Reserve announced interest rates would remain steady.")
    assert en_res["code"] == "en"
    assert en_res["name"] == "English"
    assert en_res["is_english"] is True

    # Malayalam
    ml_res = ms.detect_language("നരേന്ദ്ര മോദി ഇന്ത്യയുടെ പ്രധാനമന്ത്രിയാണ്.")
    assert ml_res["code"] == "ml"
    assert ml_res["name"] == "Malayalam"
    assert ml_res["is_english"] is False

    # Hindi
    hi_res = ms.detect_language("नरेंद्र मोदी भारत के प्रधानमंत्री हैं।")
    assert hi_res["code"] == "hi"
    assert hi_res["name"] == "Hindi"
    assert hi_res["is_english"] is False

    # Tamil
    ta_res = ms.detect_language("நரேந்திர மோடி இந்தியாவின் பிரதமர் ஆவார்.")
    assert ta_res["code"] == "ta"
    assert ta_res["name"] == "Tamil"
    assert ta_res["is_english"] is False

def test_malayalam_credibility_flow():
    """Verify Malayalam claim processing, translation, and verification."""
    # True claim in Malayalam
    res_true = _run_full_credibility_pipeline("നരേന്ദ്ര മോദി ഇന്ത്യയുടെ പ്രധാനമന്ത്രിയാണ്.", input_type="text")
    assert res_true["language"] == "ml"
    assert res_true["language_name"] == "Malayalam"
    assert res_true["prediction_label"] == "LIKELY TRUE"
    assert "Modi" in res_true["translated_text"]
    assert res_true["confidence"] >= 90.0

    # False hoax in Malayalam
    res_false = _run_full_credibility_pipeline("തിളപ്പിച്ച വെളുത്തുള്ളി വെള്ളം കുടിച്ചാൽ 24 മണിക്കൂറിനുള്ളിൽ കൊറോണ മാറും.", input_type="text")
    assert res_false["language"] == "ml"
    assert res_false["prediction_label"] == "LIKELY FALSE"
    assert res_false["confidence"] >= 90.0

def test_hindi_credibility_flow():
    """Verify Hindi claim processing, translation, and verification."""
    # True claim in Hindi
    res_true = _run_full_credibility_pipeline("नरेंद्र मोदी भारत के प्रधानमंत्री हैं।", input_type="text")
    assert res_true["language"] == "hi"
    assert res_true["language_name"] == "Hindi"
    assert res_true["prediction_label"] == "LIKELY TRUE"
    assert res_true["confidence"] >= 90.0

    # False hoax in Hindi
    res_false = _run_full_credibility_pipeline("सरकार बैंक खातों को ट्रैक करने के लिए करेंसी नोटों के अंदर 5जी माइक्रोचिप लगा रही है।", input_type="text")
    assert res_false["language"] == "hi"
    assert res_false["prediction_label"] == "LIKELY FALSE"
    assert res_false["confidence"] >= 90.0

def test_tamil_credibility_flow():
    """Verify Tamil claim processing, translation, and verification."""
    # True claim in Tamil
    res_true = _run_full_credibility_pipeline("நரேந்திர மோடி இந்தியாவின் பிரதமர் ஆவார்.", input_type="text")
    assert res_true["language"] == "ta"
    assert res_true["language_name"] == "Tamil"
    assert res_true["prediction_label"] == "LIKELY TRUE"
    assert res_true["confidence"] >= 90.0

    # Contradicted claim in Tamil
    res_false = _run_full_credibility_pipeline("இந்தியாவின் பிரதமர் ரொனால்டோ ஆவார்.", input_type="text")
    assert res_false["language"] == "ta"
    assert res_false["prediction_label"] == "LIKELY FALSE"
    assert res_false["confidence"] >= 90.0

def test_translation_service_unavailable_fallback(monkeypatch):
    """Verify that a translation service failure returns an appropriately cautious result without crashing."""
    def mock_failing_translate(text, source_lang):
        return {"success": False, "translated_text": "", "error": "Simulated translation network timeout"}

    monkeypatch.setattr(multilingual_service, "translate_to_english", mock_failing_translate)
    
    res = _run_full_credibility_pipeline("നരേന്ദ്ര മോദി ഇന്ത്യയുടെ പ്രധാനമന്ത്രിയാണ്.", input_type="text")
    assert res["prediction_label"] == "NOT YET VERIFIED"
    assert res["status_badge"] == "warning"
    assert res["confidence"] == 50.0
    assert "unreachable" in res["explanation"]
    assert res["language"] == "ml"

def test_multilingual_feature_flag_disable(monkeypatch):
    """Verify that disabling the multilingual feature restores standard direct execution."""
    monkeypatch.setattr(multilingual_service, "enabled", False)
    
    # Process an English claim with multilingual disabled
    res = _run_full_credibility_pipeline("Paris is the capital of France.", input_type="text")
    assert res["prediction_label"] == "LIKELY TRUE"
    assert res["language"] == "en"

def test_model_not_reloaded_per_request():
    """Verify that the model pipeline instance in memory is loaded once and reused."""
    initial_id = id(model_service.pipeline)
    
    _run_full_credibility_pipeline("Paris is the capital of France.", input_type="text")
    after_first_id = id(model_service.pipeline)
    
    _run_full_credibility_pipeline("Sundar Pichai is the CEO of Google.", input_type="text")
    after_second_id = id(model_service.pipeline)
    
    assert initial_id == after_first_id == after_second_id, "Model pipeline was reloaded!"

def test_api_health_endpoint():
    """Verify the health endpoint reports model status and multilingual capabilities."""
    with app.test_client() as client:
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert data["multilingual_enabled"] is True
        assert "ml" in data["supported_languages"]
        assert "hi" in data["supported_languages"]
        assert "ta" in data["supported_languages"]
