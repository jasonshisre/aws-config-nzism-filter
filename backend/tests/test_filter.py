"""Unit tests for TemplateFilter."""

import pytest
from io import StringIO
from ruamel.yaml import YAML
from ruamel.yaml.comments import TaggedScalar

from src.filter import FilteredTemplate, TemplateFilter
from src.parser import ConfigRule, ParsedTemplate, TemplateParser


@pytest.fixture
def tf():
    return TemplateFilter()


def _make_rule(
    logical_name: str = "TestRule",
    services: set[str] | None = None,
    input_parameters: dict | None = None,
    condition: str = "",
) -> ConfigRule:
    """Helper to build a ConfigRule with sensible defaults."""
    return ConfigRule(
        logical_name=logical_name,
        config_rule_name=logical_name.lower(),
        description="desc",
        source_identifier="TEST_RULE",
        compliance_resource_types=[],
        input_parameters=input_parameters or {},
        services=services or {"EC2"},
        raw_resource={},
        condition=condition,
    )


def _make_ref(param_name: str) -> TaggedScalar:
    """Create a ruamel.yaml TaggedScalar mimicking !Ref."""
    ts = TaggedScalar(value=param_name, tag="!Ref")
    return ts


# ── filter_template ──────────────────────────────────────────────────


class TestFilterTemplate:
    def test_includes_matching_rules(self, tf):
        rule_ec2 = _make_rule("Ec2Rule", services={"EC2"})
        rule_s3 = _make_rule("S3Rule", services={"S3"})
        template = ParsedTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule_ec2, rule_s3],
            all_services={"EC2", "S3"},
        )
        result = tf.filter_template(template, {"EC2"})
        assert len(result.rules) == 1
        assert result.rules[0].logical_name == "Ec2Rule"
        assert result.is_empty is False

    def test_excludes_non_matching_rules(self, tf):
        rule = _make_rule("IamRule", services={"IAM"})
        template = ParsedTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule],
            all_services={"IAM"},
        )
        result = tf.filter_template(template, {"EC2"})
        assert len(result.rules) == 0
        assert result.is_empty is True

    def test_multi_service_rule_included_if_any_match(self, tf):
        rule = _make_rule("MultiRule", services={"EC2", "IAM"})
        template = ParsedTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule],
            all_services={"EC2", "IAM"},
        )
        result = tf.filter_template(template, {"IAM"})
        assert len(result.rules) == 1

    def test_empty_selection_produces_empty_output(self, tf):
        rule = _make_rule("Ec2Rule", services={"EC2"})
        template = ParsedTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule],
            all_services={"EC2"},
        )
        result = tf.filter_template(template, set())
        assert result.rules == []
        assert result.parameters == {}
        assert result.is_empty is True

    def test_no_matching_rules_marks_empty(self, tf):
        rule = _make_rule("S3Rule", services={"S3"})
        template = ParsedTemplate(
            name="t.yaml", parameters={}, conditions={}, rules=[rule],
            all_services={"S3"},
        )
        result = tf.filter_template(template, {"Lambda"})
        assert result.is_empty is True

    def test_preserves_template_name(self, tf):
        template = ParsedTemplate(
            name="my-template.yaml", parameters={}, conditions={}, rules=[],
            all_services=set(),
        )
        result = tf.filter_template(template, {"EC2"})
        assert result.name == "my-template.yaml"


# ── filter_parameters ────────────────────────────────────────────────


class TestFilterParameters:
    def test_keeps_referenced_parameters(self, tf):
        ref = _make_ref("MaxSize")
        rule = _make_rule(input_parameters={"maxSize": ref})
        params = {"MaxSize": {"Default": "100", "Type": "String"}}
        result = tf.filter_parameters(params, [rule], {})
        assert "MaxSize" in result

    def test_removes_unreferenced_parameters(self, tf):
        ref = _make_ref("MaxSize")
        rule = _make_rule(input_parameters={"maxSize": ref})
        params = {
            "MaxSize": {"Default": "100", "Type": "String"},
            "Unused": {"Default": "x", "Type": "String"},
        }
        result = tf.filter_parameters(params, [rule], {})
        assert "MaxSize" in result
        assert "Unused" not in result

    def test_plain_string_values_not_treated_as_refs(self, tf):
        rule = _make_rule(input_parameters={"enabled": "true"})
        params = {"true": {"Default": "y", "Type": "String"}}
        result = tf.filter_parameters(params, [rule], {})
        assert result == {}

    def test_no_rules_returns_empty_params(self, tf):
        params = {"Foo": {"Default": "bar", "Type": "String"}}
        result = tf.filter_parameters(params, [], {})
        assert result == {}

    def test_multiple_rules_reference_same_param(self, tf):
        ref1 = _make_ref("SharedParam")
        ref2 = _make_ref("SharedParam")
        rule1 = _make_rule("R1", input_parameters={"a": ref1})
        rule2 = _make_rule("R2", input_parameters={"b": ref2})
        params = {"SharedParam": {"Default": "v", "Type": "String"}}
        result = tf.filter_parameters(params, [rule1, rule2], {})
        assert "SharedParam" in result

    def test_multiple_refs_across_rules(self, tf):
        ref_a = _make_ref("ParamA")
        ref_b = _make_ref("ParamB")
        rule1 = _make_rule("R1", input_parameters={"x": ref_a})
        rule2 = _make_rule("R2", input_parameters={"y": ref_b})
        params = {
            "ParamA": {"Default": "a", "Type": "String"},
            "ParamB": {"Default": "b", "Type": "String"},
            "ParamC": {"Default": "c", "Type": "String"},
        }
        result = tf.filter_parameters(params, [rule1, rule2], {})
        assert set(result.keys()) == {"ParamA", "ParamB"}


# ── Integration with real YAML parsing ───────────────────────────────


class TestFilterIntegration:
    """Test filter with templates produced by the real parser."""

    YAML_WITH_REFS = """\
Parameters:
  MaxSize:
    Default: "100"
    Type: String
  Unused:
    Default: "x"
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

    def test_filter_with_parsed_template(self):
        parser = TemplateParser()
        template = parser.parse_template("test.yaml", self.YAML_WITH_REFS)
        tf = TemplateFilter()

        result = tf.filter_template(template, {"S3"})
        assert len(result.rules) == 1
        assert result.rules[0].logical_name == "S3Rule"
        # Only MaxSize should survive (referenced by S3Rule)
        assert "MaxSize" in result.parameters
        assert "Unused" not in result.parameters

    def test_filter_ec2_excludes_s3_params(self):
        parser = TemplateParser()
        template = parser.parse_template("test.yaml", self.YAML_WITH_REFS)
        tf = TemplateFilter()

        result = tf.filter_template(template, {"EC2"})
        assert len(result.rules) == 1
        assert result.rules[0].logical_name == "Ec2Rule"
        # EC2 rule has no InputParameters, so no params should be included
        assert result.parameters == {}
