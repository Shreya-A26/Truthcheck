import re
import urllib.parse
import xml.etree.ElementTree as ET
import logging
import requests

import time

logger = logging.getLogger(__name__)

COMPARISON_CACHE = {}
COMPARISON_TTL = 900  # 15 minutes

class SourceComparisonService:
    def compare_sources(self, topic_or_headline: str, max_sources: int = 4) -> dict:
        """
        Retrieves related coverage from distinct publishers to facilitate cross-source comparison.
        Returns actual retrieved reports or a clear empty state with caching.
        """
        cache_key = topic_or_headline.strip().lower()
        now = time.time()
        if cache_key in COMPARISON_CACHE:
            entry = COMPARISON_CACHE[cache_key]
            if now - entry.get("timestamp", 0) < COMPARISON_TTL:
                return entry.get("data")

        try:
            # Extract main keywords
            words = [w for w in re.findall(r'\b[A-Za-z0-9]{4,}\b', topic_or_headline) if w.lower() not in (
                "that", "this", "with", "from", "have", "been", "were", "said", "about", "their", "there", "news", "report"
            )]
            query = " ".join(words[:5])
            if not query:
                return {"available": False, "sources": [], "message": "Text does not contain enough searchable terms for related coverage comparison."}

            encoded_query = urllib.parse.quote_plus(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(rss_url, headers=headers, timeout=3)
            if resp.status_code != 200:
                return {
                    "available": False,
                    "sources": [],
                    "message": "Live news search provider is temporarily unreachable. Cross-source comparison is currently unavailable."
                }

            root = ET.fromstring(resp.content)
            items = []
            seen_publishers = set()

            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else "Recent"
                source_elem = item.find('source')
                publisher = source_elem.text if source_elem is not None else "News Outlet"

                clean_title = title
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    clean_title = parts[0]
                    if publisher == "News Outlet":
                        publisher = parts[1]

                if publisher in seen_publishers:
                    continue
                seen_publishers.add(publisher)

                items.append({
                    "publisher": publisher,
                    "headline": clean_title,
                    "pub_date": pub_date,
                    "url": link,
                    "coverage_note": "Independent publisher reporting on this event."
                })

                if len(items) >= max_sources:
                    break

            if not items:
                return {
                    "available": False,
                    "sources": [],
                    "message": "No related coverage from external publishers was found for this article topic."
                }

            res = {
                "available": True,
                "sources": items,
                "message": f"Retrieved {len(items)} related reports across distinct publishers for comparison."
            }
            COMPARISON_CACHE[cache_key] = {"data": res, "timestamp": now}
            return res

        except Exception as e:
            logger.warning(f"Source comparison failed: {e}")
            return {
                "available": False,
                "sources": [],
                "message": "External source comparison is currently unavailable."
            }
