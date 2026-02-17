"""Template Parser - parses YAML templates and extracts config rules with service mappings."""

from dataclasses import dataclass, field
from io import StringIO

from ruamel.yaml import YAML


@dataclass
class ConfigRule:
    logical_name: str              # Resource logical name in the template
    config_rule_name: str          # ConfigRuleName property
    description: str               # Description property
    source_identifier: str         # Source.SourceIdentifier
    compliance_resource_types: list[str]  # Scope.ComplianceResourceTypes
    input_parameters: dict         # InputParameters (may reference template Parameters)
    services: set[str]             # Derived AWS services
    raw_resource: dict             # Original resource dict for faithful regeneration
    condition: str                 # Resource-level Condition key (empty if none)


@dataclass
class ParsedTemplate:
    name: str                      # Template filename
    parameters: dict               # Parameters section
    conditions: dict               # Conditions section
    rules: list[ConfigRule]        # All extracted config rules
    all_services: set[str]         # Union of all rule services


class TemplateParseError(Exception):
    """Raised when a YAML template cannot be parsed."""


class TemplateParser:
    """Parses YAML conformance pack templates and extracts config rules with service mappings."""

    # Mapping from SourceIdentifier prefixes to service names
    SOURCE_ID_SERVICE_MAP: dict[str, str] = {
        "EC2_": "EC2",
        "ECS_": "ECS",
        "S3_": "S3",
        "RDS_": "RDS",
        "IAM_": "IAM",
        "LAMBDA_": "Lambda",
        "DYNAMODB_": "DynamoDB",
        "CLOUDFRONT_": "CloudFront",
        "CLOUDTRAIL_": "CloudTrail",
        "CLOUD_TRAIL_": "CloudTrail",
        "CLOUDWATCH_": "CloudWatch",
        "CW_": "CloudWatch",
        "ELB_": "ELB",
        "ALB_": "ALB",
        "WAF": "WAF",
        "VPC_": "VPC",
        "EBS_": "EBS",
        "EFS_": "EFS",
        "ELASTICSEARCH_": "OpenSearch",
        "OPENSEARCH_": "OpenSearch",
        "REDSHIFT_": "Redshift",
        "SAGEMAKER_": "SageMaker",
        "SNS_": "SNS",
        "SQS_": "SQS",
        "KMS_": "KMS",
        "CMK_": "KMS",
        "SECRETSMANAGER_": "Secrets Manager",
        "CODEBUILD_": "CodeBuild",
        "EMR_": "EMR",
        "GUARDDUTY_": "GuardDuty",
        "SSM_": "Systems Manager",
        "ACM_": "ACM",
        "API_GW_": "API Gateway",
        "AUTOSCALING_": "Auto Scaling",
        "DB_INSTANCE_": "RDS",
        "DMS_": "DMS",
        "ECR_": "ECR",
        "ELASTICACHE_": "ElastiCache",
        "ELASTIC_BEANSTALK_": "Elastic Beanstalk",
        "ENCRYPTED_VOLUMES": "EC2",
        "INCOMING_SSH_": "EC2",
        "INSTANCES_IN_VPC": "EC2",
        "MFA_ENABLED_FOR_IAM_": "IAM",
        "ROOT_ACCOUNT_": "IAM",
        "SECURITYHUB_": "Security Hub",
    }

    # Mapping from CloudFormation resource types to service names
    RESOURCE_TYPE_SERVICE_MAP: dict[str, str] = {
        "AWS::EC2::": "EC2",
        "AWS::ECS::": "ECS",
        "AWS::S3::": "S3",
        "AWS::RDS::": "RDS",
        "AWS::IAM::": "IAM",
        "AWS::Lambda::": "Lambda",
        "AWS::DynamoDB::": "DynamoDB",
        "AWS::CloudFront::": "CloudFront",
        "AWS::ElasticLoadBalancing::": "ELB",
        "AWS::ElasticLoadBalancingV2::": "ALB",
        "AWS::WAF::": "WAF",
        "AWS::WAFv2::": "WAF",
        "AWS::EBS::": "EBS",
        "AWS::EFS::": "EFS",
        "AWS::Elasticsearch::": "OpenSearch",
        "AWS::OpenSearchService::": "OpenSearch",
        "AWS::OpenSearch::": "OpenSearch",
        "AWS::Redshift::": "Redshift",
        "AWS::SageMaker::": "SageMaker",
        "AWS::SNS::": "SNS",
        "AWS::SQS::": "SQS",
        "AWS::KMS::": "KMS",
        "AWS::SecretsManager::": "Secrets Manager",
        "AWS::CodeBuild::": "CodeBuild",
        "AWS::EMR::": "EMR",
        "AWS::GuardDuty::": "GuardDuty",
        "AWS::SSM::": "Systems Manager",
        "AWS::CertificateManager::": "ACM",
        "AWS::ACM::": "ACM",
        "AWS::ApiGateway::": "API Gateway",
        "AWS::ApiGatewayV2::": "API Gateway",
        "AWS::AutoScaling::": "Auto Scaling",
        "AWS::ECR::": "ECR",
        "AWS::ElasticBeanstalk::": "Elastic Beanstalk",
        "AWS::ElastiCache::": "ElastiCache",
        "AWS::DMS::": "DMS",
    }

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.preserve_quotes = True

    def parse_template(self, name: str, yaml_content: str) -> ParsedTemplate:
        """Parse a YAML template and extract all config rules with service mappings.

        Args:
            name: Template filename.
            yaml_content: Raw YAML string.

        Returns:
            ParsedTemplate with extracted rules and services.

        Raises:
            TemplateParseError: If the YAML is malformed or unparseable.
        """
        try:
            data = self._yaml.load(StringIO(yaml_content))
        except Exception as exc:
            raise TemplateParseError(f"Malformed YAML in {name}: {exc}") from exc

        if data is None:
            raise TemplateParseError(f"Empty YAML document in {name}")

        parameters = dict(data.get("Parameters", {}) or {})
        conditions = dict(data.get("Conditions", {}) or {})
        resources = data.get("Resources", {}) or {}

        rules: list[ConfigRule] = []
        all_services: set[str] = set()

        for logical_name, resource in resources.items():
            if not isinstance(resource, dict):
                continue
            resource_type = resource.get("Type", "")
            if resource_type != "AWS::Config::ConfigRule":
                continue

            try:
                rule = self._extract_rule(logical_name, resource)
                rules.append(rule)
                all_services.update(rule.services)
            except Exception:
                # Skip individual rules with unexpected structure
                continue

        return ParsedTemplate(
            name=name,
            parameters=parameters,
            conditions=conditions,
            rules=rules,
            all_services=all_services,
        )

    def _extract_rule(self, logical_name: str, resource: dict) -> ConfigRule:
        """Extract a ConfigRule from a resource dict."""
        props = resource.get("Properties", {}) or {}

        config_rule_name = props.get("ConfigRuleName", "")
        description = props.get("Description", "")

        source = props.get("Source", {}) or {}
        source_identifier = source.get("SourceIdentifier", "")

        scope = props.get("Scope", {}) or {}
        compliance_resource_types = list(scope.get("ComplianceResourceTypes", []) or [])

        input_parameters = dict(props.get("InputParameters", {}) or {})

        # Capture resource-level Condition key (outside Properties)
        condition = str(resource.get("Condition", "") or "")

        rule = ConfigRule(
            logical_name=logical_name,
            config_rule_name=str(config_rule_name),
            description=str(description),
            source_identifier=str(source_identifier),
            compliance_resource_types=[str(t) for t in compliance_resource_types],
            input_parameters=input_parameters,
            services=set(),
            raw_resource=dict(resource),
            condition=condition,
        )

        rule.services = self.extract_services(rule)
        return rule

    def extract_services(self, rule: ConfigRule) -> set[str]:
        """Determine AWS services for a config rule from SourceIdentifier and ComplianceResourceTypes.

        Uses a two-pass approach:
        1. Match SourceIdentifier against known prefixes.
        2. Match ComplianceResourceTypes against known CloudFormation resource type prefixes.
        3. Union both results. If empty, tag with "Other".
        """
        services: set[str] = set()

        # Pass 1: SourceIdentifier prefix matching
        sid = rule.source_identifier
        for prefix, service in self.SOURCE_ID_SERVICE_MAP.items():
            if sid.startswith(prefix):
                services.add(service)
                break

        # Pass 2: ComplianceResourceTypes matching
        for resource_type in rule.compliance_resource_types:
            for type_prefix, service in self.RESOURCE_TYPE_SERVICE_MAP.items():
                if resource_type.startswith(type_prefix):
                    services.add(service)
                    break

        # Tag unmatched rules with "Other"
        if not services:
            services.add("Other")

        return services

    def get_all_services(self, templates: list[ParsedTemplate]) -> list[str]:
        """Return deduplicated, alphabetically sorted list of all services across templates."""
        all_services: set[str] = set()
        for template in templates:
            all_services.update(template.all_services)
        return sorted(all_services)
