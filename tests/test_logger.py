from __future__ import annotations

from us_quant.logger import resolve_log_output


def test_resolve_log_output_treats_json_format_as_structured_logging():
    format_str, serialize = resolve_log_output("json")

    assert format_str == "{message}"
    assert serialize is True


def test_resolve_log_output_preserves_readable_text_format():
    format_str, serialize = resolve_log_output("{level} | {message}")

    assert format_str == "{level} | {message}"
    assert serialize is False
