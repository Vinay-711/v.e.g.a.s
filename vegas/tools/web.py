"""
Web research and API integration tools for the Vegas Assistant.
Exposes tools for web search, URL fetching, and news retrieval.
"""

import os
import re
import subprocess
import urllib.parse
import html as html_module
from urllib.parse import urlparse, parse_qs
import requests
from vegas.memory import log_event

def clean_html(text: str) -> str:
    """
    Helper function to clean HTML tags and unescape HTML entities.
    """
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Unescape HTML entities
    text = html_module.unescape(text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def ddg_search(query: str, num_results: int = 5) -> str:
    """
    Performs a DuckDuckGo HTML search as a no-key fallback.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        # DuckDuckGo HTML search endpoint
        response = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        html_content = response.text
        
        results = []
        
        # Try matching h2 result__title blocks and result__snippet blocks
        title_blocks = re.findall(r'<h2 class="result__title">.*?</h2>', html_content, flags=re.DOTALL)
        snippet_blocks = re.findall(r'<a class="result__snippet"[^>]*>.*?</a>|<span class="result__snippet"[^>]*>.*?</span>', html_content, flags=re.DOTALL)
        
        for i in range(min(len(title_blocks), num_results)):
            title_block = title_blocks[i]
            url_match = re.search(r'href="([^"]+)"', title_block)
            title_match = re.search(r'<a[^>]*>(.*?)</a>', title_block, flags=re.DOTALL)
            
            if not url_match or not title_match:
                continue
                
            url = url_match.group(1)
            title = clean_html(title_match.group(1))
            
            # Extract query params if URL is a DuckDuckGo redirect link containing 'uddg='
            if "uddg=" in url:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                if "uddg" in qs:
                    url = qs["uddg"][0]
                    
            # Skip advertisements or internal links
            if url.startswith("//") or "duckduckgo.com/y.js" in url:
                continue
                
            snippet = "No description available."
            if i < len(snippet_blocks):
                snippet_text = re.sub(r'<[^>]+>', '', snippet_blocks[i])
                snippet = clean_html(snippet_text)
                
            results.append((title, snippet, url))
            
        # Fallback to result__body parser if titles/snippets were empty
        if not results:
            bodies = re.findall(r'<div class="[^"]*result__body[^"]*">(.*?)</div>\s*</div>', html_content, flags=re.DOTALL)
            for body in bodies:
                if len(results) >= num_results:
                    break
                url_match = re.search(r'<a class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, flags=re.DOTALL)
                if not url_match:
                    continue
                url, title = url_match.groups()
                snippet_match = re.search(r'<(?:a|span) class="result__snippet"[^>]*>(.*?)</(?:a|span)>', body, flags=re.DOTALL)
                snippet = snippet_match.group(1) if snippet_match else "No description available."
                
                title = clean_html(title)
                snippet = clean_html(snippet)
                
                if "uddg=" in url:
                    parsed = urlparse(url)
                    qs = parse_qs(parsed.query)
                    if "uddg" in qs:
                        url = qs["uddg"][0]
                        
                if url.startswith("//") or "duckduckgo.com/y.js" in url:
                    continue
                    
                results.append((title, snippet, url))
                
        if not results:
            return "VEGAS: No results found."
            
        formatted = []
        for i, (title, snippet, url) in enumerate(results, 1):
            formatted.append(f"{i}. {title}\n   Snippet: {snippet}\n   URL: {url}")
        return "\n\n".join(formatted)
        
    except Exception as e:
        return f"VEGAS: Web search failed due to network or parsing error: {str(e)}"

def search_web(query: str, num_results: int = 5) -> str:
    """
    Performs a web search and returns a formatted string of top results.

    Args:
        query: The search term to query.
        num_results: The number of top results to return (default 5).
    """
    return ddg_search(query, num_results)

def fetch_url(url: str) -> str:
    """
    Fetches the content of a URL, cleans HTML tags to produce readable text,
    and returns the first 3000 characters.

    Args:
        url: The absolute web address to fetch content from.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return response.text[:3000]
            
        html = response.text
        
        # Remove script and style elements
        html = re.sub(r'<(script|style)[^>]*?>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        # Replace block tags with newlines to preserve readability
        html = re.sub(r'</?(?:p|div|h\d|li|tr|br)[^>]*?>', '\n', html, flags=re.IGNORECASE)
        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Unescape HTML entities
        text = html_module.unescape(text)
        # Normalize whitespace (but keep some newlines for readability)
        lines = [line.strip() for line in text.splitlines()]
        cleaned_text = '\n'.join([line for line in lines if line])
        # Condense consecutive newlines
        cleaned_text = re.sub(r'\n+', '\n', cleaned_text)
        
        if not cleaned_text:
            return "VEGAS: The URL fetched successfully but contained no readable text."
            
        return cleaned_text[:3000]
    except Exception as e:
        return f"VEGAS: Fetch URL failed due to network or parsing error: {str(e)}"

def get_world_news(topic: str = "general", num_results: int = 5) -> str:
    """
    Fetches recent news headlines for a topic and returns a formatted summary.

    Args:
        topic: The news category or topic to search (default "general").
        num_results: The number of news articles to retrieve.
    """
    news_api_key = os.getenv("NEWS_API_KEY")
    if news_api_key:
        try:
            categories = ["business", "entertainment", "general", "health", "science", "sports", "technology"]
            url = "https://newsapi.org/v2/top-headlines"
            params = {"apiKey": news_api_key, "pageSize": num_results}
            if topic.lower() in categories:
                params["category"] = topic.lower()
            else:
                params["q"] = topic
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("articles", [])
            if not articles:
                return f"VEGAS: No news articles found for topic '{topic}' using NewsAPI."
                
            formatted = []
            for i, art in enumerate(articles[:num_results], 1):
                title = art.get("title", "No Title")
                desc = art.get("description", "No Description Available.")
                source = art.get("source", {}).get("name", "Unknown Source")
                art_url = art.get("url", "No URL")
                formatted.append(f"{i}. {title} ({source})\n   Summary: {desc}\n   URL: {art_url}")
            return "\n\n".join(formatted)
        except Exception:
            # Fallback to search-based query on any NewsAPI failures
            pass

    # Fallback to search-based news approach using DuckDuckGo
    search_query = f"{topic} news"
    return ddg_search(search_query, num_results)

def open_world_monitor() -> str:
    """
    Returns a short formatted situation report combining top headlines from
    world, tech, and business topics. Stylized like a Tony Stark-esque HUD.
    """
    world_news = get_world_news("world", num_results=2)
    tech_news = get_world_news("tech", num_results=2)
    biz_news = get_world_news("business", num_results=2)
    
    hud = [
        "======================================================================",
        "                     [ VEGAS HUD SYSTEM MONITOR ]                     ",
        "======================================================================",
        " STATUS: ONLINE | DATABASE: CONNECTED | COGNITIVE CORE: OPTIMAL",
        "----------------------------------------------------------------------",
        "\n[ SECTION I: GLOBAL CHRONICLES ]",
        world_news,
        "\n[ SECTION II: TECHNOLOGICAL FRONTIERS ]",
        tech_news,
        "\n[ SECTION III: MARKET DYNAMICS ]",
        biz_news,
        "\n----------------------------------------------------------------------",
        " MONITOR REPORT COMPLETE // ALL SYSTEMS GO // VEGAS AGENT OUT.",
        "======================================================================"
    ]
    
    return "\n".join(hud)

def open_map_location(location: str) -> str:
    """
    Opens Google Maps directly in the user's default browser for the specified location, address, landmark, or map search.
    Use this whenever the user asks to search a place on maps, show/open a location on maps, get directions, or locate a place.

    Args:
        location: The place name, city, address, or landmark (e.g. "Ramanagara", "Eiffel Tower Paris", "Times Square").
    """
    try:
        log_event("web", "Open map location", location)
        encoded = urllib.parse.quote_plus(location)
        map_url = f"https://www.google.com/maps/search/?api=1&query={encoded}"
        subprocess.Popen(["open", map_url])
        return f"🗺️ Opening Google Maps for \"{location}\" directly in your browser!"
    except Exception as e:
        return f"VEGAS: Failed to open map location: {str(e)}"

def open_in_browser(url: str) -> str:
    """
    Opens a web URL directly in the user's default web browser.
    Use this when the user asks to open a website, URL, or webpage.

    Args:
        url: The web URL to open (e.g. "https://google.com" or "https://wikipedia.org").
    """
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        log_event("web", "Open in browser", url)
        subprocess.Popen(["open", url])
        return f"🌐 Opening web page: {url} in your browser!"
    except Exception as e:
        return f"VEGAS: Failed to open URL in browser: {str(e)}"

def register(mcp) -> None:
    """
    Registers the web tools with the provided FastMCP server instance.
    """
    mcp.tool()(search_web)
    mcp.tool()(fetch_url)
    mcp.tool()(get_world_news)
    mcp.tool()(open_world_monitor)
    mcp.tool()(open_map_location)
    mcp.tool()(open_in_browser)

