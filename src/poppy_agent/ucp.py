"""Minimal UCP-over-MCP client (signed out). Shop responses are untrusted data."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

from .discover import DiscoveryError, USER_AGENT, discover

PLATFORM_PROFILE = "https://pimvanoerle.github.io/poppy-agent/ucp-profile.json"
MAX_BYTES = 5_000_000


class UcpError(Exception):
    pass


def mcp_endpoint(ucp_profile: dict) -> str:
    """Find the shopping MCP endpoint in a business's /.well-known/ucp profile."""
    for svc in (ucp_profile.get("ucp", {}).get("services", {}).get("dev.ucp.shopping") or []):
        if svc.get("transport") == "mcp" and svc.get("endpoint", "").startswith("https://"):
            return svc["endpoint"]
    raise UcpError("no https MCP endpoint for dev.ucp.shopping in profile")


def call_tool(endpoint: str, name: str, args: dict, profile: str = PLATFORM_PROFILE, timeout: float = 30.0) -> dict:
    args = {"meta": {"ucp-agent": {"profile": profile}}, **args}
    body = json.dumps({"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
                       "params": {"name": name, "arguments": args}}).encode()
    req = urllib.request.Request(endpoint, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "UCP-Agent": f'profile="{profile}"',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raw = e.read(MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError) as e:
        raise UcpError(f"{endpoint}: {e}") from e
    try:
        msg = json.loads(raw)
    except ValueError as e:
        raise UcpError("response was not JSON") from e
    if "error" in msg:
        err = msg["error"]
        raise UcpError(f"{err.get('message')}: {(err.get('data') or {}).get('content', '')}")
    result = msg.get("result", {})
    if "structuredContent" in result:
        return result["structuredContent"]
    for part in result.get("content", []):
        if part.get("type") == "text":
            try:
                return json.loads(part["text"])
            except ValueError:
                return {"text": part["text"]}
    return result


def search(domain: str, query: str, limit: int = 5) -> dict:
    d = discover(domain)
    if d.ucp is None:
        raise UcpError(f"{d.domain} publishes no UCP profile")
    return call_tool(mcp_endpoint(d.ucp), "search_catalog",
                     {"catalog": {"query": query, "pagination": {"limit": limit}}})
