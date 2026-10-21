import pytest
from app import _run_full_credibility_pipeline

@pytest.mark.parametrize("claim_text,expected_assessment", [
    ("The Prime Minister of India was Ronaldo.", "LIKELY FALSE"),
    ("Narendra Modi is the Prime Minister of India.", "LIKELY TRUE"),
    ("Drinking boiled garlic water cures coronavirus infection within 24 hours.", "LIKELY FALSE"),
    ("NASA confirms Earth will plunge into complete darkness for six days due to planetary alignment.", "LIKELY FALSE"),
    ("Elon Musk is the President of France.", "LIKELY FALSE"),
    ("WASHINGTON (Reuters) - The U.S. Federal Reserve announced interest rates would remain steady on Wednesday.", "LIKELY TRUE"),
    ("Government installing 5G microchips inside currency notes to track bank accounts.", "LIKELY FALSE"),
    ("Secret underground tunnels beneath city hospital where politicians harvest children blood.", "LIKELY FALSE"),
    ("Paris is the capital of France.", "LIKELY TRUE"),
    ("Sydney is the capital of Australia.", "LIKELY FALSE"),
    ("prime minister of india is Rajeev chandrashekhar", "LIKELY FALSE"),
    ("Sundar Pichai is the CEO of Google", "LIKELY TRUE"),
    ("Pinarayi Vijayan is the Chief Minister of Kerala.", "LIKELY TRUE"),
    ("Joe Biden is the President of the United States.", "LIKELY FALSE"),
    ("president of india declare an war over Russia", "LIKELY FALSE"),
    ("trump is minister of india", "LIKELY FALSE"),
    ("trump is a minister of india", "LIKELY FALSE")
])
def test_factual_credibility_accuracy(claim_text, expected_assessment):
    res = _run_full_credibility_pipeline(claim_text, input_type="test")
    assert res["prediction_label"] == expected_assessment
    assert res["confidence"] >= 50.0
    assert len(res["explanation"]) > 20
