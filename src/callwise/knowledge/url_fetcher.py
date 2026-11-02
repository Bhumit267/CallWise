"""SSRF-protected web page fetcher and HTML content extractor."""

import ipaddress
import socket
from typing import Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx


def validate_public_url(url: str) -> None:
    """
    Validate that a URL uses http/https and does not resolve to internal,
    private, loopback, or cloud-metadata IP addresses.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must contain a valid hostname.")

    # Reject localhost directly
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        raise ValueError("SSRF Protection: Access to localhost is blocked.")

    # Resolve hostname to all associated IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as err:
        raise ValueError(f"Could not resolve hostname '{hostname}': {err}")

    for item in addr_info:
        ip_str = item[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        # Check standard reserved ranges
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(
                f"SSRF Protection: Access to private or internal address ({ip}) is blocked."
            )

        # Explicit check for cloud metadata (169.254.169.254)
        if str(ip) == "169.254.169.254":
            raise ValueError("SSRF Protection: Access to cloud metadata IP is blocked.")


def fetch_and_clean_html(url: str, max_redirects: int = 3, timeout_sec: float = 10.0) -> Tuple[str, str]:
    """
    Safely fetch a public URL (verifying redirects) and extract clean readable text.

    Returns:
        (extracted_text, page_title)
    """
    current_url = url
    redirect_count = 0

    headers = {
        "User-Agent": (
            "CallwiseBot/1.0 (+https://github.com/Bhumit267/CallWise; "
            "Receptionist Knowledge Ingestion)"
        ),
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
    }

    with httpx.Client(timeout=timeout_sec, follow_redirects=False) as client:
        while True:
            validate_public_url(current_url)

            response = client.get(current_url, headers=headers)

            # Handle redirects manually to re-validate destination IP
            if response.is_redirect:
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise ValueError(f"Too many redirects (limit is {max_redirects})")
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect response missing Location header")
                current_url = urljoin(current_url, location)
                continue

            response.raise_for_status()
            break

    html_content = response.text
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title and soup.find("h1"):
        h1 = soup.find("h1")
        if h1 and h1.string:
            title = h1.string.strip()
    if not title:
        title = urlparse(url).netloc

    # Strip noisy elements
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe", "form"]):
        tag.decompose()

    # Extract body or main content
    main_elem = soup.find("main") or soup.find("article") or soup.body or soup
    text = main_elem.get_text(separator="\n", strip=True)

    # Normalize excessive blank lines
    cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned_text = "\n\n".join(cleaned_lines)

    if not cleaned_text:
        raise ValueError(f"No readable content could be extracted from {url}")

    return cleaned_text, title
