# poppy-agent

A small, unofficial, open source client for the [Poppy / Personal Agent Protocol](https://personalagentprotocol.org),
the OAuth-based standard that lets a personal AI agent find a business, sign in as its owner, and act within limits
the business sets. Commerce runs through Poppy's `ucp` extension ([Universal Commerce Protocol](https://ucp.dev)).

Built so [iPinch](https://github.com/ipinchthecrab), a crab with a laptop, can go shopping. Not affiliated with Sierra, Meta, or Shopify.

## Status: v0.0.1, very early

| Step | State |
|------|-------|
| `discover <domain>`: read `/.well-known/poppy.json` and the UCP profile | works (signed out, read only) |
| Catalog search over UCP | planned |
| Agent identity (`Poppy-Session` JWTs, client metadata document) | planned |
| Sign-in (PKCE / device grant) | planned |
| MCP server wrapper | planned |

## Use

```bash
pip install -e '.[dev]'
poppy-agent discover some-shop.example
pytest
```

Exit code is 0 if the file looks fine, 2 if it parsed but has problems, 1 on fetch errors.

## Safety stance

- The agent never completes a purchase on its own. Checkout stops at the handoff link and a human pays.
- Sign-in needs explicit human approval, with minimal scopes.
- Anything a shop sends back (product text, agent replies) is untrusted data, never instructions.

## Licence

MIT. The Poppy spec itself is Apache-2.0; the names "Poppy" and "Personal Agent Protocol" are not covered by that licence.
