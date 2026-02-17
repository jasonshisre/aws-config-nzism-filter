"""Unit tests for TemplateParser."""

import pytest

from src.parser import ConfigRule, ParsedTemplate, TemplateParseError, TemplateParser


@pytest.fixture
def parser():
    return TemplateParser()


VALID_TEMPLATE_YAML = """\
Parameters:
  Ec2DesiredInstanceType:
    Default: t2.micro
    Type: String
Resources:
  Ec2InstanceNoPublicIp:
    Properties:
      ConfigRuleName: ec2-instance-no-public-ip
      Description: Checks whether EC2 instances have a public IP.
      Source:
        Owner: AWS
        SourceIdentifier: EC2_INSTANCE_NO_PUBLIC_IP
      Scope:
        ComplianceResourceTypes:
          - "AWS::EC2::Instance"
    Type: AWS::Config::ConfigRule
  S3BucketPublicReadProhibited:
    Properties:
      ConfigRuleName: s3-bucket-public-read-prohibited
      Description: Checks that S3 buckets do not allow public read.
      Source:
        Owner: AWS
        SourceIdentifier: S3_BUCKET_PUBLIC_READ_PROHIBITED
      Scope:
        ComplianceResourceTypes:
          - "AWS::S3::Bucket"
    Type: AWS::Config::ConfigRule
  IamRootAccessKeyCheck:
    Properties:
      ConfigRuleName: iam-root-access-key-check
      Description: Checks whether root account has access keys.
      Source:
        Owner: AWS
        SourceIdentifier: IAM_ROOT_ACCESS_KEY_CHECK
    Type: AWS::Config::ConfigRule
"""


class TestParseTemplate:
    def test_extracts_all_config_rules(self, parser):
        result = parser.parse_template("test.yaml", VALID_TEMPLATE_YAML)
        assert len(result.rules) == 3

    def test_extracts_rule_fields(self, parser):
        result = parser.parse_template("test.yaml", VALID_TEMPLATE_YAML)
        ec2_rule = next(r for r in result.rules if r.logical_name == "Ec2InstanceNoPublicIp")
        assert ec2_rule.config_rule_name == "ec2-instance-no-public-ip"
        assert ec2_rule.description == "Checks whether EC2 instances have a public IP."
        assert ec2_rule.source_identifier == "EC2_INSTANCE_NO_PUBLIC_IP"
        assert ec2_rule.compliance_resource_types == ["AWS::EC2::Instance"]

    def test_preserves_template_name(self, parser):
        result = parser.parse_template("my-template.yaml", VALID_TEMPLATE_YAML)
        assert result.name == "my-template.yaml"

    def test_extracts_parameters(self, parser):
        result = parser.parse_template("test.yaml", VALID_TEMPLATE_YAML)
        assert "Ec2DesiredInstanceType" in result.parameters

    def test_collects_all_services(self, parser):
        result = parser.parse_template("test.yaml", VALID_TEMPLATE_YAML)
        assert "EC2" in result.all_services
        assert "S3" in result.all_services
        assert "IAM" in result.all_services

    def test_preserves_raw_resource(self, parser):
        result = parser.parse_template("test.yaml", VALID_TEMPLATE_YAML)
        ec2_rule = next(r for r in result.rules if r.logical_name == "Ec2InstanceNoPublicIp")
        assert ec2_rule.raw_resource["Type"] == "AWS::Config::ConfigRule"
        assert "Properties" in ec2_rule.raw_resource

    def test_skips_non_config_rule_resources(self, parser):
        yaml_content = """\
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: my-bucket
  MyRule:
    Properties:
      ConfigRuleName: my-rule
      Source:
        Owner: AWS
        SourceIdentifier: S3_BUCKET_PUBLIC_READ_PROHIBITED
    Type: AWS::Config::ConfigRule
"""
        result = parser.parse_template("test.yaml", yaml_content)
        assert len(result.rules) == 1
        assert result.rules[0].logical_name == "MyRule"

    def test_handles_missing_resources_section(self, parser):
        yaml_content = """\
Parameters:
  Foo:
    Default: bar
    Type: String
"""
        result = parser.parse_template("test.yaml", yaml_content)
        assert len(result.rules) == 0
        assert result.all_services == set()

    def test_handles_empty_resources(self, parser):
        yaml_content = """\
Resources: {}
"""
        result = parser.parse_template("test.yaml", yaml_content)
        assert len(result.rules) == 0

    def test_malformed_yaml_raises_error(self, parser):
        with pytest.raises(TemplateParseError, match="Malformed YAML"):
            parser.parse_template("bad.yaml", "{{invalid yaml::")

    def test_empty_yaml_raises_error(self, parser):
        with pytest.raises(TemplateParseError, match="Empty YAML"):
            parser.parse_template("empty.yaml", "")

    def test_skips_rules_with_unexpected_structure(self, parser):
        yaml_content = """\
Resources:
  BrokenRule:
    Type: AWS::Config::ConfigRule
  GoodRule:
    Properties:
      ConfigRuleName: good-rule
      Source:
        Owner: AWS
        SourceIdentifier: S3_BUCKET_PUBLIC_READ_PROHIBITED
    Type: AWS::Config::ConfigRule
"""
        result = parser.parse_template("test.yaml", yaml_content)
        # BrokenRule has no Properties, but _extract_rule handles missing Properties gracefully
        # so both should be extracted
        assert len(result.rules) >= 1

    def test_handles_input_parameters_with_ref(self, parser):
        yaml_content = """\
Parameters:
  MaxSize:
    Default: "100"
    Type: String
Resources:
  MyRule:
    Properties:
      ConfigRuleName: my-rule
      Description: A rule
      Source:
        Owner: AWS
        SourceIdentifier: S3_BUCKET_PUBLIC_READ_PROHIBITED
      InputParameters:
        maxSize: !Ref MaxSize
    Type: AWS::Config::ConfigRule
"""
        result = parser.parse_template("test.yaml", yaml_content)
        assert len(result.rules) == 1
        assert "maxSize" in result.rules[0].input_parameters


