"""Unit tests for TemplateGenerator."""

import pytest
from ruamel.yaml import YAML
from io import StringIO

from src.filter import FilteredTemplate
from src.generator import TemplateGenerator
from src.parser import ConfigRule, ParsedTemplate, TemplateParser


@pytest.fixture
def gen():
    return TemplateGenerator()


def _make_rule(
    logical_name: str = "TestRule",
    services: set[str] | None = None,
    raw_resource: dict | None = None,
    condition: str = "",
) -> ConfigRule:
    """Helper to build a ConfigRule with sensible defaults."""
    if raw_resource is None:
        raw_resource = {
            "Properties": {
                "ConfigRuleName": logical_name.lower(),
                "Description": f"Description for {logical_name}",
                "Source": {"Owner": "AWS", "SourceIdentifier": "TEST_RULE"},
            },
            "Type": "AWS::Config::ConfigRule",
        }
    return ConfigRule(
        logical_name=logical_name,
        config_rule_name=logical_name.lower(),
        description=f"Description for {logical_name}",
        source_identifier="TEST_RULE",
        compliance_resource_types=[],
        input_parameters={},
        services=services or {"EC2"},
        raw_resource=raw_resource,
        condition=condition,
    )


# ── generate_yaml ────────────────────────────────────────────────────


class TestGenerateYaml:
    def test_produces_valid_yaml(self, gen):
        rule = _make_rule("Ec2Rule")
        filtered = FilteredTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule], is_empty=False,
        )
        yaml_str = gen.generate_yaml(filtered)
        yaml = YAML()
        data = yaml.load(StringIO(yaml_str))
        assert "Resources" in data

    def test_includes_resources(self, gen):
        rule = _make_rule("Ec2Rule")
        filtered = FilteredTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule], is_empty=False,
        )
        yaml_str = gen.generate_yaml(filtered)
        yaml = YAML()
        data = yaml.load(StringIO(yaml_str))
        assert "Ec2Rule" in data["Resources"]

    def test_includes_parameters_when_present(self, gen):
        rule = _make_rule("Ec2Rule")
        params = {"MaxSize": {"Default": "100", "Type": "String"}}
        filtered = FilteredTemplate(
            name="t.yaml", parameters=params, conditions={}, rules=[rule], is_empty=False,
        )
        yaml_str = gen.generate_yaml(filtered)
        yaml = YAML()
        data = yaml.load(StringIO(yaml_str))
        assert "Parameters" in data
        assert "MaxSize" in data["Parameters"]

    def test_omits_parameters_when_empty(self, gen):
        rule = _make_rule("Ec2Rule")
        filtered = FilteredTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule], is_empty=False,
        )
        yaml_str = gen.generate_yaml(filtered)
        yaml = YAML()
        data = yaml.load(StringIO(yaml_str))
        assert "Parameters" not in data

    def test_preserves_raw_resource_structure(self, gen):
        raw = {
            "Properties": {
                "ConfigRuleName": "ec2-rule",
                "Description": "EC2 rule",
                "Source": {"Owner": "AWS", "SourceIdentifier": "EC2_INSTANCE_NO_PUBLIC_IP"},
                "Scope": {"ComplianceResourceTypes": ["AWS::EC2::Instance"]},
            },
            "Type": "AWS::Config::ConfigRule",
        }
        rule = _make_rule("Ec2Rule", raw_resource=raw)
        filtered = FilteredTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule], is_empty=False,
        )
        yaml_str = gen.generate_yaml(filtered)
        yaml = YAML()
        data = yaml.load(StringIO(yaml_str))
        resource = data["Resources"]["Ec2Rule"]
        assert resource["Type"] == "AWS::Config::ConfigRule"
        assert resource["Properties"]["Source"]["SourceIdentifier"] == "EC2_INSTANCE_NO_PUBLIC_IP"

    def test_multiple_rules_in_output(self, gen):
        rule1 = _make_rule("RuleA")
        rule2 = _make_rule("RuleB")
        filtered = FilteredTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule1, rule2], is_empty=False,
        )
        yaml_str = gen.generate_yaml(filtered)
        yaml = YAML()
        data = yaml.load(StringIO(yaml_str))
        assert "RuleA" in data["Resources"]
        assert "RuleB" in data["Resources"]

    def test_empty_rules_produces_empty_resources(self, gen):
        filtered = FilteredTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[], is_empty=True,
        )
        yaml_str = gen.generate_yaml(filtered)
        yaml = YAML()
        data = yaml.load(StringIO(yaml_str))
        assert data["Resources"] == {} or len(data["Resources"]) == 0

    def test_summary_header_present(self, gen):
        rule = _make_rule("Ec2Rule", services={"EC2"})
        filtered = FilteredTemplate(
            name="my-template.yaml", parameters={}, conditions={}, rules=[rule], is_empty=False,
        )
        yaml_str = gen.generate_yaml(filtered)
        assert yaml_str.startswith("# NZISM Config Filter")
        assert "# Source: my-template.yaml" in yaml_str
        assert "# Generated:" in yaml_str
        assert "NZST" in yaml_str
        assert "# Total service types: 1" in yaml_str
        assert "# Total rules: 1" in yaml_str
        assert "# EC2 (1 rules):" in yaml_str
        assert "#   - ec2rule" in yaml_str


