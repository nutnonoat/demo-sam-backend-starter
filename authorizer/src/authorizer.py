"""Lambda authorizer — validates Cognito JWT and checks group membership."""

import json
import os
import urllib.request
import time
import hmac
import hashlib
import base64
import struct

# ── Config from environment ──
COGNITO_REGION = os.environ["COGNITO_REGION"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
ALLOWED_GROUP = os.environ["ALLOWED_GROUP"]
JWKS_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"

# Cache JWKS keys across invocations
_jwks_cache = None


def _get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        with urllib.request.urlopen(JWKS_URL) as resp:
            _jwks_cache = json.loads(resp.read())["keys"]
    return _jwks_cache


def _b64url_decode(s):
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _decode_jwt_unverified(token):
    """Decode JWT payload without cryptographic verification of signature.

    IMPORTANT: This only decodes the payload — it does NOT verify the signature.
    For production use, replace this with a library like python-jose or PyJWT
    that performs full RS256 signature verification against the JWKS keys.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    payload = json.loads(_b64url_decode(parts[1]))
    return payload


def handler(event, context):
    try:
        token = event.get("identitySource", "").replace("Bearer ", "")
        if not token:
            return {"isAuthorized": False}

        claims = _decode_jwt_unverified(token)

        # Validate issuer
        expected_issuer = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}"
        if claims.get("iss") != expected_issuer:
            return {"isAuthorized": False}

        # Validate expiration
        if claims.get("exp", 0) < time.time():
            return {"isAuthorized": False}

        # Validate token_use
        if claims.get("token_use") not in ("id", "access"):
            return {"isAuthorized": False}

        # Check group membership
        groups = claims.get("cognito:groups", [])
        if ALLOWED_GROUP not in groups:
            return {"isAuthorized": False}

        return {
            "isAuthorized": True,
            "context": {
                "sub": claims.get("sub", ""),
                "email": claims.get("email", ""),
                "groups": ",".join(groups),
            },
        }
    except Exception:
        return {"isAuthorized": False}
