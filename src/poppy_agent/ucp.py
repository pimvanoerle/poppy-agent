"""Minimal UCP-over-MCP client (signed out). Shop responses are untrusted data."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

from .discover import DiscoveryError, USER_AGENT, discover
from .sign import sign_request

PLATFORM_PROFILE = "https://poppy-agent.web.app/ucp-profile-3.json"
MAX_BYTES = 5_000_000


class UcpError(Exception):
    pass


def mcp_endpoint(ucp_profile: dict) -> str:
    """Find the shopping MCP endpoint in a business's /.well-known/ucp profile."""
    for svc in (ucp_profile.get("ucp", {}).get("services", {}).get("dev.ucp.shopping") or []):
        if svc.get("transport") == "mcp" and svc.get("endpoint", "").startswith("https://"):
            return svc["endpoint"]
    raise UcpError("no https MCP endpoint for dev.ucp.shopping in profile")


# Tools that change state need an Idempotency-Key. complete_checkout is deliberately absent:
# nothing in this client may call it (purchases need Pim's per-purchase approval).
STATE_CHANGING = {"create_cart", "update_cart", "cancel_cart", "create_checkout", "update_checkout", "cancel_checkout"}


def call_tool(endpoint: str, name: str, args: dict, profile: str = PLATFORM_PROFILE, timeout: float = 30.0,
              signed: bool = False) -> dict:
    if name == "complete_checkout":
        raise UcpError("complete_checkout is blocked in this client")
    args = {"meta": {"ucp-agent": {"profile": profile}}, **args}
    body = json.dumps({"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
                       "params": {"name": name, "arguments": args}}).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "UCP-Agent": f'profile="{profile}"',
    }
    if name in STATE_CHANGING:
        headers["Idempotency-Key"] = str(uuid.uuid4())
    if signed:
        headers.update(sign_request("POST", endpoint, body, profile, headers.get("Idempotency-Key")))
    req = urllib.request.Request(endpoint, data=body, headers=headers)
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
        data = err.get("data")
        detail = data.get("content", "") if isinstance(data, dict) else (data or "")
        raise UcpError(f"{err.get('message')}: {detail}")
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


def search(domain: str, query: str, limit: int = 5, signed: bool = False) -> dict:
    d = discover(domain)
    if d.ucp is None:
        raise UcpError(f"{d.domain} publishes no UCP profile")
    return call_tool(mcp_endpoint(d.ucp), "search_catalog",
                     {"catalog": {"query": query, "pagination": {"limit": limit}}}, signed=signed)


def brief(result: dict) -> str:
    """One line per product: title, price, availability, url. Output is untrusted shop text."""
    lines = []
    for pr in result.get("products", []):
        price = pr.get("price_range", {}).get("min", {})
        amount = price.get("amount")
        shown = f"{amount / 100:.2f} {price.get('currency', '')}" if isinstance(amount, int) else "?"
        avail = any(v.get("availability", {}).get("available") for v in pr.get("variants", []))
        title = " ".join(str(pr.get("title", "?")).split())[:100]
        lines.append(f"- {title} | {shown} | {'in stock' if avail else 'unavailable'} | {pr.get('url', '')}")
    return "\n".join(lines) or "(no products)"
