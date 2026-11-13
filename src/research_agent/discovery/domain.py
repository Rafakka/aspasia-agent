
from dataclasses import dataclass
import ipaddress
from urllib.parse import urlsplit

import tldextract

@dataclass(frozen=True)
class SourceDomain:
    hostname: str
    registered_domain: str
    subdomain: str
    suffix: str


_EXTRACTOR = tldextract.TLDExtract(
    suffix_list_urls=(),
    include_psl_private_domains=True,
)


def extract_source_domain(url: str) -> SourceDomain:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string.")

    try:
        parsed = urlsplit(url.strip())

        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS URLs are supported.")

        if not parsed.hostname:
            raise ValueError("URL must contain a hostname.")

        if parsed.username or parsed.password:
            raise ValueError("URL credentials are not supported.")

        hostname = parsed.hostname.encode("idna").decode("ascii").lower()

        # Validate port syntax and range.
        _ = parsed.port

    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"Invalid source URL: {exc}") from exc

    if hostname.startswith("www."):
        hostname = hostname[4:]

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses are not supported.")

    extracted = _EXTRACTOR(hostname)

    if not extracted.domain or not extracted.suffix:
        raise ValueError(f"Could not identify domain: {hostname}")

    return SourceDomain(
        hostname=hostname,
        registered_domain=extracted.top_domain_under_public_suffix,
        subdomain=extracted.subdomain,
        suffix=extracted.suffix,
    )
