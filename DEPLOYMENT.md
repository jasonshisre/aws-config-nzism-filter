# Deploying the NZISM Config Filter

This guide walks you through deploying the NZISM Config Filter application to AWS. The app runs as a serverless stack: a React frontend on CloudFront + S3, and a Python backend on Lambda + API Gateway.

## Prerequisites

Install the following before you begin:

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | v2 | [Install AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| AWS SAM CLI | Latest | [Install SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) |
| Node.js | 18+ | [Download Node.js](https://nodejs.org/) |
| Python | 3.11+ | [Download Python](https://www.python.org/downloads/) |

You also need an AWS account with admin permissions (or at minimum, permissions to create IAM roles, Lambda functions, API Gateway APIs, S3 buckets, and CloudFront distributions).

## AWS Account Setup

Configure your AWS credentials if you haven't already:

```bash
aws configure
```

You'll be prompted for:
- **AWS Access Key ID** — from your IAM user or SSO session
- **AWS Secret Access Key**
- **Default region name** — enter `ap-southeast-2` (Sydney is the default for this project)
- **Default output format** — `json` works well

Verify your credentials are working:

```bash
aws sts get-caller-identity
```

## Quick Start

The fastest path from clone to running application:

```bash
git clone <repository-url>
cd nzism-config-filter
make deploy-all
```

This deploys:
1. **WAF stack** in us-east-1 (required for CloudFront WAF)
2. **Main application stack** in ap-southeast-2 (or your configured region)

When deployment finishes, the stack outputs are printed as a table. Look for the `CloudFrontUrl` — that's your application URL.

```
-----------------------------------------------------------------
|                        Outputs                                |
+-----------------+---------------------------------------------+
|  CloudFrontUrl  |  https://d1234abcdef.cloudfront.net         |
|  ApiUrl         |  https://abc123.execute-api...              |
|  FrontendBucket |  nzism-config-filter-frontendbucket-xyz     |
+-----------------+---------------------------------------------+
```

Open the `CloudFrontUrl` in your browser to use the application.

> **Note:** CloudFront distributions can take 5–15 minutes to fully propagate after the first deployment. If you get an error immediately, wait a few minutes and try again.

### Deployment Options

| Command | Description |
|---------|-------------|
| `make deploy-all` | Full deployment: WAF (us-east-1) + Application (your region) |
| `make deploy-waf` | Deploy only the WAF stack to us-east-1 |
| `make deploy` | Deploy only the application stack (uses existing WAF if available) |

### Without WAF

If you don't need WAF protection, you can deploy just the application:

```bash
make deploy
```

The application will work without WAF, but CloudFront won't have rate limiting or managed rule protection.

## Security Architecture

The application implements multiple layers of security:

### WAF Protection (CloudFront)

When deployed with `make deploy-all`, a WAF WebACL protects CloudFront with:

| Rule | Description |
|------|-------------|
| Rate Limiting | Blocks IPs exceeding 1000 requests per 5 minutes |
| AWSManagedRulesCommonRuleSet | Protects against XSS, SQL injection, and common attacks |
| AWSManagedRulesKnownBadInputsRuleSet | Blocks known malicious request patterns |

The WAF stack is deployed separately in us-east-1 (required for CloudFront-scoped WAF) and referenced by the main stack.

### Origin Verification (API Gateway)

The API Gateway is protected from direct access bypass using a secret header verification:

1. **Secret in Secrets Manager**: An auto-generated 32-character secret is stored in AWS Secrets Manager
2. **CloudFront adds header**: CloudFront automatically adds the `x-origin-verify` header to all API requests
3. **Lambda Authorizer validates**: A Lambda authorizer rejects requests without the correct header

This ensures all API traffic must flow through CloudFront, where WAF rules are enforced. Direct calls to the API Gateway URL are rejected with 403.

### S3 Bucket Protection

The frontend S3 bucket is configured with:
- All public access blocked
- Origin Access Control (OAC) for CloudFront
- Bucket policy allowing only CloudFront to read objects

### Secret Rotation

The origin verification secret is auto-generated during deployment. To rotate it:

1. Delete the secret in Secrets Manager (or update it manually)
2. Redeploy with `make deploy`
3. CloudFront will automatically use the new secret value

## Service Mapping Notes

The application groups AWS Config rules by service name. Some mappings may not be immediately obvious:

| Template Resource / Rule Prefix | Displayed As | Why |
|---|---|---|
| `AWS::EC2::SecurityGroup`, `INCOMING_SSH_DISABLED`, `VPC_SG_OPEN_ONLY_TO_AUTHORIZED_PORTS` | **EC2** | Security Groups are an EC2 resource. Selecting "EC2" includes all security group rules. |
| `AWS::EC2::Volume`, `ENCRYPTED_VOLUMES`, `EBS_*` | **EC2** / **EBS** | EBS volumes may appear under EC2 or EBS depending on how the rule is defined. |
| `ELASTICSEARCH_*`, `AWS::Elasticsearch::Domain` | **OpenSearch** | AWS renamed Elasticsearch Service to OpenSearch Service. Both old and new rule prefixes map to "OpenSearch". |
| `CLOUD_TRAIL_*`, `CLOUDTRAIL_*` | **CloudTrail** | Some rules use underscores (`CLOUD_TRAIL_`), others don't (`CLOUDTRAIL_`). Both map to "CloudTrail". |
| `ROOT_ACCOUNT_*`, `MFA_ENABLED_FOR_IAM_*` | **IAM** | Root account and MFA rules are IAM-related. |
| `INSTANCES_IN_VPC`, `INCOMING_SSH_DISABLED` | **EC2** | These are general EC2 instance rules without the `EC2_` prefix. |

If a rule's SourceIdentifier or ComplianceResourceType doesn't match any known mapping, it appears under **"Other"**. This can happen if AWS adds new Config rules with new prefixes. To add support for a new service:

1. Open `backend/src/parser.py`
2. Add the new prefix to `SOURCE_ID_SERVICE_MAP` (for SourceIdentifier-based rules) and/or `RESOURCE_TYPE_SERVICE_MAP` (for ComplianceResourceType-based rules)
3. Redeploy with `make deploy`

Until the mapping is added, affected rules will still be included in filtered output — they just appear under "Other" instead of the specific service name.

## Manual Step-by-Step Deployment

If you prefer to run each step individually instead of using `make deploy`:

### 1. Build the frontend

```bash
cd frontend
npm ci
npm run build
cd ..
```

This installs dependencies and produces a production build in `frontend/dist/`.

### 2. Build the backend

```bash
cd backend
pip install -r requirements.txt -t .package/
cp -r src .package/
cd ..
```

### 3. Build and deploy with SAM

For a first-time deployment, use the guided flow:

```bash
sam build
sam deploy --guided
```

SAM will prompt you for:
- **Stack Name** — use `nzism-config-filter` (or your preferred name)
- **AWS Region** — use `ap-southeast-2` (or your preferred region)
- **Confirm changes before deploy** — your choice
- **Allow SAM CLI IAM role creation** — Yes
- **Save arguments to configuration file** — Yes (saves to `samconfig.toml` for future deploys)

For subsequent deployments, you can skip the guided flow:

```bash
sam build
sam deploy
```

### 4. Upload frontend assets to S3

After the stack deploys, get the S3 bucket name from the stack outputs:

```bash
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name nzism-config-filter \
  --region ap-southeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
  --output text)

aws s3 sync frontend/dist s3://$BUCKET --delete --region ap-southeast-2
```

### 5. Get the application URL

```bash
aws cloudformation describe-stacks \
  --stack-name nzism-config-filter \
  --region ap-southeast-2 \
  --query 'Stacks[0].Outputs' \
  --output table
```

The `CloudFrontUrl` output is your application URL.

## Configuration

### Changing the AWS region

The default region is `ap-southeast-2` (Sydney). To deploy to a different region:

```bash
REGION=us-east-1 make deploy
```

### Changing the stack name

The default stack name is `nzism-config-filter`. To use a different name:

```bash
STACK_NAME=my-nzism-stack make deploy
```

### Combining options

```bash
STACK_NAME=my-stack REGION=us-east-1 make deploy
```

## Updating and Redeploying

To update the application after making code changes, just run:

```bash
make deploy
```

SAM automatically creates and applies a CloudFormation changeset. Only the resources that changed are updated. The frontend assets are re-synced to S3 as well.

## Tearing Down

To remove all deployed resources:

```bash
make destroy-all
```

This removes:
1. The main application stack (empties S3 bucket first, then deletes CloudFormation stack)
2. The WAF stack in us-east-1

### Partial Cleanup

| Command | Description |
|---------|-------------|
| `make destroy-all` | Remove everything (application + WAF) |
| `make destroy` | Remove only the application stack |
| `make destroy-waf` | Remove only the WAF stack in us-east-1 |

> **Note:** If you destroy the WAF stack while the application is still deployed, CloudFront will continue to work but without WAF protection.

## Troubleshooting

### AWS credentials not configured

**Symptom:** `Unable to locate credentials` or `The config profile could not be found`

**Fix:** Run `aws configure` and enter your access key, secret key, and region. Or if using SSO, run `aws sso login`.

### SAM CLI not found

**Symptom:** `sam: command not found`

**Fix:** Install the SAM CLI following the [official guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html). Make sure it's on your PATH.

### S3 bucket not empty on delete

**Symptom:** Stack deletion fails with `The bucket you tried to delete is not empty`

**Fix:** Use `make destroy` instead of deleting the stack manually. It empties the bucket first. If you already tried a manual delete, empty the bucket and retry:

```bash
aws s3 rm s3://BUCKET_NAME --recursive
aws cloudformation delete-stack --stack-name nzism-config-filter --region ap-southeast-2
```

### CloudFront propagation delay

**Symptom:** The CloudFront URL returns an error or shows stale content right after deployment.

**Fix:** CloudFront distributions take 5–15 minutes to propagate globally after creation or update. Wait and try again. For content updates, you can create an invalidation:

```bash
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

### Lambda timeout issues

**Symptom:** API calls return 504 Gateway Timeout.

**Fix:** The Lambda function has a 30-second timeout configured in `template.yaml`. If template fetching from GitHub is slow, you can increase the timeout in the `Globals` section:

```yaml
Globals:
  Function:
    Timeout: 60
```

Then redeploy with `make deploy`.

### CORS errors during local development

**Symptom:** Browser console shows CORS errors when the frontend dev server calls the deployed API.

**Fix:** This only happens during local development when the frontend runs on `localhost` but calls the deployed API Gateway directly. In production, CloudFront serves both the frontend and API from the same domain, so CORS is not an issue.

For local development, either:
1. Use the CloudFront URL (the deployed version) for testing
2. Set up a local proxy in your Vite config to forward `/api/*` requests to the deployed API Gateway URL

### Rate limit errors (403)

**Symptom:** The app shows "Server error (403)" after many rapid requests.

**Fix:** This is WAF rate limiting working as intended. Wait 5 minutes for the rate limit window to reset. If you need higher limits for legitimate use, update the `Limit` value in `waf-template.yaml` and redeploy with `make deploy-waf`.

### API returns 403 when called directly

**Symptom:** Calling the API Gateway URL directly returns `{"message":"User is not authorized to access this resource"}`

**Fix:** This is expected behavior. The API is protected by origin verification and only accepts requests from CloudFront. Always use the CloudFront URL to access the application.
