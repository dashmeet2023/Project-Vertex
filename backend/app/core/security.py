"""
Cryptographic utilities for Project Vertex's opaque reference tokens.

Token structure (opaque to the client):
    raw_token = base64url( kid + "." + random_bytes(32) )

Storage:
    The raw_token is NEVER stored.  We store:
        HMAC-SHA256( secret_for_kid, raw_token ) → token_hash

Verification algorithm:
    1. Decode kid prefix from raw_token bytes.
    2. Look up the secret for that kid in the signing keys map.
    3. Recompute HMAC and compare (constant-time).
    4. Look up the token_hash in reference_tokens table.
    5. Check expiry (expires_at > now()).
    6. Check single-use (used_at IS NULL).

Key rotation:
    Add a new entry to TOKEN_SIGNING_KEYS and update TOKEN_ACTIVE_KID.
    Old tokens with a previous kid continue to verify with their original secret.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re

from app.core.config import get_settings


_KID_SEPARATOR = b"."
_RANDOM_BYTES = 32


def _get_secret(kid: str) -> bytes:
    keys = get_settings().signing_keys
    if kid not in keys:
        raise KeyError(f"Unknown signing key id: {kid!r}")
    return keys[kid].encode()


def issue_raw_token() -> tuple[str, str, str]:
    """
    Generate a new opaque reference token.

    Returns:
        (raw_token, kid, token_hash)
        - raw_token  : the string given to the client (opaque)
        - kid        : the signing key id used
        - token_hash : HMAC digest to store in the DB
    """
    settings = get_settings()
    kid = settings.TOKEN_ACTIVE_KID
    secret = _get_secret(kid)

    payload = kid.encode() + _KID_SEPARATOR + os.urandom(_RANDOM_BYTES)
    raw_token = base64.urlsafe_b64encode(payload).decode()

    token_hash = hmac.new(secret, raw_token.encode(), hashlib.sha256).hexdigest()

    return raw_token, kid, token_hash


def compute_token_hash(raw_token: str) -> tuple[str, str]:
    """
    Given a client-supplied raw_token, extract the kid and compute its hash.

    Returns:
        (kid, token_hash)

    Raises:
        ValueError if the token is malformed or uses an unknown kid.
    """
    try:
        payload = base64.urlsafe_b64decode(raw_token.encode() + b"==")
    except Exception as exc:
        raise ValueError("Malformed token: base64 decode failed") from exc

    if _KID_SEPARATOR not in payload:
        raise ValueError("Malformed token: missing kid separator")

    kid_bytes, _ = payload.split(_KID_SEPARATOR, 1)
    kid = kid_bytes.decode()

    try:
        secret = _get_secret(kid)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc

    token_hash = hmac.new(secret, raw_token.encode(), hashlib.sha256).hexdigest()
    return kid, token_hash


def verify_token_signature(raw_token: str, expected_hash: str) -> bool:
    """
    Constant-time comparison of the recomputed HMAC against the stored hash.
    Returns True iff the signature is valid.
    """
    try:
        _, computed_hash = compute_token_hash(raw_token)
    except ValueError:
        return False
    return hmac.compare_digest(computed_hash, expected_hash)
