"""Lambda authorizer — validates Cognito JWT and checks group membership."""

import json
import os
import urllib.request
import time

from jose import jwt, jwk, JWTError

# ── Config from environment ──
COGNITO_REGION = os.environ["COGNITO_REGION"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
ALLOWED_GROUP = os.environ["ALLOWED_GROUP"]
JWKS_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}"

# Cache JWKS keys across invocations
_jwks_cache = None


def _get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        with urllib.request.urlopen(JWKS_URL) as resp:
            _jwks_cache = json.loads(resp.read())["keys"]
    return _jwks_cache


def _generate_policy(principal_id, effect, method_arn, context=None):
    """Generate IAM policy document for REST API authorizer."""
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
        headers = event.get("headers", {})
        token = headers.get("Authorization", headers.get("authorization", "")).replace("Bearer ", "")
        method_arn = event.get("methodArn", "")

        if not token:
            return _generate_policy("anonymous", "Deny", method_arn)

        # Verify JWT signature and decode claims
        jwks = _get_jwks()
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=None,
            issuer=ISSUER,
            options={"verify_aud": False},
        )

        # Validate token_use
        if claims.get("token_use") != "id":
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
    except JWTError as e:
        print(f"JWT verification failed: {e}")
        return _generate_policy("anonymous", "Deny", event.get("methodArn", ""))
    except Exception as e:
        print(f"Authorizer error: {e}")
        return _generate_policy("anonymous", "Deny", event.get("methodArn", ""))