# ── get_download_filename ────────────────────────────────────────────


class TestGetDownloadFilename:
    def test_inserts_filtered_suffix(self, gen):
        result = gen.get_download_filename(
            "Operational-Best-Practices-for-NZISM-Extension.yaml"
        )
        assert result == "Operational-Best-Practices-for-NZISM-Extension-filtered.yaml"

    def test_simple_yaml_filename(self, gen):
        assert gen.get_download_filename("template.yaml") == "template-filtered.yaml"

    def test_no_yaml_extension(self, gen):
        assert gen.get_download_filename("template") == "template-filtered"

    def test_preserves_path_structure(self, gen):
        result = gen.get_download_filename("some-long-name.yaml")
        assert result == "some-long-name-filtered.yaml"


# ── generate_explanation ─────────────────────────────────────────────


class TestGenerateExplanation:
    def test_typical_explanation(self, gen):
        result = gen.generate_explanation(42, 150)
        assert result == "42 of 150 rules matched your selected services"

    def test_zero_matched(self, gen):
        result = gen.generate_explanation(0, 100)
        assert result == "0 of 100 rules matched your selected services"

    def test_all_matched(self, gen):
        result = gen.generate_explanation(50, 50)
        assert result == "50 of 50 rules matched your selected services"


# ── Integration with parser + filter ─────────────────────────────────


class TestGeneratorIntegration:
    """Test generator with templates produced by the real parser and filter."""

    YAML_TEMPLATE = """\
Parameters:
  MaxSize:
    Default: "100"
    Type: String
Resources:
  S3Rule:
    Properties:
      ConfigRuleName: s3-rule
      Description: S3 rule
      Source:
        Owner: AWS
        SourceIdentifier: S3_BUCKET_PUBLIC_READ_PROHIBITED
      Scope:
        ComplianceResourceTypes:
          - "AWS::S3::Bucket"
      InputParameters:
        maxSize: !Ref MaxSize
    Type: AWS::Config::ConfigRule
  Ec2Rule:
    Properties:
      ConfigRuleName: ec2-rule
      Description: EC2 rule
      Source:
        Owner: AWS
        SourceIdentifier: EC2_INSTANCE_NO_PUBLIC_IP
      Scope:
        ComplianceResourceTypes:
          - "AWS::EC2::Instance"
    Type: AWS::Config::ConfigRule
"""

    def test_round_trip_parse_filter_generate(self):
        from src.filter import TemplateFilter

        parser = TemplateParser()
        template = parser.parse_template("test.yaml", self.YAML_TEMPLATE)
        tf = TemplateFilter()
        filtered = tf.filter_template(template, {"S3"})
        gen = TemplateGenerator()
        yaml_str = gen.generate_yaml(filtered)

        # Parse the generated YAML back
        yaml = YAML()
        data = yaml.load(StringIO(yaml_str))
        assert "S3Rule" in data["Resources"]
        assert "Ec2Rule" not in data["Resources"]
        assert "MaxSize" in data["Parameters"]

    def test_generated_yaml_is_reparseable(self):
        from src.filter import TemplateFilter

        parser = TemplateParser()
        template = parser.parse_template("test.yaml", self.YAML_TEMPLATE)
        tf = TemplateFilter()
        filtered = tf.filter_template(template, {"S3"})
        gen = TemplateGenerator()
        yaml_str = gen.generate_yaml(filtered)

        # Re-parse with our own parser
        reparsed = parser.parse_template("filtered.yaml", yaml_str)
        assert len(reparsed.rules) == 1
        assert reparsed.rules[0].logical_name == "S3Rule"
