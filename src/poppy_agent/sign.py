"""RFC 9421 HTTP Message Signatures for UCP requests (ES256, stdlib + the openssl CLI).

Spec: https://ucp.dev/2026-08-25/specification/signatures/
The private key never leaves the key file; openssl reads it for each signature.
"""
from __future__ import annotations

import base64
import hashlib
import os
import subprocess
from urllib.parse import urlsplit

DEFAULT_KEY = os.path.expanduser("~/.poppy-agent/client_key.pem")
DEFAULT_KID = "FFVd4jp5H22H3Z4YeXDn8oMrJsl1CFLzm4fcmqarkA4"  # matches keys[] in our UCP profile


class SignError(Exception):
    pass


def _der_to_raw(der: bytes, size: int = 32) -> bytes:
    """ASN.1 DER ECDSA signature -> fixed-width r||s (RFC 9421 section 3.3.1)."""
    try:
        if der[0] != 0x30:
            raise ValueError
        i = 2 if der[1] < 0x80 else 2 + (der[1] & 0x7F)
        parts = []
        for _ in range(2):
            if der[i] != 0x02:
                raise ValueError
            n = der[i + 1]
            parts.append(int.from_bytes(der[i + 2:i + 2 + n], "big"))
            i += 2 + n
        return b"".join(p.to_bytes(size, "big") for p in parts)
    except (ValueError, IndexError, OverflowError) as e:
        raise SignError("could not parse ECDSA signature from openssl") from e


def _es256(message: bytes, key_path: str) -> bytes:
    p = subprocess.run(["openssl", "dgst", "-sha256", "-sign", key_path], input=message,
                       capture_output=True, timeout=10)
    if p.returncode != 0:
        raise SignError("openssl signing failed")
    return _der_to_raw(p.stdout)


def content_digest(body: bytes) -> str:
    return "sha-256=:" + base64.b64encode(hashlib.sha256(body).digest()).decode() + ":"


def sign_request(method: str, url: str, body: bytes | None, profile: str | None,
                 idempotency_key: str | None, key_path: str = DEFAULT_KEY,
                 kid: str = DEFAULT_KID) -> dict[str, str]:
    """Return the headers to add: Content-Digest, Signature-Input, Signature (+ Idempotency-Key is the caller's)."""
    u = urlsplit(url)
    headers: dict[str, str] = {}
    comps: list[tuple[str, str]] = [("@method", method.upper()), ("@authority", u.netloc.lower()),
                                    ("@path", u.path or "/")]
    if u.query:
        comps.append(("@query", "?" + u.query))
    if profile:
        comps.append(("ucp-agent", f'profile="{profile}"'))
    if idempotency_key:
        comps.append(("idempotency-key", idempotency_key))
    if body:
        headers["Content-Digest"] = content_digest(body)
        comps.append(("content-digest", headers["Content-Digest"]))
        comps.append(("content-type", "application/json"))
    params = "(" + " ".join(f'"{n}"' for n, _ in comps) + f');keyid="{kid}"'
    base = "\n".join(f'"{n}": {v}' for n, v in comps) + f'\n"@signature-params": {params}'
    sig = _es256(base.encode(), key_path)
    headers["Signature-Input"] = f"sig1={params}"
    headers["Signature"] = "sig1=:" + base64.b64encode(sig).decode() + ":"
    return headers
