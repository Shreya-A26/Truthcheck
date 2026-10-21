import re
import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional

logger = logging.getLogger("truthlens.multilingual")

class MultilingualService:
    """
    Isolated Multilingual Processing Layer for TruthLens.
    Supports English, Malayalam, Hindi, and Tamil without altering
    the pre-trained English ML model or degrading English detection performance.
    """

    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'ml': 'Malayalam',
        'hi': 'Hindi',
        'ta': 'Tamil'
    }

    def __init__(self, enabled: bool = True, timeout: int = 5):
        self.enabled = enabled
        self.timeout = timeout
        self._translation_cache: Dict[str, str] = {}
        self._max_cache_size = 500

    def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Fast, zero-dependency, deterministic script-based language detection.
        Immediately identifies English (Latin script), Malayalam, Devanagari (Hindi),
        and Tamil using Unicode codepoint ranges with sub-millisecond execution.
        """
        if not text or not text.strip():
            return {"code": "en", "name": "English", "is_english": True, "confidence": 1.0}

        cleaned = text.strip()
        
        # Count script occurrences
        ml_count = 0
        hi_count = 0
        ta_count = 0
        latin_count = 0

        for ch in cleaned:
            cp = ord(ch)
            if 0x0D00 <= cp <= 0x0D7F:
                ml_count += 1
            elif 0x0900 <= cp <= 0x097F:
                hi_count += 1
            elif 0x0B80 <= cp <= 0x0BFF:
                ta_count += 1
            elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
                latin_count += 1

        total_indic = ml_count + hi_count + ta_count
        if total_indic == 0:
            return {
                "code": "en",
                "name": "English",
                "is_english": True,
                "confidence": 1.0
            }

        # Determine dominant Indic language
        counts = [('ml', ml_count), ('hi', hi_count), ('ta', ta_count)]
        counts.sort(key=lambda x: x[1], reverse=True)
        dominant_code, dominant_count = counts[0]

        if dominant_count > 0:
            return {
                "code": dominant_code,
                "name": self.SUPPORTED_LANGUAGES.get(dominant_code, "Unknown"),
                "is_english": False,
                "confidence": round(dominant_count / (total_indic + latin_count or 1), 2)
            }

        return {
            "code": "en",
            "name": "English",
            "is_english": True,
            "confidence": 1.0
        }

    def translate_to_english(self, text: str, source_lang: str) -> Dict[str, Any]:
        """
        Translates Malayalam, Hindi, or Tamil text to English with resilient
        retries and caching. Never crashes the caller on network or service issues.
        """
        if not text or not text.strip():
            return {"success": False, "translated_text": "", "error": "Empty text provided"}

        if source_lang == 'en':
            return {"success": True, "translated_text": text.strip(), "source_lang": "en"}

        clean_text = text.strip()
        cache_key = f"{source_lang}:{clean_text}"
        if cache_key in self._translation_cache:
            return {
                "success": True,
                "translated_text": self._translation_cache[cache_key],
                "source_lang": source_lang,
                "cached": True
            }

        # Translation Strategy 1: Google Translate single-shot gtx web endpoint
        try:
            encoded_query = urllib.parse.quote(clean_text)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl=en&dt=t&q={encoded_query}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "*/*"
                }
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_data = resp.read().decode('utf-8')
                data = json.loads(raw_data)
                translated_parts = [part[0] for part in data[0] if part and len(part) > 0 and part[0]]
                translated = "".join(translated_parts).strip()
                
                if translated:
                    self._cache_translation(cache_key, translated)
                    logger.info(f"[MULTILINGUAL-TRANSLATE] {source_lang} -> en: '{clean_text[:60]}' -> '{translated[:60]}'")
                    return {
                        "success": True,
                        "translated_text": translated,
                        "source_lang": source_lang,
                        "cached": False
                    }
        except Exception as e1:
            logger.warning(f"[MULTILINGUAL-TRANSLATE] Primary endpoint failed for {source_lang}: {e1}")

        # Translation Strategy 2: deep_translator fallback
        try:
            from deep_translator import GoogleTranslator
            fallback_translator = GoogleTranslator(source=source_lang, target='en')
            fallback_translated = fallback_translator.translate(clean_text)
            if fallback_translated and fallback_translated.strip():
                result = fallback_translated.strip()
                self._cache_translation(cache_key, result)
                return {
                    "success": True,
                    "translated_text": result,
                    "source_lang": source_lang,
                    "cached": False
                }
        except Exception as e2:
            logger.warning(f"[MULTILINGUAL-TRANSLATE] Fallback translator failed for {source_lang}: {e2}")

        # Graceful failure return (never crash the caller)
        return {
            "success": False,
            "translated_text": "",
            "source_lang": source_lang,
            "error": "External translation service unreachable or timed out."
        }

    def _cache_translation(self, key: str, value: str):
        if len(self._translation_cache) >= self._max_cache_size:
            # Purge oldest entries
            self._translation_cache.clear()
        self._translation_cache[key] = value

    def clear_cache(self):
        """Clears translation cache for testing."""
        self._translation_cache.clear()
