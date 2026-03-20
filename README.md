# demo-sam-backend-starter

A SAM-based backend starter kit for teams modernizing to serverless on AWS.

## Architecture

```
Client → API Gateway (HTTP API) → Lambda (Python 3.12) → RDS PostgreSQL (via RDS Proxy)
              ↓
       Lambda Authorizer → validates Cognito JWT + group membership
```

## What's included

| Component | Description |
|---|---|
| API Gateway (HTTP API) | Routes with CORS, per-app |
| Backend Lambda | CRUDQ API for `items` table in RDS PostgreSQL |
| Authorizer Lambda | Validates Cognito JWT and checks group membership |
| Cognito App Client | Per-app client in centralized User Pool |
| Lambda Security Group | App-owned SG in provided VPC |

## Prerequisites (infra team provides)

- VPC with private subnets
- RDS Proxy + RDS PostgreSQL
- Secrets Manager secret with DB credentials and proxy endpoint (standard RDS format: `host`, `port`, `username`, `password`, `dbname`)
- VPC endpoints: Secrets Manager
- Cognito User Pool with app-specific group created
- RDS/Proxy security group allows inbound from app Lambda security group (output after first deploy)

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `AppName` | Yes | — | Application name for resource naming |
| `Environment` | No | `dev` | `dev`, `staging`, or `prod` |
| `CognitoUserPoolId` | Yes | — | Shared Cognito User Pool ID |
| `CognitoUserPoolArn` | Yes | — | Shared Cognito User Pool ARN |
| `AllowedCognitoGroup` | Yes | — | Cognito group allowed to access this app |
| `VpcId` | Yes | — | VPC ID for Lambda |
| `PrivateSubnetIds` | Yes | — | Comma-separated private subnet IDs |
| `RdsSecretArn` | Yes | — | Secrets Manager ARN with RDS credentials |
| `CorsAllowOrigin` | No | `*` | Frontend origin URL (must set when auth enabled) |
| `LambdaTimeout` | No | `30` | Lambda timeout in seconds |
| `LambdaMemory` | No | `512` | Lambda memory in MB |

## Quick start

### 1. Configure

Edit `samconfig.toml` and fill in the parameter values:

```toml
parameter_overrides = "AppName=\"my-app\" Environment=\"dev\" CognitoUserPoolId=\"ap-southeast-1_XXXXX\" ..."
```

### 2. Build & deploy

```bash
make deploy-guided   # first time (interactive)
make deploy          # subsequent deploys
```

### 3. Post-deploy

1. Note the `LambdaSecurityGroupId` from stack outputs
2. Ask infra team to allow this SG inbound on the RDS/Proxy security group (port 5432)

### 4. Test

```bash
# Get a Cognito token
TOKEN=$(aws cognito-idp initiate-auth \
  --client-id <AppClientId from outputs> \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=<user>,PASSWORD=<pass> \
  --query 'AuthenticationResult.IdToken' --output text)

# Create an item
curl -X POST <ApiUrl>/items \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "description": "hello world"}'

# List items
curl <ApiUrl>/items -H "Authorization: Bearer $TOKEN"
```

## API routes

| Method | Path | Description |
|---|---|---|
| GET | `/items` | List items (supports `?limit=&offset=`) |
| GET | `/items/{id}` | Get item by ID |
| POST | `/items` | Create item (`{"name": "...", "description": "..."}`) |
| PUT | `/items/{id}` | Update item |
| DELETE | `/items/{id}` | Delete item |

## Project structure

```
demo-sam-backend-starter/
├── template.yaml              # SAM template (all infrastructure)
├── samconfig.toml             # Deploy configuration
├── Makefile                   # Build/deploy commands
├── backend/
│   └── src/
│       ├── app.py             # Lambda handler with CRUDQ routing
│       └── requirements.txt   # Python dependencies (psycopg2)
├── authorizer/
│   └── src/
│       ├── authorizer.py      # JWT validation + group check
│       └── requirements.txt   # No external dependencies
└── README.md
```

## Important notes

- **CORS**: Default `AllowOrigin` is `*` which works for development. When Cognito auth is used from a browser, you **must** set this to the actual frontend domain (e.g., `https://main.d1234.amplifyapp.com`), because browsers reject wildcard origins with `Authorization` headers.
- **JWT verification**: The authorizer decodes and validates JWT claims (issuer, expiry, group) but does **not** perform RS256 signature verification. For production, add a library like `python-jose` or `PyJWT` with cryptographic verification against the JWKS endpoint.
- **DB table**: The `items` table is auto-created on first request. For production, use a migration tool.
- **Connection management**: Each Lambda invocation opens and closes a DB connection. For high-throughput, RDS Proxy handles connection pooling on the database side.

## Cleanup

```bash
make delete
```
