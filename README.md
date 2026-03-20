# demo-sam-backend-starter

A SAM-based backend starter kit for teams modernizing to serverless on AWS.

## Architecture

```
Client → API Gateway (REST API) → Lambda (Python 3.12) → RDS PostgreSQL
              ↓
       Lambda Authorizer → validates Cognito JWT + group membership
```

## What's included

| Component | Description |
|---|---|
| API Gateway (REST API) | Routes with CORS, WAF-ready, per-app |
| Backend Lambda | CRUDQ API for `items` table in RDS PostgreSQL |
| Authorizer Lambda | Validates Cognito JWT signature (RS256) and checks group membership |
| Cognito App Client | Per-app client in centralized User Pool |
| Secrets Manager Secret | App-owned, created with placeholder values |
| Lambda Security Group | App-owned SG in provided VPC |

## Prerequisites (infra team provides)

- VPC with private subnets
- RDS PostgreSQL
- VPC endpoints: Secrets Manager
- Cognito User Pool with app-specific group created
- Per-app database user and credentials (handed to app team securely)

## Prerequisites (local machine)

- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- [Docker](https://docs.docker.com/get-docker/) (required for `sam build --use-container`)
- AWS CLI configured with credentials
- **Windows users**: Use PowerShell version of test script (`test-api.ps1`)

## Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `Project` | Yes | - | Application name for resource naming |
| `Environment` | No | `dev` | `dev`, `staging`, or `prod` |
| `CognitoUserPoolId` | Yes | - | Shared Cognito User Pool ID |
| `CognitoUserPoolArn` | Yes | - | Shared Cognito User Pool ARN |
| `AllowedCognitoGroup` | Yes | - | Cognito group allowed to access this app |
| `VpcId` | Yes | - | VPC ID for Lambda |
| `PrivateSubnetIds` | Yes | - | Comma-separated private subnet IDs |
| `SecretsExtensionLayerArn` | No | *(ap-southeast-1 default)* | AWS Parameters and Secrets Lambda Extension layer ARN ([find your region's ARN](https://docs.aws.amazon.com/systems-manager/latest/userguide/ps-integration-lambda-extensions.html)) |
| `CorsAllowOrigin` | No | `*` | Frontend origin URL (must set when auth enabled) |
| `LambdaTimeout` | No | `30` | Lambda timeout in seconds |
| `LambdaMemory` | No | `512` | Lambda memory in MB |

## Getting started - for app teams

### Step 1: Copy the template

```bash
cp -r demo-sam-backend-starter my-app-name
cd my-app-name
```

### Step 2: Gather infra team inputs

Request the following from your infrastructure team:

| What you need | Example value |
|---|---|
| Cognito User Pool ID | `ap-southeast-1_AbCdEfG` |
| Cognito User Pool ARN | `arn:aws:cognito-idp:ap-southeast-1:123456789012:userpool/ap-southeast-1_AbCdEfG` |
| Cognito group name for your app | `my-app-users` |
| VPC ID | `vpc-0abc1234def56789` |
| Private subnet IDs (2+) | `subnet-aaa111,subnet-bbb222` |
| RDS endpoint | `my-rds.xxx.ap-southeast-1.rds.amazonaws.com` |
| Database name | `appdb` |
| Database username | *(provided securely)* |
| Database password | *(provided securely)* |

### Step 3: Deploy (first time)

```bash
sam build --use-container && sam deploy --guided --tags "project=<Project> environment=<Environment>"
```

SAM will prompt you for each parameter one by one. Your answers are saved to `samconfig.toml` automatically. The `--tags` flag ensures all resources (including API Gateway) are tagged consistently.

### Step 4: Update RDS credentials in Secrets Manager

The template creates a secret with placeholder values. Update it with the actual credentials from your infra team:

```bash
aws secretsmanager update-secret \
  --secret-id <Project>-<Environment>/rds-credentials \
  --secret-string '{"host":"my-rds.xxx.rds.amazonaws.com","port":5432,"dbname":"appdb","username":"myapp_user","password":"actual-password"}'
```

### Step 5: Post-deploy setup

1. Get stack outputs:
   ```bash
   aws cloudformation describe-stacks --stack-name <your-stack-name> --query "Stacks[0].Outputs"
   ```
2. Note `ApiUrl` and `CognitoAppClientId` for testing and frontend integration

### Step 6: Test

Run the included test script:

**Bash (macOS/Linux):**
```bash
./test-api.sh <ApiUrl> <CognitoAppClientId> <username> <password> <region>
```

**PowerShell (Windows):**
```powershell
.\test-api.ps1 <ApiUrl> <CognitoAppClientId> <username> <password> <region>
```

Example:
```bash
./test-api.sh \
  https://xxx.execute-api.ap-southeast-1.amazonaws.com/dev \
  <CognitoAppClientId> \
  <cognito-username> \
  '<cognito-password>' \
  ap-southeast-1
```

```powershell
.\test-api.ps1 `
  https://xxx.execute-api.ap-southeast-1.amazonaws.com/dev `
  <CognitoAppClientId> `
  <cognito-username> `
  '<cognito-password>' `
  ap-southeast-1
```

The script tests all CRUD operations, 404 handling, and authentication/authorization (8 tests total).

## Building your own API

The template includes a working CRUD API for an `items` table as a starting point. To build your own:

1. Add your tables/schema in `_init_table()` or replace with a migration tool
2. Add your route handlers in `backend/src/app.py`
3. Add corresponding API Gateway events in `template.yaml` under `BackendFunction.Events`
4. Add any new Python dependencies to `backend/src/requirements.txt`

After making changes, redeploy:

```bash
sam build --use-container && sam deploy
```

To change parameter values, run `sam build --use-container && sam deploy --guided` again.

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
├── test-api.sh                # API test script (bash)
├── test-api.ps1               # API test script (PowerShell for Windows)
├── backend/
│   └── src/
│       ├── app.py             # Lambda handler with CRUDQ routing
│       └── requirements.txt   # Python dependencies (psycopg2)
├── authorizer/
│   └── src/
│       ├── authorizer.py      # JWT signature verification + group check
│       └── requirements.txt   # python-jose for RS256 verification
└── README.md
```

## Important notes

- **CORS**: Default `AllowOrigin` is `*` which works for development. When Cognito auth is used from a browser, you **must** set this to the actual frontend domain (e.g., `https://main.d1234.amplifyapp.com`), because browsers reject wildcard origins with `Authorization` headers.
- **JWT verification**: The authorizer verifies JWT signature (RS256) against Cognito's JWKS keys, validates issuer, expiration, and group membership.
- **Secrets Manager**: The template creates a secret named `<Project>-<Environment>/rds-credentials` with placeholder values. You must update it with actual credentials after deploy (see Step 4).
- **DB schema**: Lambda auto-creates a schema named `<project>_<environment>` (hyphens replaced with underscores, e.g., `my_app_dev`). If the infra team pre-creates the schema, Lambda uses it without needing extra privileges. If the schema doesn't exist, Lambda creates it (requires `CREATE` privilege on the database).
- **DB table**: The `items` table is auto-created in the app schema on first request. For production, use a migration tool.
- **Connection management**: Each Lambda invocation opens and closes a DB connection.
- **Lambda Extension layer**: The default layer ARN is for `ap-southeast-1`. If deploying to a different region, override `SecretsExtensionLayerArn` with the correct ARN from [AWS docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/ps-integration-lambda-extensions.html).

## Cleanup

```bash
sam delete
```
