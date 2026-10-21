import pytest
from services.model_service import ModelService

@pytest.fixture(scope="module")
def model_service():
    return ModelService('models/fake_news_model.pkl', 'models/metadata.json')

def test_model_loading_and_metadata(model_service):
    assert model_service.is_loaded is True
    meta = model_service.get_metadata()
    assert meta.get("model_type") == "TF-IDF + Logistic Regression"
    assert meta.get("test_accuracy") == 0.9908
    assert meta.get("labels", {}).get("0") == "Fake News"
    assert meta.get("labels", {}).get("1") == "Real News"

def test_credible_news_prediction(model_service):
    text = "WASHINGTON (Reuters) - The U.S. Federal Reserve announced a modest adjustment in interest rates following its policy meeting on Wednesday."
    res = model_service.analyze_text(text)
    assert res["prediction_label"] == "Likely Credible"
    assert res["raw_label"] == 1
    assert res["confidence"] > 50.0
    assert res["word_count"] > 15
    assert len(res["feature_contributions"]) > 0

def test_misleading_news_prediction(model_service):
    text = "BREAKING SHOCKING: Leaked secret underground bunker documents reveal celebrity alien clone conspiracy confirmed by insiders!"
    res = model_service.analyze_text(text)
    assert res["prediction_label"] == "Likely Misleading"
    assert res["raw_label"] == 0
    assert res["confidence"] > 50.0
    assert res["word_count"] > 10

def test_too_short_input_uncertainty(model_service):
    res = model_service.analyze_text("Hello there.")
    assert res["prediction_label"] == "Uncertain"
    assert res["is_uncertain"] is True
    assert res["confidence"] == 50.0

def test_feature_contributions_have_direction(model_service):
    text = "Reuters reported on economic inflation figures released by official government statistical bureaus."
    res = model_service.analyze_text(text)
    features = res["feature_contributions"]
    assert isinstance(features, list)
    if features:
        top_f = features[0]
        assert "term" in top_f
        assert "direction" in top_f
        assert "abs_score" in top_f
