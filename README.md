# demo-sam-backend-starter

A SAM-based backend starter kit for teams modernizing to serverless on AWS.

## Architecture

```
Client → API Gateway (REST API) → Lambda (Python 3.12) → RDS PostgreSQL (via RDS Proxy)
              ↓
       Lambda Authorizer → validates Cognito JWT + group membership
```

## What's included

| Component | Description |
|---|---|
| API Gateway (REST API) | Routes with CORS, WAF-ready, per-app |
| Backend Lambda | CRUDQ API for `items` table in RDS PostgreSQL |
| Authorizer Lambda | Validates Cognito JWT and checks group membership |
| Cognito App Client | Per-app client in centralized User Pool |
| Secrets Manager Secret | App-owned, created by template with RDS credentials |
| Lambda Security Group | App-owned SG in provided VPC |

## Prerequisites (infra team provides)

- VPC with private subnets
- RDS Proxy + RDS PostgreSQL
- Secrets Manager secret with DB credentials and proxy endpoint (standard RDS format: `host`, `port`, `username`, `password`, `dbname`) — OR provide credentials as template parameters and the template creates the secret
- VPC endpoints: Secrets Manager
- Cognito User Pool with app-specific group created
- RDS/Proxy security group allows inbound from app Lambda security group (output after first deploy)

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `Project` | Yes | — | Application name for resource naming |
| `Environment` | No | `dev` | `dev`, `staging`, or `prod` |
| `CognitoUserPoolId` | Yes | — | Shared Cognito User Pool ID |
| `CognitoUserPoolArn` | Yes | — | Shared Cognito User Pool ARN |
| `AllowedCognitoGroup` | Yes | — | Cognito group allowed to access this app |
| `VpcId` | Yes | — | VPC ID for Lambda |
| `PrivateSubnetIds` | Yes | — | Comma-separated private subnet IDs |
| `RdsHost` | No | `your-rds-proxy-endpoint...` | RDS Proxy endpoint |
| `RdsPort` | No | `5432` | Database port |
| `RdsDbName` | No | `mydb` | Database name |
| `RdsUsername` | No | `dbadmin` | Database username (NoEcho) |
| `RdsPassword` | No | `changeme` | Database password (NoEcho) |
| `CorsAllowOrigin` | No | `*` | Frontend origin URL (must set when auth enabled) |
| `LambdaTimeout` | No | `30` | Lambda timeout in seconds |
| `LambdaMemory` | No | `512` | Lambda memory in MB |

## Getting started — for app teams

### Step 1: Copy the template

```bash
cp -r demo-sam-backend-starter my-app-name
cd my-app-name
```

### Step 2: Gather infra team inputs

Before deploying, request the following from your infrastructure team:

| What you need | Example value |
|---|---|
| Cognito User Pool ID | `ap-southeast-1_AbCdEfG` |
| Cognito User Pool ARN | `arn:aws:cognito-idp:ap-southeast-1:123456789012:userpool/ap-southeast-1_AbCdEfG` |
| Cognito group name for your app | `my-app-users` |
| VPC ID | `vpc-0abc1234def56789` |
| Private subnet IDs (2+) | `subnet-aaa111,subnet-bbb222` |
| RDS Proxy endpoint | `my-proxy.proxy-xxx.ap-southeast-1.rds.amazonaws.com` |
| Database name | `mydb` |
| Database username | `dbadmin` |
| Database password | *(provided securely)* |

### Step 3: Deploy (first time)

```bash
make deploy-guided
```

SAM will prompt you for each parameter one by one:

```
Parameter Project []: my-app-name
Parameter Environment [dev]: dev
Parameter CognitoUserPoolId []: ap-southeast-1_AbCdEfG
Parameter CognitoUserPoolArn []: arn:aws:cognito-idp:ap-southeast-1:123456789012:userpool/ap-southeast-1_AbCdEfG
Parameter AllowedCognitoGroup []: my-app-users
Parameter VpcId []: vpc-0abc1234def56789
Parameter PrivateSubnetIds []: subnet-aaa111,subnet-bbb222
Parameter RdsHost [your-rds-proxy-endpoint.rds.amazonaws.com]: my-proxy.proxy-xxx.ap-southeast-1.rds.amazonaws.com
Parameter RdsDbName [mydb]: mydb
Parameter RdsUsername [dbadmin]: dbadmin
Parameter RdsPassword [changeme]: ********
...
```

Your answers are saved to `samconfig.toml` automatically. You won't need to enter them again.

### Step 4: Subsequent deploys

```bash
make deploy
```

To change parameter values later, run `make deploy-guided` again — it shows current values as defaults.

### Step 5: Post-deploy setup

1. Get stack outputs:
   ```bash
   aws cloudformation describe-stacks --stack-name my-app-name-dev --query "Stacks[0].Outputs"
   ```
2. Send `LambdaSecurityGroupId` to infra team — they must allow it inbound on the RDS/Proxy security group (port 5432)
3. Note `ApiUrl` and `CognitoAppClientId` for testing and frontend integration

### Step 6: Write your code

Replace the sample code in `backend/src/app.py` with your application logic:

1. Update the table schema in `_init_table()` or replace with a migration tool
2. Add your routes in the `handler()` function
3. Add corresponding API Gateway events in `template.yaml` under `BackendFunction.Events`
4. Add any new Python dependencies to `backend/src/requirements.txt`

### Step 7: Test

```bash
# Get a Cognito token
TOKEN=$(aws cognito-idp initiate-auth \
  --client-id <CognitoAppClientId> \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=<user>,PASSWORD=<pass> \
  --query 'AuthenticationResult.IdToken' --output text)

# Call your API
curl <ApiUrl>/items -H "Authorization: Bearer $TOKEN"
```

### Step 8: Redeploy after code changes

```bash
make deploy
```

## Quick start

### 1. Configure

Edit `samconfig.toml` and fill in the parameter values:

```toml
parameter_overrides = "Project=\"my-app\" Environment=\"dev\" CognitoUserPoolId=\"ap-southeast-1_XXXXX\" ..."
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
- **Secrets Manager**: The template creates a secret named `<Project>-<Environment>/rds-credentials` with the RDS connection details you provide as parameters. You can also update the secret values later via the console or CLI: `aws secretsmanager update-secret --secret-id <Project>-<Environment>/rds-credentials --secret-string '{"host":"...","port":5432,"dbname":"...","username":"...","password":"..."}'`
- **DB table**: The `items` table is auto-created on first request. For production, use a migration tool.
- **Connection management**: Each Lambda invocation opens and closes a DB connection. For high-throughput, RDS Proxy handles connection pooling on the database side.

## Cleanup

```bash
make delete
```
