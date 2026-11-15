import base64
import subprocess

import pytest

from poppy_agent.sign import _der_to_raw, content_digest, sign_request


@pytest.fixture()
def key(tmp_path):
    k = tmp_path / "k.pem"
    subprocess.run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(k)], check=True,
                   capture_output=True)
    return k


def test_digest():
    assert content_digest(b"") == "sha-256=:47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=:"


def test_signature_verifies(key, tmp_path):
    body = b'{"a":1}'
    h = sign_request("POST", "https://Shop.example/api/ucp/mcp", body, "https://p.example/u.json", "idem-1",
                     key_path=str(key), kid="k1")
    assert h["Signature-Input"] == ('sig1=("@method" "@authority" "@path" "ucp-agent" "idempotency-key" '
                                    '"content-digest" "content-type");keyid="k1"')
    raw = base64.b64decode(h["Signature"][len("sig1=:"):-1])
    assert len(raw) == 64
    r, s = raw[:32], raw[32:]

    def der_int(b):
        b = b.lstrip(b"\0") or b"\0"
        if b[0] & 0x80:
            b = b"\0" + b
        return b"\x02" + bytes([len(b)]) + b
    seq = der_int(r) + der_int(s)
    der = b"\x30" + bytes([len(seq)]) + seq
    base = ('"@method": POST\n"@authority": shop.example\n"@path": /api/ucp/mcp\n'
            '"ucp-agent": profile="https://p.example/u.json"\n"idempotency-key": idem-1\n'
            f'"content-digest": {h["Content-Digest"]}\n"content-type": application/json\n'
            f'"@signature-params": {h["Signature-Input"][5:]}')
    (tmp_path / "pub.pem").write_bytes(subprocess.run(["openssl", "ec", "-in", str(key), "-pubout"], check=True,
                                                     capture_output=True).stdout)
    (tmp_path / "sig").write_bytes(der)
    (tmp_path / "msg").write_bytes(base.encode())
    p = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(tmp_path / "pub.pem"), "-signature",
                        str(tmp_path / "sig"), str(tmp_path / "msg")], capture_output=True)
    assert p.returncode == 0, p.stdout


def test_der_roundtrip_short_ints():
    der = bytes([0x30, 6, 2, 1, 5, 2, 1, 7])
    assert _der_to_raw(der) == (5).to_bytes(32, "big") + (7).to_bytes(32, "big")
