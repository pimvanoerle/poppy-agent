import pytest

from poppy_agent.discover import DiscoveryError, check, discover, normalise_domain

GOOD = {
    "protocol_version": "1.0",
    "organization": {"name": "Kettle & Leaf", "domain": "kettle.example"},
    "apis": [{"type": "mcp", "url": "https://kettle.example/mcp"}],
    "auth": {"scopes": {"orders:read": {}}},
    "extensions": {"ucp": [{"version": "1"}]},
}


def test_normalise():
    assert normalise_domain("https://Kettle.example/shop?x=1") == "kettle.example"
    with pytest.raises(DiscoveryError):
        normalise_domain("not a domain")


def test_check_good_and_bad():
    assert check(GOOD, "kettle.example") == []
    bad = {"organization": {"domain": "evil.example"}}
    problems = check(bad, "kettle.example")
    assert len(problems) == 3


def test_discover_follows_ucp():
    calls = []

    def fake(url):
        calls.append(url)
        return GOOD if url.endswith("poppy.json") else {"ucp": True}

    d = discover("kettle.example", fetch=fake)
    assert d.has_commerce and d.ucp == {"ucp": True}
    assert calls[1].endswith("/.well-known/ucp")
    assert "mcp" in d.summary()


def test_missing_ucp_is_reported():
    def fake(url):
        if url.endswith("poppy.json"):
            return GOOD
        raise DiscoveryError("nope")

    assert any("ucp" in p for p in discover("kettle.example", fetch=fake).problems)


def test_brief_formats_prices():
    from poppy_agent.ucp import brief

    r = {"products": [{"title": "Sock\n Pair", "url": "https://x.example/p", "price_range": {"min": {"amount": 1400, "currency": "USD"}},
                       "variants": [{"availability": {"available": True}}]}]}
    assert brief(r) == "- Sock Pair | 14.00 USD | in stock | https://x.example/p"
    assert brief({}) == "(no products)"


def test_mcp_handshake_and_unknown_tool():
    from poppy_agent.mcp_server import handle

    assert handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})["result"]["serverInfo"]["name"] == "poppy-agent"
    names = [t["name"] for t in handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
    assert "poppy_search" in names and not any("checkout" in n or "buy" in n for n in names)
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert "error" in handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nope"}})
