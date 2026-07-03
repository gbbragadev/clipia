"""Upload de um arquivo para Cloudflare R2 (API S3-compatible) via SigV4.

Sem dependencias externas (apenas stdlib). Chamado por backup-postgres.ps1.

Env vars (User scope ou herdadas):
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET

Uso: python upload_r2.py <arquivo_local> <object_key>
Retorna: exit 0 + "OK <url>" | exit 1 + mensagem de erro.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import sys
import urllib.error
import urllib.request


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _sign(key: bytes, msg: str) -> str:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def upload(file_path: str, object_key: str) -> str:
    account_id = os.environ.get("R2_ACCOUNT_ID", "")
    access_key_id = os.environ.get("R2_ACCESS_KEY_ID", "")
    secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    bucket = os.environ.get("R2_BUCKET", "")
    missing = [
        k
        for k, v in {
            "R2_ACCOUNT_ID": account_id,
            "R2_ACCESS_KEY_ID": access_key_id,
            "R2_SECRET_ACCESS_KEY": secret_access_key,
            "R2_BUCKET": bucket,
        }.items()
        if not v
    ]
    if missing:
        raise RuntimeError(f"Env vars ausentes: {', '.join(missing)}")

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    host = f"{account_id}.r2.cloudflarestorage.com"
    url = f"{endpoint}/{bucket}/{object_key}"

    with open(file_path, "rb") as f:
        body = f.read()
    payload_hash = _sha256_hex(body)

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    region = "auto"
    service = "s3"

    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = f"PUT\n/{bucket}/{object_key}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n{_sha256_hex(canonical_request.encode())}"

    k_date = _hmac(("AWS4" + secret_access_key).encode(), datestamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    k_signing = _hmac(k_service, "aws4_request")
    signature = _sign(k_signing, string_to_sign)

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    req = urllib.request.Request(
        url,
        method="PUT",
        data=body,
        headers={
            "Authorization": authorization,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return f"OK {resp.status} {url}"
    except urllib.error.HTTPError as e:
        detail = e.read()[:500].decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {detail}") from None


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python upload_r2.py <arquivo> <object_key>", file=sys.stderr)
        sys.exit(2)
    try:
        msg = upload(sys.argv[1], sys.argv[2])
        print(msg)
    except Exception as e:  # noqa: BLE001 - mensagem pro caller
        print(f"FAIL {e}", file=sys.stderr)
        sys.exit(1)
