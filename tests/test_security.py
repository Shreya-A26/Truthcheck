import pytest
from services.article_extraction import validate_url_safe, SSRFException

def test_ssrf_rejects_localhost():
    with pytest.raises(SSRFException):
        validate_url_safe("http://localhost/admin")

    with pytest.raises(SSRFException):
        validate_url_safe("http://127.0.0.1:8080/secret")

    with pytest.raises(SSRFException):
        validate_url_safe("http://[::1]/internal")

def test_ssrf_rejects_private_ips():
    with pytest.raises(SSRFException):
        validate_url_safe("http://10.0.0.1/status")

    with pytest.raises(SSRFException):
        validate_url_safe("http://192.168.1.100/router")

    with pytest.raises(SSRFException):
        validate_url_safe("http://172.16.0.5/api")

    with pytest.raises(SSRFException):
        validate_url_safe("http://169.254.169.254/latest/meta-data/")

def test_ssrf_rejects_invalid_schemes():
    with pytest.raises(SSRFException):
        validate_url_safe("file:///etc/passwd")

    with pytest.raises(SSRFException):
        validate_url_safe("ftp://ftp.example.com/data")

def test_ssrf_accepts_valid_public_domain():
    # Public domain should validate without error
    url = "https://www.wikipedia.org"
    validated = validate_url_safe(url)
    assert validated == url
