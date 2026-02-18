# NZISM Config Filter

> This is a community-driven, independent open source project. It is not affiliated with, endorsed by, or officially supported by Amazon Web Services (AWS) or the New Zealand Government Communications Security Bureau (GCSB).

A web application that helps New Zealand public sector customers generate filtered AWS Config conformance pack templates based on the AWS services they use.

Instead of deploying the full NZISM conformance pack (which may contain hundreds of rules for services you don't use), this tool lets you select only the AWS services relevant to your environment and generates a tailored YAML template ready for deployment.

## How It Works

1. The app fetches the latest NZISM conformance pack templates from the [official AWS repository](https://github.com/awslabs/aws-config-rules/tree/master/aws-config-conformance-packs)
2. It parses each template to extract Config rules and maps them to AWS services
3. You select the services you use (e.g., EC2, S3, Lambda, RDS)
4. The app generates filtered templates containing only the rules relevant to your selected services, including the required Parameters and Conditions sections
5. Download the filtered YAML template and deploy it as a conformance pack

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                               │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  CloudFront   │───▶│  S3 Bucket   │    │  Secrets Manager │  │
│  │  Distribution │    │  (React SPA) │    │  (Origin Secret) │  │
│  │  + WAF        │    └──────────────┘    └────────┬─────────┘  │
│  │               │                                 │            │
│  │  /api/* ──────│──▶ ┌──────────────┐    ┌────────▼─────────┐  │
│  │               │    │ API Gateway  │───▶│ Lambda Authorizer│  │
│  └──────────────┘    │ (REST API)   │    │ (Origin Verify)  │  │
│                      └──────┬───────┘    └──────────────────┘  │
│                             │                                   │
│                      ┌──────▼───────┐                          │
│                      │   Lambda     │──▶ GitHub API            │
│                      │  (Python)    │   (NZISM templates)      │
│                      └──────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| CloudFront | Unified entry point for frontend and API, with WAF protection |
| S3 Bucket | Hosts the React SPA (private, accessed via OAC) |
| API Gateway | REST API with two endpoints |
| Lambda (Backend) | Fetches, parses, filters, and generates conformance pack templates |
| Lambda (Authorizer) | Validates origin verification header to block direct API access |
| Secrets Manager | Stores the shared secret between CloudFront and API Gateway |
| WAF WebACL | Rate limiting and managed rule protection (deployed in us-east-1) |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/templates` | Fetches NZISM templates from GitHub, returns available services |
| POST | `/api/filter` | Accepts selected services, returns filtered YAML templates |

### Backend Modules

| Module | Responsibility |
|--------|---------------|
| `fetcher.py` | Discovers and downloads NZISM templates from GitHub (with in-memory caching) |
| `parser.py` | Parses YAML templates, extracts Config rules, maps rules to AWS services |
| `filter.py` | Filters rules by selected services, resolves Parameter and Condition dependencies |
| `generator.py` | Generates valid YAML conformance pack templates with summary headers |
| `handler.py` | Lambda entry point, routes API Gateway requests |

### Filtering Logic

The filter follows the dependency chain: **Rule → Condition → Parameter**

1. Rules are included if their mapped services overlap with the user's selection
2. Conditions are included if referenced by an included rule's resource-level `Condition` key
3. Parameters are included if referenced by an included rule's `InputParameters` (via `!Ref`) or by an included condition's body (via `Ref`)

This ensures the generated template is self-contained and deployable.

### Security

- **WAF**: Rate limiting (1000 req/5min), AWS managed rules for XSS/SQLi protection
- **Origin Verification**: API Gateway only accepts requests from CloudFront via a secret header validated by a Lambda authorizer
- **S3 Protection**: Bucket is fully private, accessed only through CloudFront OAC
- **No data stored**: The app is stateless — no user data is stored or logged

## Prerequisites

| Tool | Version |
|------|---------|
| AWS CLI | v2 |
| AWS SAM CLI | Latest |
| Node.js | 18+ |
| Python | 3.11+ |

## Quick Start

```bash
git clone https://github.com/jasonshisre/aws-config-nzism-filter.git
cd aws-config-nzism-filter

# Deploy everything (WAF + Application)
make deploy-all
```

The CloudFront URL is printed in the stack outputs after deployment.

## Deployment Commands

| Command | Description |
|---------|-------------|
| `make deploy-all` | Full deployment: WAF (us-east-1) + Application |
| `make deploy` | Application only (skips WAF) |
| `make deploy-waf` | WAF stack only (us-east-1) |
| `make destroy-all` | Remove everything |
| `make destroy` | Remove application stack only |
| `make destroy-waf` | Remove WAF stack only |
| `make clean` | Remove local build artifacts |

### Configuration

```bash
# Change region (default: ap-southeast-2)
REGION=us-west-2 make deploy

# Change stack name (default: nzism-config-filter)
STACK_NAME=my-nzism make deploy
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions, manual steps, and troubleshooting.

## Running Tests

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
```

## Project Structure

```
├── template.yaml              # SAM template (main infrastructure)
├── waf-template.yaml          # WAF CloudFormation template (us-east-1)
├── Makefile                   # Build and deploy orchestration
├── DEPLOYMENT.md              # Detailed deployment guide
├── backend/
│   ├── requirements.txt
│   ├── src/
│   │   ├── handler.py         # Lambda entry point
│   │   ├── fetcher.py         # GitHub template fetcher
│   │   ├── parser.py          # YAML parser + service mapper
│   │   ├── filter.py          # Service-based rule filter
│   │   └── generator.py       # YAML template generator
│   └── tests/
│       ├── test_parser.py
│       ├── test_filter.py
│       └── test_generator.py
└── frontend/
    ├── package.json
    ├── index.html
    └── src/
        ├── App.tsx
        ├── api/client.ts
        └── components/
            ├── ServiceSelector.tsx
            └── TemplateResults.tsx
```

## License

This project is open source. See [LICENSE](LICENSE) for details.
