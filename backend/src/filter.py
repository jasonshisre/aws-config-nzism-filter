"""Template Filter - filters config rules based on selected AWS services."""

import json
from dataclasses import dataclass

from ruamel.yaml.comments import TaggedScalar

from src.parser import ConfigRule, ParsedTemplate


@dataclass
class FilteredTemplate:
    name: str                      # Original template name
    parameters: dict               # Filtered parameters (only referenced ones)
    conditions: dict               # Filtered conditions (only referenced ones)
    rules: list[ConfigRule]        # Filtered config rules
    is_empty: bool                 # True if no rules matched


class TemplateFilter:
    """Filters config rules based on selected AWS services."""

    def filter_template(
        self, template: ParsedTemplate, selected_services: set[str]
    ) -> FilteredTemplate:
        """Filter a parsed template to include only rules matching selected services.

        A rule is included if the intersection of its services and the selected
        services is non-empty.  When no services are selected the result is an
        empty FilteredTemplate.
        """
        if not selected_services:
            return FilteredTemplate(
                name=template.name,
                parameters={},
                conditions={},
                rules=[],
                is_empty=True,
            )

        matched_rules = [
            rule for rule in template.rules
            if rule.services & selected_services
        ]

        # Collect conditions referenced by matched rules
        filtered_conditions = self.filter_conditions(template.conditions, matched_rules)

        # Collect parameters referenced by matched rules' InputParameters
        # AND parameters referenced by the included conditions
        filtered_params = self.filter_parameters(
            template.parameters, matched_rules, filtered_conditions
        )

        return FilteredTemplate(
            name=template.name,
            parameters=filtered_params,
            conditions=filtered_conditions,
            rules=matched_rules,
            is_empty=len(matched_rules) == 0,
        )

    def filter_conditions(
        self, conditions: dict, rules: list[ConfigRule]
    ) -> dict:
        """Return only conditions that are referenced by the included rules.

        Each rule may have a ``condition`` field (resource-level Condition key)
        that references a condition by name.
        """
        referenced: set[str] = set()
        for rule in rules:
            if rule.condition:
                referenced.add(rule.condition)

        return {
            name: defn
            for name, defn in conditions.items()
            if name in referenced
        }

    def filter_parameters(
        self, parameters: dict, rules: list[ConfigRule], conditions: dict
    ) -> dict:
        """Return only parameters that are referenced by included rules or conditions.

        Scans:
        1. Each rule's ``input_parameters`` values for ``!Ref`` tagged scalars
        2. Each condition's body for ``Ref`` intrinsic function references
        """
        referenced: set[str] = set()

        # From rule InputParameters (!Ref tags)
        for rule in rules:
            for value in rule.input_parameters.values():
                if isinstance(value, TaggedScalar) and value.tag.value == "!Ref":
                    referenced.add(str(value))

        # From condition bodies (Ref intrinsic functions)
        for _name, defn in conditions.items():
            self._collect_refs(defn, referenced)

        return {
            name: defn
            for name, defn in parameters.items()
            if name in referenced
        }

    def _collect_refs(self, obj: object, refs: set[str]) -> None:
        """Recursively scan a condition definition for Ref references."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "Ref" and isinstance(value, str):
                    refs.add(value)
                else:
                    self._collect_refs(value, refs)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_refs(item, refs)
