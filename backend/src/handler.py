"""Lambda API Handler - REST API endpoints for template fetching, filtering, and generation."""

import json
import logging

from src.fetcher import TemplateFetchError, TemplateFetcher
from src.filter import TemplateFilter
from src.generator import TemplateGenerator
from src.parser import TemplateParseError, TemplateParser

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def _response(status_code: int, body: dict) -> dict:
    """Build an API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def _handle_get_templates() -> dict:
    """GET /api/templates — fetch templates from GitHub, parse, return list and services."""
    fetcher = TemplateFetcher()
    parser = TemplateParser()

    template_files = fetcher.list_nzism_templates()

    parsed_templates = []
    warnings = []

    for tf in template_files:
        try:
            parsed = parser.parse_template(tf.name, tf.content)
            parsed_templates.append(parsed)
        except TemplateParseError as exc:
            warnings.append(str(exc))

    services = parser.get_all_services(parsed_templates)
    templates = [
        {"name": pt.name, "ruleCount": len(pt.rules)}
        for pt in parsed_templates
    ]

    body: dict = {"templates": templates, "services": services}
    if warnings:
        body["warnings"] = warnings

    return _response(200, body)


def _handle_post_filter(body: str | None) -> dict:
    """POST /api/filter — filter templates by selected services, return filtered YAML."""
    if not body:
        return _response(400, {"error": "Request body is required"})

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "Invalid JSON in request body"})

    selected_services = payload.get("selectedServices")
    if not isinstance(selected_services, list):
        return _response(400, {"error": "selectedServices must be a list"})

    selected_set = set(selected_services)

    fetcher = TemplateFetcher()
    parser = TemplateParser()
    template_filter = TemplateFilter()
    generator = TemplateGenerator()

    template_files = fetcher.list_nzism_templates()

    parsed_templates = []
    warnings = []

    for tf in template_files:
        try:
            parsed = parser.parse_template(tf.name, tf.content)
            parsed_templates.append(parsed)
        except TemplateParseError as exc:
            warnings.append(str(exc))

    filtered_templates = []
    for pt in parsed_templates:
        filtered = template_filter.filter_template(pt, selected_set)
        if filtered.is_empty:
            continue
        yaml_output = generator.generate_yaml(filtered)
        filtered_templates.append({
            "name": generator.get_download_filename(pt.name),
            "yaml": yaml_output,
            "ruleCount": len(filtered.rules),
            "originalRuleCount": len(pt.rules),
            "explanation": generator.generate_explanation(
                len(filtered.rules), len(pt.rules),
            ),
        })

    body_out: dict = {"filteredTemplates": filtered_templates}
    if warnings:
        body_out["warnings"] = warnings

    return _response(200, body_out)


def lambda_handler(event: dict, context: object) -> dict:
    """AWS Lambda entry point — routes requests based on HTTP method and path."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")

    # Handle CORS preflight
    if http_method == "OPTIONS":
        return _response(200, {})

    try:
        if http_method == "GET" and path == "/api/templates":
            return _handle_get_templates()

        if http_method == "POST" and path == "/api/filter":
            return _handle_post_filter(event.get("body"))

        return _response(404, {"error": f"Not found: {http_method} {path}"})

    except TemplateFetchError as exc:
        msg = str(exc)
        if "rate limit" in msg.lower():
            return _response(429, {
                "error": "GitHub API rate limit exceeded. Please wait and try again.",
            })
        return _response(502, {"error": msg})

    except Exception as exc:
        logger.exception("Unhandled error in lambda_handler")
        return _response(500, {"error": f"Internal server error: {exc}"})
