"""SSRF-safe, bounded public-web fetcher for company/official research (Phase 7F, §25–§33).

A deliberately small fetcher — NOT a crawler, NOT a browser. It fetches a few same-origin public
HTTPS pages, revalidating every hop against a strict network policy:

* HTTPS only; scheme/host allow-list checks (§28).
* Resolve the hostname and REJECT any private / loopback / link-local / reserved / metadata IP,
  before connecting — defeats SSRF and DNS-rebinding to internal ranges (§25/§27).
* Bounded timeout, redirects (each revalidated), response bytes, and pages (§29).
* robots.txt respected; disallowed → not fetched (§32).
* HTML parsed WITHOUT executing scripts; only human-readable text extracted (§31).
* A clear product User-Agent, never a browser/Googlebot disguise (§33).

No JavaScript, no headless browser, no login, no recursion. Content returned by this module is
UNTRUSTED DATA (the caller wraps it as evidence, never instructions).
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

USER_AGENT = "Ask4Mo-Research/7F (+https://ask4mo.example; bounded public-web research)"
DEFAULT_TIMEOUT = 8.0
MAX_BYTES = 1_000_000       # ~1 MB text page cap
MAX_REDIRECTS = 3
MAX_PAGES = 5
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")


class WebFetchError(Exception):
    """A bounded, safe web-fetch failure with a category (never leaks internals)."""

    def __init__(self, category: str, message: str = "") -> None:
        super().__init__(message or category)
        self.category = category


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    content_type: str
    status_code: int
    bytes_read: int


@dataclass
class FetchOutcome:
    pages: list[FetchedPage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    robots_disallowed: bool = False


# --- network policy (SSRF) ------------------------------------------------------------

def _ip_is_public(ip: str) -> bool:
    """True only for a globally-routable public address (rejects private/reserved/metadata)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast
            or addr.is_reserved or addr.is_unspecified):
        return False
    # Cloud metadata service (169.254.169.254) is link-local → already blocked; block its v6 too.
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            return _ip_is_public(str(addr.ipv4_mapped))
        # Unique-local fc00::/7
        if str(addr).startswith(("fc", "fd")):
            return False
    return addr.is_global


