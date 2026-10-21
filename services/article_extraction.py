import ipaddress
import socket
import urllib.parse
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)

# Reserved / Private IP networks that must be blocked to prevent SSRF
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]

class SSRFException(Exception):
    """Raised when a URL attempts to access private, local, or prohibited IP addresses."""
    pass

class ArticleExtractionException(Exception):
    """Raised when an article cannot be fetched or parsed."""
    pass

def validate_url_safe(url: str) -> str:
    """
    Validates URL scheme and resolves hostname to ensure it does not map
    to internal, private, loopback, or link-local network ranges.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFException("Only HTTP and HTTPS URLs are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFException("Invalid or missing hostname in URL.")

    # Disallow known localhost aliases
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "local"):
        raise SSRFException("Access to local infrastructure is prohibited.")

    try:
        # Resolve all IPs for the host
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise SSRFException(f"Could not resolve host: {hostname}")

    for item in addr_info:
        ip_str = item[4][0]
        ip_obj = ipaddress.ip_address(ip_str)
        for net in BLOCKED_NETWORKS:
            if ip_obj in net:
                raise SSRFException(f"Access to restricted IP range ({ip_str}) is prohibited.")

    return url

def fetch_url_with_ssrf_protection(url: str, max_redirects=3, timeout=8) -> tuple[str, str]:
    """
    Safely fetches a web page, re-validating SSRF rules on every HTTP redirect hop.
    Returns (html_content, final_url).
    """
    current_url = url
    session = requests.Session()
    session.headers.update({
        "User-Agent": "TruthLens/1.0 (+https://truthlens.local/about; NewsCredibilityBot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    })

    for _ in range(max_redirects + 1):
        validate_url_safe(current_url)
        try:
            resp = session.get(current_url, allow_redirects=False, timeout=timeout, stream=True)
        except requests.RequestException as e:
            raise ArticleExtractionException(f"Network error while connecting to source: {e}")

        # Check for redirects
        if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
            redirect_target = resp.headers.get("Location")
            if not redirect_target:
                raise ArticleExtractionException("Redirect response missing Location header.")
            current_url = urllib.parse.urljoin(current_url, redirect_target)
            continue

        if resp.status_code != 200:
            raise ArticleExtractionException(f"Publisher returned HTTP {resp.status_code}.")

        # Enforce content-type and size checks (max 5 MB for HTML)
        content_type = resp.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            raise ArticleExtractionException(f"Unsupported content type '{content_type}'. Must be HTML news page.")

        # Read safely with size limit
        content = resp.raw.read(5 * 1024 * 1024, decode_content=True)
        try:
            html_text = content.decode(resp.encoding or "utf-8", errors="replace")
        except Exception:
            html_text = content.decode("utf-8", errors="replace")

        return html_text, current_url

    raise SSRFException("Too many redirects encountered.")

def extract_article_from_url(url: str) -> dict:
    """
    Fetches URL safely and extracts title, publication date, author, domain, and body text.
    """
    html_text, final_url = fetch_url_with_ssrf_protection(url)
    parsed = urllib.parse.urlparse(final_url)
    domain = parsed.netloc.replace("www.", "")

    soup = BeautifulSoup(html_text, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "form", "svg"]):
        tag.decompose()

    # Title extraction
    title = ""
    og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text().strip()

    # Author extraction
    author = "Not available"
    author_meta = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", property="article:author")
    if author_meta and author_meta.get("content"):
        author = author_meta["content"].strip()

    # Publication date extraction
    pub_date = "Not available"
    date_meta = (
        soup.find("meta", property="article:published_time") or
        soup.find("meta", attrs={"name": "pubdate"}) or
        soup.find("meta", attrs={"name": "publishdate"}) or
        soup.find("time")
    )
    if date_meta:
        if date_meta.get("content"):
            pub_date = date_meta["content"].strip()
        elif date_meta.get("datetime"):
            pub_date = date_meta["datetime"].strip()
        elif hasattr(date_meta, "get_text"):
            pub_date = date_meta.get_text().strip()

    # Main text extraction
    # Try finding article tag first
    article_tag = soup.find("article") or soup.find("main") or soup.find(id=lambda x: x and "article" in x.lower())
    if article_tag:
        paragraphs = [p.get_text().strip() for p in article_tag.find_all("p") if len(p.get_text().strip()) > 20]
    else:
        paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 20]

    body_text = "\n\n".join(paragraphs).strip()
    if not body_text or len(body_text) < 40:
        # Fallback to general text
        body_text = soup.get_text(separator="\n", strip=True)

    if not body_text or len(body_text.strip()) < 15:
        raise ArticleExtractionException("Could not extract readable article text from the provided webpage.")

    return {
        "title": title or "Untitled Article",
        "domain": domain,
        "author": author,
        "publication_date": pub_date,
        "original_url": final_url,
        "body_text": body_text[:40000] # Safe upper limit
    }
