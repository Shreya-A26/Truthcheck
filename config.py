import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'truthlens-editorial-secret-key-prod-2026')
    
    # Model Artifacts
    MODEL_PATH = os.environ.get('MODEL_PATH', str(BASE_DIR / 'models' / 'fake_news_model.pkl'))
    METADATA_PATH = os.environ.get('METADATA_PATH', str(BASE_DIR / 'models' / 'metadata.json'))
    
    # Storage & Database
    INSTANCE_DIR = BASE_DIR / 'instance'
    DATABASE_PATH = os.environ.get('DATABASE_PATH', str(INSTANCE_DIR / 'truthlens.db'))
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(INSTANCE_DIR / 'uploads'))
    
    # Upload limits
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024  # 30 MB max
    ALLOWED_EXTENSIONS_DOC = {'pdf'}
    ALLOWED_EXTENSIONS_IMAGE = {'png', 'jpg', 'jpeg', 'webp'}
    ALLOWED_EXTENSIONS_VIDEO = {'mp4', 'mov', 'avi', 'mkv'}
    
    # Processing limits
    MAX_TEXT_LENGTH = 50000  # max characters
    MIN_TEXT_LENGTH = 15     # min characters for meaningful news analysis
    MAX_PDF_PAGES = 15       # page cap to prevent resource exhaustion
    MAX_VIDEO_FRAMES = 10    # maximum sampled frames for video OCR
    MAX_VIDEO_DURATION_SEC = 60  # max video length in seconds
    
    # Request & SSRF timeouts
    URL_FETCH_TIMEOUT = 8    # seconds
    MAX_REDIRECTS = 3
    
    # Optional External APIs
    NEWS_API_KEY = os.environ.get('NEWS_API_KEY', '')
    SEARCH_API_KEY = os.environ.get('SEARCH_API_KEY', '')

    # Multilingual Configuration (English, Malayalam, Hindi, Tamil)
    ENABLE_MULTILINGUAL = os.environ.get('ENABLE_MULTILINGUAL', 'true').lower() in ('true', '1', 'yes')
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'ml': 'Malayalam',
        'hi': 'Hindi',
        'ta': 'Tamil'
    }
    TRANSLATION_TIMEOUT = int(os.environ.get('TRANSLATION_TIMEOUT', 5))