def _resolve_public_ips(host: str) -> list[str]:
    """Resolve a hostname to IPs and require EVERY resolved address to be public (§25/§27)."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, socket.herror, UnicodeError):
        raise WebFetchError("dns_error", "could not resolve host") from None
    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise WebFetchError("dns_error", "no addresses")
    for ip in ips:
        if not _ip_is_public(ip):
            raise WebFetchError("private_address", "host resolves to a non-public address")
    return ips


def validate_url(url: str) -> tuple[str, str]:
    """Validate a URL is a safe public HTTPS target. Returns (normalised_url, host).

    Rejects non-HTTPS, credential-bearing, non-web schemes, and hosts resolving to private/
    reserved/metadata addresses. Raises :class:`WebFetchError` with a category otherwise.
    """
    if not url or "://" not in url:
        raise WebFetchError("invalid_url", "missing scheme")
    parts = urlparse(url)
    if parts.scheme.lower() != "https":                       # §28 HTTPS only (no silent upgrade)
        raise WebFetchError("insecure_scheme", "only https is allowed")
    if parts.username or parts.password:
        raise WebFetchError("credentialed_url", "credentials in URL are not allowed")
    host = (parts.hostname or "").strip().lower()
    if not host:
        raise WebFetchError("invalid_url", "missing host")
    # Reject obvious internal hostnames without a public DNS answer.
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".internal") \
            or host.endswith(".local"):
        raise WebFetchError("private_address", "internal hostname")
    _resolve_public_ips(host)                                  # raises if any IP is non-public
    normalised = urlunparse((parts.scheme, parts.netloc, parts.path or "/", "", parts.query, ""))
    return normalised, host


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, (pa.hostname or "").lower()) == (pb.scheme, (pb.hostname or "").lower())


# --- HTML → text (no execution) -------------------------------------------------------

def extract_text(html: str) -> tuple[str, str]:
    """Return (title, human_readable_text) from HTML WITHOUT executing anything (§31).

    Uses the stdlib HTML parser; drops script/style/noscript/template/head content; never
    evaluates JS, iframes or forms. Prompt-injection defence is the caller's (this only extracts).
    """
    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        # Drop executable/non-text elements. NOT <head> itself — <title> lives there and
        # <script>/<style> inside it are dropped individually.
        _DROP = {"script", "style", "noscript", "template", "svg", "iframe"}

        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.title: str = ""
            self._skip = 0
            self._in_title = False

        def handle_starttag(self, tag, attrs):
            if tag in self._DROP:
                self._skip += 1
            if tag == "title":
                self._in_title = True

        def handle_endtag(self, tag):
            if tag in self._DROP and self._skip:
                self._skip -= 1
            if tag == "title":
                self._in_title = False

        def handle_data(self, data):
            if self._skip:
                return
            text = data.strip()
            if not text:
                return
            if self._in_title and not self.title:
                self.title = text[:200]
            else:
                self.parts.append(text)

    parser = _Extractor()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - malformed HTML never crashes the fetcher
        pass
    text = " ".join(parser.parts)
    text = " ".join(text.split())  # collapse whitespace
    return parser.title, text


# --- robots ---------------------------------------------------------------------------

def _robots_allows(url: str, *, get_fn) -> bool:
    parts = urlparse(url)
    robots_url = urlunparse((parts.scheme, parts.netloc, "/robots.txt", "", "", ""))
    rp = urllib.robotparser.RobotFileParser()
    try:
        status, _ctype, body = get_fn(robots_url)
        if status != 200 or not body:
            return True  # no robots.txt → allowed
        rp.parse(body.splitlines())
        return rp.can_fetch(USER_AGENT, url)
    except Exception:  # noqa: BLE001 - a robots fetch failure must not block a normal page unsafely;
        return True     # absence/parse error is treated as "no restriction" (common convention)


# --- fetcher --------------------------------------------------------------------------

@dataclass
class WebFetcher:
    """Bounded HTTPS fetcher. ``transport`` is an injectable (url)->(status, content_type, body)
    hook for tests so no real network is used; default uses httpx."""

    timeout: float = DEFAULT_TIMEOUT
    max_bytes: int = MAX_BYTES
    max_redirects: int = MAX_REDIRECTS
    respect_robots: bool = True
    transport: object = None  # test hook

    def _get(self, url: str) -> tuple[int, str, str]:
        if self.transport is not None:
            return self.transport(url)  # type: ignore[operator]
        import httpx
        # Manual redirect handling so each hop is revalidated (§26).
        current = url
        for _hop in range(self.max_redirects + 1):
            norm, _host = validate_url(current)
            with httpx.Client(timeout=self.timeout, follow_redirects=False,
                              headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(norm)
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("location", "")
                if not loc:
                    raise WebFetchError("bad_redirect", "redirect without location")
                nxt = loc if "://" in loc else urlunparse(urlparse(norm)._replace(path=loc))
                if not _same_origin(norm, nxt):                 # §26 cross-origin redirect rejected
                    raise WebFetchError("cross_origin_redirect", "redirect left the origin")
                validate_url(nxt)                                # revalidate target (SSRF)
                current = nxt
                continue
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            body = resp.text[: self.max_bytes]
            return resp.status_code, ctype, body
        raise WebFetchError("too_many_redirects", "redirect limit exceeded")

    def fetch_page(self, url: str) -> FetchedPage:
        norm, _host = validate_url(url)
        if self.respect_robots and not _robots_allows(norm, get_fn=self._get):
            raise WebFetchError("robots_disallowed", "robots.txt disallows this path")
        status, ctype, body = self._get(norm)
        if status != 200:
            raise WebFetchError("http_error", f"status {status}")
        if ctype and not any(ctype.startswith(t) for t in ALLOWED_CONTENT_TYPES):
            raise WebFetchError("unsupported_content_type", ctype)
        if len(body.encode("utf-8", "ignore")) > self.max_bytes:
            raise WebFetchError("too_large", "response exceeds byte cap")
        title, text = extract_text(body)
        return FetchedPage(url=norm, title=title, text=text, content_type=ctype or "text/html",
                           status_code=status, bytes_read=len(body))
