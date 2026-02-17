"""Template Generator - generates valid YAML conformance pack templates from filtered data."""

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from src.filter import FilteredTemplate


class TemplateGenerator:
    """Generates valid YAML conformance pack templates from filtered data."""

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.preserve_quotes = True

    def generate_yaml(self, filtered: FilteredTemplate) -> str:
        """Generate a valid YAML conformance pack template from filtered data.

        Builds the output document with a commented summary header, then
        Parameters (if any), Conditions (if any), and Resources, using each
        rule's ``raw_resource`` dict to preserve original structure and key ordering.
        """
        doc = CommentedMap()

        if filtered.parameters:
            doc["Parameters"] = CommentedMap(filtered.parameters)

        if filtered.conditions:
            doc["Conditions"] = CommentedMap(filtered.conditions)

        resources = CommentedMap()
        for rule in filtered.rules:
            resources[rule.logical_name] = rule.raw_resource
        doc["Resources"] = resources

        stream = StringIO()
        self._yaml.dump(doc, stream)
        yaml_body = stream.getvalue()

        header = self._generate_summary_header(filtered)
        return header + yaml_body

    def _generate_summary_header(self, filtered: FilteredTemplate) -> str:
        """Build a YAML comment block summarising included rules grouped by service."""
        # Group rules by service (a rule may appear under multiple services)
        service_rules: dict[str, list[str]] = defaultdict(list)
        for rule in filtered.rules:
            for svc in sorted(rule.services):
                service_rules[svc].append(rule.config_rule_name)

        nzst = timezone(timedelta(hours=12))
        timestamp = datetime.now(nzst).strftime("%Y-%m-%d %H:%M:%S NZST")

        lines = [
            f"# NZISM Config Filter — Template Summary",
            f"# Source: {filtered.name}",
            f"# Generated: {timestamp}",
            f"# Total service types: {len(service_rules)}",
            f"# Total rules: {len(filtered.rules)}",
        ]

        for svc in sorted(service_rules):
            rules = service_rules[svc]
            lines.append(f"# {svc} ({len(rules)} rules):")
            for rule_name in sorted(rules):
                lines.append(f"#   - {rule_name}")

        lines.append("#")
        lines.append("")

        return "\n".join(lines) + "\n"

    def get_download_filename(self, original_name: str) -> str:
        """Generate download filename with ``-filtered`` suffix.

        Inserts ``-filtered`` before the ``.yaml`` extension.
        E.g. ``"Operational-Best-Practices-for-NZISM-Extension.yaml"``
        becomes ``"Operational-Best-Practices-for-NZISM-Extension-filtered.yaml"``.
        """
        if original_name.endswith(".yaml"):
            return original_name[: -len(".yaml")] + "-filtered.yaml"
        return original_name + "-filtered"

    def generate_explanation(
        self, matched_count: int, total_count: int,
    ) -> str:
        """Produce a human-readable explanation of the filtering result.

        Returns a string like ``"42 of 150 rules matched your selected services"``.
        """
        return f"{matched_count} of {total_count} rules matched your selected services"
