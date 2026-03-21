#!/bin/bash
# Usage: ./test-api.sh <stack-name> <cognito-username> <cognito-password> [region]
# Example: ./test-api.sh demo-tg-sam-backend appuser@aws.local 'AppP@ssw0rd!' ap-southeast-1

set -e

STACK_NAME="${1:?Usage: $0 <stack-name> <region> <cognito-username> <cognito-password>}"
REGION="${2:?Missing region}"
USERNAME="${3:?Missing cognito-username}"
PASSWORD="${4:?Missing cognito-password}"

echo "Reading stack outputs from $STACK_NAME..."
API_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
CLIENT_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoAppClientId'].OutputValue" --output text)

echo "API URL:   $API_URL"
echo "Client ID: $CLIENT_ID"

echo ""
echo "Getting Cognito token..."
TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
  --region "$REGION" \
  --query 'AuthenticationResult.IdToken' --output text)

AUTH="Authorization: Bearer $TOKEN"
CT="Content-Type: application/json"
PASS=0
FAIL=0

check() {
  local test_name="$1" expected="$2" actual="$3"
  if echo "$actual" | grep -q "$expected"; then
    echo "  PASS: $test_name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $test_name (expected '$expected')"
    echo "  Response: $actual"
    FAIL=$((FAIL + 1))
  fi
}

echo ""
echo "=== 1. POST /items (Create) ==="
RES=$(curl -s -X POST "$API_URL/items" -H "$AUTH" -H "$CT" -d '{"name":"test item","description":"api test"}')
echo "$RES" | jq .
check "Create returns id" '"id"' "$RES"
ITEM_ID=$(echo "$RES" | jq -r '.id')

echo ""
echo "=== 2. GET /items (List) ==="
RES=$(curl -s "$API_URL/items" -H "$AUTH")
echo "$RES" | jq .
check "List returns array" '"name"' "$RES"

echo ""
echo "=== 3. GET /items/$ITEM_ID (Get by ID) ==="
RES=$(curl -s "$API_URL/items/$ITEM_ID" -H "$AUTH")
echo "$RES" | jq .
check "Get returns item" "\"id\": $ITEM_ID" "$RES"

echo ""
echo "=== 4. PUT /items/$ITEM_ID (Update) ==="
RES=$(curl -s -X PUT "$API_URL/items/$ITEM_ID" -H "$AUTH" -H "$CT" -d '{"name":"updated","description":"updated"}')
echo "$RES" | jq .
check "Update returns updated name" '"updated"' "$RES"

echo ""
echo "=== 5. DELETE /items/$ITEM_ID (Delete) ==="
RES=$(curl -s -X DELETE "$API_URL/items/$ITEM_ID" -H "$AUTH")
echo "$RES" | jq .
check "Delete confirms" "deleted" "$RES"

echo ""
echo "=== 6. GET /items/$ITEM_ID (Should be 404) ==="
RES=$(curl -s "$API_URL/items/$ITEM_ID" -H "$AUTH")
echo "$RES" | jq .
check "Get deleted item returns 404" "not found\|Not found" "$RES"

echo ""
echo "=== 7. No auth (Should be 401) ==="
RES=$(curl -s "$API_URL/items")
echo "$RES" | jq .
check "No auth returns Unauthorized" "Unauthorized" "$RES"

echo ""
echo "=== 8. Fake token (Should be denied) ==="
RES=$(curl -s "$API_URL/items" -H "Authorization: Bearer fake.token.here")
echo "$RES" | jq .
check "Fake token denied" "not authorized\|Unauthorized" "$RES"

echo ""
echo "=== 9. CORS preflight (Should return CORS headers) ==="
RES=$(curl -s -X OPTIONS "$API_URL/items" -H "Origin: https://example.com" -H "Access-Control-Request-Method: POST" -D /tmp/cors_headers -o /dev/null && cat /tmp/cors_headers)
echo "$RES"
check "Preflight returns Allow-Origin" "access-control-allow-origin" "$RES"

echo ""
echo "=== 10. CORS on GET response (Should return CORS headers) ==="
RES=$(curl -s "$API_URL/items" -H "$AUTH" -H "Origin: https://example.com" -D /tmp/cors_get_headers -o /dev/null && cat /tmp/cors_get_headers)
echo "$RES"
check "GET response returns Allow-Origin" "access-control-allow-origin" "$RES"

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed"
echo "================================"
exit $FAIL
