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
| Authorizer Lambda | Validates Cognito JWT and checks group membership |
| Cognito App Client | Per-app client in centralized User Pool |
| Secrets Manager Secret | App-owned, created with placeholder values |
| Lambda Security Group | App-owned SG in provided VPC |

## Prerequisites (infra team provides)

- VPC with private subnets
- RDS PostgreSQL
- VPC endpoints: Secrets Manager
- Cognito User Pool with app-specific group created
- Per-app database user and credentials (handed to app team securely)
- RDS security group allows inbound from app Lambda security group (after first deploy)

## Prerequisites (local machine)

- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- Python 3.12 (must match the runtime in template.yaml)
- AWS CLI configured with credentials
- Docker (optional, for `sam build --use-container` if Python version doesn't match)

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
...
```

Your answers are saved to `samconfig.toml` automatically.

### Step 4: Update RDS credentials in Secrets Manager

The template creates a secret with placeholder values. Update it with the actual credentials from your infra team:

```bash
aws secretsmanager update-secret \
  --secret-id my-app-name-dev/rds-credentials \
  --secret-string '{"host":"my-rds.xxx.rds.amazonaws.com","port":5432,"dbname":"appdb","username":"myapp_user","password":"actual-password"}'
```

### Step 5: Post-deploy setup

1. Get stack outputs:
   ```bash
   aws cloudformation describe-stacks --stack-name my-app-name-dev --query "Stacks[0].Outputs"
   ```
2. Send `LambdaSecurityGroupId` to infra team - they must allow it inbound on the RDS security group (port 5432)
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

To change parameter values later, run `make deploy-guided` again.

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
- **JWT verification**: The authorizer verifies JWT signature (RS256) against Cognito's JWKS keys, validates issuer, expiration, and group membership.
- **Secrets Manager**: The template creates a secret named `<Project>-<Environment>/rds-credentials` with placeholder values. You must update it with actual credentials after deploy (see Step 4).
- **DB table**: The `items` table is auto-created on first request. For production, use a migration tool.
- **Connection management**: Each Lambda invocation opens and closes a DB connection.

## Cleanup

```bash
make delete
```
