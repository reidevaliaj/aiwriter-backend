"""
Security utilities for HMAC signing and validation.
"""
import hmac
import hashlib
from typing import Dict, Any


def create_hmac_signature(data: str, secret: str) -> str:
    """Create HMAC signature for data."""
    return hmac.new(
        secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verify_hmac_signature(data: str, signature: str, secret: str) -> bool:
    """Verify HMAC signature."""
    expected_signature = create_hmac_signature(data, secret)
    return hmac.compare_digest(signature, expected_signature)


def sign_payload(payload: Dict[str, Any], secret: str) -> Dict[str, Any]:
    """Sign a payload with HMAC."""
    import json
    payload_str = json.dumps(payload, sort_keys=True)
    signature = create_hmac_signature(payload_str, secret)
    return {
        "payload": payload,
        "signature": signature
    }
