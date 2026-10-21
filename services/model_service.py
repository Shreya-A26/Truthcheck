import os
import json
import logging
import joblib
import numpy as np

logger = logging.getLogger(__name__)

class ModelService:
    def __init__(self, model_path=None, metadata_path=None):
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.pipeline = None
        self.metadata = {}
        self.is_loaded = False
        self.load_error = None
        
        self.feature_names = None
        self.coefs = None
        self._analysis_cache = {}
        
        if model_path and metadata_path:
            self.load()

    def load(self):
        """Loads the model and metadata artifacts once from disk."""
        try:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file not found at: {self.model_path}")
            if not os.path.exists(self.metadata_path):
                raise FileNotFoundError(f"Metadata file not found at: {self.metadata_path}")
            
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
                
            self.pipeline = joblib.load(self.model_path)
            
            # Precompute feature names and coefficients for high-efficiency inference
            try:
                tfidf = self.pipeline.named_steps.get('tfidf')
                clf = self.pipeline.named_steps.get('classifier')
                if tfidf and clf and hasattr(clf, 'coef_'):
                    self.feature_names = np.array(tfidf.get_feature_names_out())
                    self.coefs = clf.coef_[0]
            except Exception as fe:
                logger.warning(f"Could not precompute feature arrays: {fe}")

            self.is_loaded = True
            self.load_error = None
            logger.info("TruthLens model pipeline and metadata successfully loaded.")
        except Exception as e:
            self.is_loaded = False
            self.load_error = str(e)
            logger.error(f"Failed to load model artifacts: {e}", exc_info=True)
            raise

    def analyze_text(self, text: str):
        """
        Runs inference on news text and returns comprehensive credibility assessment,
        calibrated confidence, word count, and model explanation.
        """
        if not self.is_loaded:
            raise RuntimeError(f"Model is not loaded: {self.load_error or 'Unknown initialization error'}")
            
        clean_text = text.strip()
        words = clean_text.split()
        word_count = len(words)

        # Check in-memory prediction cache
        cache_key = hash(clean_text)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]
        
        if word_count < 3 or len(clean_text) < 15:
            res = {
                "prediction_label": "Uncertain",
                "raw_label": -1,
                "confidence": 50.0,
                "probabilities": {"fake": 0.5, "real": 0.5},
                "word_count": word_count,
                "explanation": "The submitted text is too brief to provide a reliable linguistic pattern analysis.",
                "feature_contributions": [],
                "is_uncertain": True,
                "status_badge": "warning",
                "model_type": self.metadata.get("model_type", "TF-IDF + Logistic Regression"),
                "test_accuracy": self.metadata.get("test_accuracy", 0.9908)
            }
            return res

        # Model inference via pipeline
        proba = self.pipeline.predict_proba([clean_text])[0]
        prob_fake = float(proba[0])
        prob_real = float(proba[1])

        # Stylistic Sensationalism & Clickbait Heuristic Adjustment
        caps_words = [w for w in words if w.isupper() and len(w) > 2 and w not in ('USA', 'UK', 'NASA', 'ISRO', 'WHO', 'UN', 'FBI', 'CIA', 'PM', 'CEO')]
        exclamation_count = clean_text.count('!')
        if len(caps_words) >= 2 or exclamation_count >= 2:
            # Shift slightly towards fake/misleading probability for excessive sensational punctuation
            prob_fake = min(0.99, prob_fake + 0.15)
            prob_real = max(0.01, 1.0 - prob_fake)
        
        # Decision logic with documented uncertainty boundary
        if 0.45 <= prob_real <= 0.55:
            prediction_label = "Uncertain"
            raw_label = -1
            confidence = round(max(prob_fake, prob_real) * 100, 1)
            status_badge = "neutral"
            explanation = (
                "The statistical patterns in this text do not strongly align with either "
                "credible journalistic reports or misleading text from the training data. "
                "Further independent verification is strongly advised."
            )
        elif prob_real > 0.55:
            prediction_label = "Likely Credible"
            raw_label = 1
            confidence = round(prob_real * 100, 1)
            status_badge = "success"
            explanation = (
                "Our machine-learning model classified this article as likely credible based on "
                "vocabulary structure, dateline phrasing, and informational tone typical of authentic news reports. "
                "This prediction is an initial assessment and should be examined alongside independent evidence."
            )
        else:
            prediction_label = "Likely Misleading"
            raw_label = 0
            confidence = round(prob_fake * 100, 1)
            status_badge = "error"
            explanation = (
                "Our machine-learning model classified this article as likely misleading based on "
                "rhetorical framing and phrase frequencies observed in deceptive or fabricated reports during training. "
                "This prediction is an initial assessment and should be examined alongside independent evidence."
            )

        # Feature influence / Explainability
        feature_contributions = self._extract_influential_terms(clean_text)

        result = {
            "prediction_label": prediction_label,
            "raw_label": raw_label,
            "confidence": confidence,
            "probabilities": {
                "fake": round(prob_fake * 100, 1),
                "real": round(prob_real * 100, 1)
            },
            "word_count": word_count,
            "explanation": explanation,
            "feature_contributions": feature_contributions,
            "is_uncertain": (prediction_label == "Uncertain"),
            "status_badge": status_badge,
            "model_type": self.metadata.get("model_type", "TF-IDF + Logistic Regression"),
            "test_accuracy": self.metadata.get("test_accuracy", 0.9908)
        }

        # Cache last 200 items
        if len(self._analysis_cache) > 200:
            self._analysis_cache.clear()
        self._analysis_cache[cache_key] = result
        return result

    def _extract_influential_terms(self, text: str, max_terms=8):
        """
        Calculates term contribution using TF-IDF weights and precomputed Logistic Regression coefficients.
        Positive coefficient * weight pushes toward Class 1 (Real News).
        Negative coefficient * weight pushes toward Class 0 (Fake News).
        """
        try:
            tfidf = self.pipeline.named_steps.get('tfidf')
            if not tfidf or self.feature_names is None or self.coefs is None:
                return []
                
            vec_input = tfidf.transform([text])
            nonzero_indices = vec_input.nonzero()[1]
            
            if len(nonzero_indices) == 0:
                return []
                
            contributions = []
            for idx in nonzero_indices:
                weight = vec_input[0, idx]
                coef = self.coefs[idx]
                score = weight * coef
                contributions.append({
                    "term": str(self.feature_names[idx]),
                    "score": float(score),
                    "abs_score": float(abs(score)),
                    "direction": "Credible indicator" if score > 0 else "Misleading indicator",
                    "lean": "real" if score > 0 else "fake"
                })
                
            # Sort by absolute impact
            contributions.sort(key=lambda x: x["abs_score"], reverse=True)
            return contributions[:max_terms]
        except Exception as e:
            logger.warning(f"Could not compute feature influence: {e}")
            return []

    def get_metadata(self):
        """Returns loaded model metadata."""
        return self.metadata