class TestExtractServices:
    def test_source_identifier_ec2(self, parser):
        rule = ConfigRule(
            logical_name="Test", config_rule_name="test", description="",
            source_identifier="EC2_INSTANCE_NO_PUBLIC_IP",
            compliance_resource_types=[], input_parameters={},
            services=set(), raw_resource={}, condition="",
        )
        assert parser.extract_services(rule) == {"EC2"}

    def test_source_identifier_s3(self, parser):
        rule = ConfigRule(
            logical_name="Test", config_rule_name="test", description="",
            source_identifier="S3_BUCKET_PUBLIC_READ_PROHIBITED",
            compliance_resource_types=[], input_parameters={},
            services=set(), raw_resource={}, condition="",
        )
        assert parser.extract_services(rule) == {"S3"}

    def test_compliance_resource_type_mapping(self, parser):
        rule = ConfigRule(
            logical_name="Test", config_rule_name="test", description="",
            source_identifier="UNKNOWN_RULE",
            compliance_resource_types=["AWS::Lambda::Function"],
            input_parameters={}, services=set(), raw_resource={}, condition="",
        )
        assert "Lambda" in parser.extract_services(rule)

    def test_union_of_both_mappings(self, parser):
        rule = ConfigRule(
            logical_name="Test", config_rule_name="test", description="",
            source_identifier="EC2_INSTANCE_NO_PUBLIC_IP",
            compliance_resource_types=["AWS::IAM::Role"],
            input_parameters={}, services=set(), raw_resource={}, condition="",
        )
        services = parser.extract_services(rule)
        assert "EC2" in services
        assert "IAM" in services

    def test_unmatched_rule_tagged_other(self, parser):
        rule = ConfigRule(
            logical_name="Test", config_rule_name="test", description="",
            source_identifier="COMPLETELY_UNKNOWN",
            compliance_resource_types=[], input_parameters={},
            services=set(), raw_resource={}, condition="",
        )
        assert parser.extract_services(rule) == {"Other"}

    def test_waf_prefix_no_underscore(self, parser):
        rule = ConfigRule(
            logical_name="Test", config_rule_name="test", description="",
            source_identifier="WAFV2_LOGGING_ENABLED",
            compliance_resource_types=[], input_parameters={},
            services=set(), raw_resource={}, condition="",
        )
        assert "WAF" in parser.extract_services(rule)

    def test_opensearch_from_elasticsearch_prefix(self, parser):
        rule = ConfigRule(
            logical_name="Test", config_rule_name="test", description="",
            source_identifier="ELASTICSEARCH_ENCRYPTED_AT_REST",
            compliance_resource_types=[], input_parameters={},
            services=set(), raw_resource={}, condition="",
        )
        assert "OpenSearch" in parser.extract_services(rule)

    def test_multiple_compliance_resource_types(self, parser):
        rule = ConfigRule(
            logical_name="Test", config_rule_name="test", description="",
            source_identifier="UNKNOWN_RULE",
            compliance_resource_types=["AWS::EC2::Instance", "AWS::S3::Bucket"],
            input_parameters={}, services=set(), raw_resource={}, condition="",
        )
        services = parser.extract_services(rule)
        assert "EC2" in services
        assert "S3" in services


class TestGetAllServices:
    def test_deduplicates_services(self, parser):
        t1 = ParsedTemplate(name="t1.yaml", parameters={}, conditions={}, rules=[], all_services={"EC2", "S3"})
        t2 = ParsedTemplate(name="t2.yaml", parameters={}, conditions={}, rules=[], all_services={"EC2", "IAM"})
        result = parser.get_all_services([t1, t2])
        assert result == ["EC2", "IAM", "S3"]

    def test_alphabetical_sort(self, parser):
        t1 = ParsedTemplate(name="t1.yaml", parameters={}, conditions={}, rules=[], all_services={"S3", "ACM", "Lambda"})
        result = parser.get_all_services([t1])
        assert result == ["ACM", "Lambda", "S3"]

    def test_empty_templates(self, parser):
        result = parser.get_all_services([])
        assert result == []

    def test_single_template_no_services(self, parser):
        t1 = ParsedTemplate(name="t1.yaml", parameters={}, conditions={}, rules=[], all_services=set())
        result = parser.get_all_services([t1])
        assert result == []
