"""Offline structure checks. Never resolve DNS or retrieve a submitted URL."""
import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit

import idna
import tldextract

from .errors import SinyaraError
from .schemas import Check, Evidence

# Use the packaged PSL snapshot. Disable both network refresh and cache writes.
extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
SHORTENERS = {"bit.ly", "s.id", "tinyurl.com", "t.co", "shorturl.at", "cutt.ly"}


def parse_url(raw: str) -> dict:
    if re.search(r"[\x00-\x20\x7f\\]", raw):
        raise SinyaraError("invalid_input", "Tautan mengandung spasi atau karakter yang tidak valid.")
    try:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError()
        _ = parsed.port
        hostname = parsed.hostname.rstrip(".")
        try:
            ipaddress.ip_address(hostname)
            host, domain = hostname, hostname
        except ValueError:
            host = idna.encode(hostname, uts46=True).decode("ascii").lower()
            parts = extract(host)
            if not parts.suffix or not parts.domain:
                raise ValueError()
            domain = parts.top_domain_under_public_suffix
        unicode_host = idna.decode(host) if not ":" in host else host
    except (ValueError, idna.IDNAError) as exc:
        raise SinyaraError("invalid_input", "Masukkan tautan HTTP atau HTTPS dengan domain yang valid.") from exc
    return {"raw": raw, "host": host, "domain": domain, "unicode_host": unicode_host,
            "scheme": parsed.scheme.lower(), "userinfo": parsed.username is not None,
            "subdomain": host[:-len(domain)].rstrip(".") if host != domain else ""}


def inspect_urls(urls: list[str]) -> tuple[list[Evidence], list[Check]]:
    evidence, checks = [], []
    for i, raw in enumerate(urls):
        parsed = parse_url(raw)
        prefix = f"url-{i + 1}"
        facts = [("structure", f"Domain utama: {parsed['domain']}. Host lengkap: {parsed['host']}. Alamat belum dibuka.")]
        if parsed["userinfo"]:
            facts.append(("url_warning", "Ada bagian nama pengguna sebelum @. Domain tujuan adalah yang terletak setelah @."))
        if parsed["domain"] in SHORTENERS:
            facts.append(("url_unknown", "Tautan pendek belum diperluas. Tujuan akhirnya belum diketahui."))
        if "xn--" in parsed["host"]:
            facts.append(("url_warning", "Domain menggunakan IDN/punycode. Periksa ejaan Unicode; ini bukan bukti penipuan dengan sendirinya."))
        scripts = {unicodedata.name(c, "").split(" ")[0] for c in parsed["unicode_host"] if c.isalpha()}
        if len(scripts & {"LATIN", "CYRILLIC", "GREEK"}) > 1:
            facts.append(("url_warning", "Domain mencampur alfabet yang dapat terlihat mirip."))
        if parsed["subdomain"].count(".") >= 2:
            facts.append(("url_warning", "Subdomain bertingkat panjang. Identitas situs tetap ditentukan domain utamanya."))
        if parsed["scheme"] == "http":
            facts.append(("url_warning", "Tautan memakai HTTP tanpa enkripsi transport. HTTPS pun tidak menjamin situs sah."))
        try:
            ipaddress.ip_address(parsed["host"])
            facts.append(("url_warning", "Tujuan berupa alamat IP, bukan nama domain organisasi."))
        except ValueError:
            pass
        for j, (indicator, explanation) in enumerate(facts):
            evidence.append(Evidence(id=f"{prefix}-{j + 1}", source="url", quote=raw,
                                     indicator=indicator, explanation=explanation))
        checks.append(Check(key=prefix, title=f"Struktur tautan {i + 1}", status="done", detail=f"Domain utama: {parsed['domain']}. Tidak ada halaman yang dibuka."))
    checks.append(Check(key="reputation", title="Reputasi tautan", status="unavailable" if urls else "skipped",
                        detail="Sumber reputasi belum dihubungkan; status situs belum dapat dipastikan." if urls else "Tidak ada tautan yang diberikan."))
    return evidence, checks
