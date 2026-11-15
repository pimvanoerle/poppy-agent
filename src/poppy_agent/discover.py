"""Signed-out discovery: what does a business publish for agents?

Fetches /.well-known/poppy.json (and, if advertised, the UCP commerce profile)
and summarises it. No authentication, nothing is changed on the business side.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

USER_AGENT = "poppy-agent/0.0.1 (+https://github.com/pimvanoerle/poppy-agent)"
MAX_BYTES = 1_000_000
_DOMAIN_RE = re.compile(r"^[A-Za-z0-9.-]+(:\d+)?$")


class DiscoveryError(Exception):
    pass


@dataclass
class Discovery:
    domain: str
    poppy: dict
    problems: list[str] = field(default_factory=list)
    ucp: dict | None = None

    @property
    def has_commerce(self) -> bool:
        return "ucp" in (self.poppy.get("extensions") or {})

    def summary(self) -> str:
        org = self.poppy.get("organization", {})
        lines = [
            f"{org.get('name', '?')} ({self.domain})",
            f"  protocol_version: {self.poppy.get('protocol_version', '?')}",
        ]
        for api in self.poppy.get("apis", []) or []:
            lines.append(f"  api [{api.get('type')}]: {api.get('url')}")
        for proto in (self.poppy.get("agent") or {}).get("protocols", []) or []:
            lines.append(f"  agent protocol [{proto.get('type')}]: {proto.get('endpoint')}")
        scopes = (self.poppy.get("auth") or {}).get("scopes") or {}
        if scopes:
            lines.append("  scopes: " + ", ".join(scopes))
        exts = self.poppy.get("extensions") or {}
        if exts:
            lines.append("  extensions: " + ", ".join(exts))
        if self.ucp is not None:
            lines.append("  ucp profile: found")
        for p in self.problems:
            lines.append(f"  ! {p}")
        return "\n".join(lines)


def normalise_domain(value: str) -> str:
    """Accept 'example.com' or 'https://example.com/anything'; return the host."""
    value = value.strip()
    if "://" in value:
        value = urlparse(value).netloc
    if not _DOMAIN_RE.match(value):
        raise DiscoveryError(f"not a valid domain: {value!r}")
    return value.lower()


def _get_json(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = urlparse(resp.geturl())
            body = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise DiscoveryError(f"{url}: HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise DiscoveryError(f"{url}: {e}") from e
    if len(body) > MAX_BYTES:
        raise DiscoveryError(f"{url}: response too large")
    # Spec: redirects are followed only if they end at the same well-known path, no query.
    if final.path != urlparse(url).path or final.query:
        raise DiscoveryError(f"{url}: redirected to {final.path}?{final.query}, not allowed")
    try:
        data = json.loads(body)
    except ValueError as e:
        raise DiscoveryError(f"{url}: not JSON") from e
    if not isinstance(data, dict):
        raise DiscoveryError(f"{url}: expected a JSON object")
    return data


def check(poppy: dict, domain: str) -> list[str]:
    """Light structural checks from the 1.0 spec. Not a full validator."""
    problems = []
    if "protocol_version" not in poppy:
        problems.append("missing required field: protocol_version")
    org = poppy.get("organization")
    if not isinstance(org, dict):
        problems.append("missing required field: organization")
    elif org.get("domain") and org["domain"].lower() != domain.split(":")[0]:
        problems.append(f"organization.domain {org['domain']!r} does not match host {domain!r}")
    if not any(poppy.get(k) for k in ("agent", "apis", "web")):
        problems.append("needs at least one of: agent, apis, web")
    return problems


def discover(domain: str, fetch=_get_json) -> Discovery:
    domain = normalise_domain(domain)
    poppy = fetch(f"https://{domain}/.well-known/poppy.json")
    d = Discovery(domain=domain, poppy=poppy, problems=check(poppy, domain))
    if d.has_commerce:
        try:
            d.ucp = fetch(f"https://{domain}/.well-known/ucp")
        except DiscoveryError as e:
            d.problems.append(f"advertises ucp but profile failed: {e}")
    return d
