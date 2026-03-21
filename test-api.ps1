# Usage: .\test-api.ps1 <stack-name> <region> <cognito-username> <cognito-password>
param(
    [Parameter(Mandatory)][string]$StackName,
    [Parameter(Mandatory)][string]$Region,
    [Parameter(Mandatory)][string]$Username,
    [Parameter(Mandatory)][string]$Password
)

$ErrorActionPreference = "Stop"

Write-Host "Reading stack outputs from $StackName..."
$ApiUrl = aws cloudformation describe-stacks --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text
$ClientId = aws cloudformation describe-stacks --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='CognitoAppClientId'].OutputValue" --output text

Write-Host "API URL:   $ApiUrl"
Write-Host "Client ID: $ClientId"

Write-Host "`nGetting Cognito token..."
$Token = aws cognito-idp initiate-auth `
    --client-id $ClientId `
    --auth-flow USER_PASSWORD_AUTH `
    --auth-parameters "USERNAME=$Username,PASSWORD=$Password" `
    --region $Region `
    --query 'AuthenticationResult.IdToken' --output text

$Headers = @{ "Authorization" = "Bearer $Token"; "Content-Type" = "application/json" }
$AuthOnly = @{ "Authorization" = "Bearer $Token" }
$Pass = 0; $Fail = 0

function Check($Name, $Expected, $Actual) {
    if ($Actual -match $Expected) {
        Write-Host "  PASS: $Name" -ForegroundColor Green
        $script:Pass++
    } else {
        Write-Host "  FAIL: $Name (expected '$Expected')" -ForegroundColor Red
        Write-Host "  Response: $Actual"
        $script:Fail++
    }
}

Write-Host "`n=== 1. POST /items (Create) ==="
$Res = Invoke-RestMethod -Uri "$ApiUrl/items" -Method POST -Headers $Headers -Body '{"name":"test item","description":"api test"}'
$Res | ConvertTo-Json
$ItemId = $Res.id
Check "Create returns id" "id" ($Res | ConvertTo-Json)

Write-Host "`n=== 2. GET /items (List) ==="
$Res = Invoke-RestMethod -Uri "$ApiUrl/items" -Headers $AuthOnly
$Res | ConvertTo-Json
Check "List returns array" "name" ($Res | ConvertTo-Json)

Write-Host "`n=== 3. GET /items/$ItemId (Get by ID) ==="
$Res = Invoke-RestMethod -Uri "$ApiUrl/items/$ItemId" -Headers $AuthOnly
$Res | ConvertTo-Json
Check "Get returns item" "$ItemId" ($Res | ConvertTo-Json)

Write-Host "`n=== 4. PUT /items/$ItemId (Update) ==="
$Res = Invoke-RestMethod -Uri "$ApiUrl/items/$ItemId" -Method PUT -Headers $Headers -Body '{"name":"updated","description":"updated"}'
$Res | ConvertTo-Json
Check "Update returns updated name" "updated" ($Res | ConvertTo-Json)

Write-Host "`n=== 5. DELETE /items/$ItemId (Delete) ==="
$Res = Invoke-RestMethod -Uri "$ApiUrl/items/$ItemId" -Method DELETE -Headers $AuthOnly
$Res | ConvertTo-Json
Check "Delete confirms" "deleted" ($Res | ConvertTo-Json)

Write-Host "`n=== 6. GET /items/$ItemId (Should be 404) ==="
try { $Res = Invoke-RestMethod -Uri "$ApiUrl/items/$ItemId" -Headers $AuthOnly } catch { $Res = $_.ErrorDetails.Message }
$Res
Check "Get deleted item returns 404" "not found|Not found" $Res

Write-Host "`n=== 7. No auth (Should be 401) ==="
try { $Res = Invoke-RestMethod -Uri "$ApiUrl/items" } catch { $Res = $_.ErrorDetails.Message }
$Res
Check "No auth returns Unauthorized" "Unauthorized" $Res

Write-Host "`n=== 8. Fake token (Should be denied) ==="
try { $Res = Invoke-RestMethod -Uri "$ApiUrl/items" -Headers @{ "Authorization" = "Bearer fake.token.here" } } catch { $Res = $_.ErrorDetails.Message }
$Res
Check "Fake token denied" "not authorized|Unauthorized" $Res

Write-Host "`n================================"
Write-Host "Results: $Pass passed, $Fail failed"
Write-Host "================================"
exit $Fail
