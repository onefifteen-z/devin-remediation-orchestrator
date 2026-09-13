import hashlib
import hmac


def compute_github_signature(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_github_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret:
        return False
    if not signature.startswith("sha256="):
        return False
    expected = compute_github_signature(payload, secret)
    return hmac.compare_digest(expected, signature)
