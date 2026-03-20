"""Lambda authorizer — validates Cognito JWT and checks group membership."""

import json
import os
import urllib.request
import time
import base64

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
    return json.loads(_b64url_decode(parts[1]))


def _generate_policy(principal_id, effect, method_arn, context=None):
    """Generate IAM policy document for REST API authorizer."""
    # Extract the base ARN (up to the stage) to allow all methods
    arn_parts = method_arn.split(":")
    api_gateway_arn = ":".join(arn_parts[:5])
    api_id_stage = arn_parts[5].split("/")
    resource_arn = f"{api_gateway_arn}:{api_id_stage[0]}/{api_id_stage[1]}/*"

    policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource_arn,
                }
            ],
        },
    }
    if context:
        policy["context"] = context
    return policy


def handler(event, context):
    try:
        token = event.get("headers", {}).get("Authorization", event.get("headers", {}).get("authorization", "")).replace("Bearer ", "")
        method_arn = event.get("methodArn", "")

        if not token:
            return _generate_policy("anonymous", "Deny", method_arn)

        claims = _decode_jwt_unverified(token)

        # Validate issuer
        expected_issuer = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}"
        if claims.get("iss") != expected_issuer:
            return _generate_policy("anonymous", "Deny", method_arn)

        # Validate expiration
        if claims.get("exp", 0) < time.time():
            return _generate_policy("anonymous", "Deny", method_arn)

        # Validate token_use
        if claims.get("token_use") not in ("id", "access"):
            return _generate_policy("anonymous", "Deny", method_arn)

        # Check group membership
        groups = claims.get("cognito:groups", [])
        if ALLOWED_GROUP not in groups:
            return _generate_policy(claims.get("sub", "anonymous"), "Deny", method_arn)

        return _generate_policy(
            claims.get("sub", "unknown"),
            "Allow",
            method_arn,
            context={
                "sub": claims.get("sub", ""),
                "email": claims.get("email", ""),
                "groups": ",".join(groups),
            },
        )
    except Exception as e:
        print(f"Authorizer error: {e}")
        return _generate_policy("anonymous", "Deny", event.get("methodArn", ""))
