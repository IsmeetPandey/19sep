#!/usr/bin/env python3
"""Detect potentially breaking changes between OpenAPI JSON documents."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HTTP_METHODS = {"get", "put", "post", "patch", "delete", "options", "head", "trace"}


@dataclass(frozen=True)
class Change:
    kind: str
    location: str
    detail: str

    @property
    def breaking(self) -> bool:
        return self.kind.startswith("BREAKING")

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "breaking": self.breaking}


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read OpenAPI JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("paths"), dict):
        raise ValueError("document must be an OpenAPI JSON object with a 'paths' object")
    if data.get("openapi") is None and data.get("swagger") is None:
        raise ValueError("document must declare 'openapi' or 'swagger'")
    return data


def _parameters(path_item: dict[str, Any], operation: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Return effective parameters; operation-level entries override path-level entries."""
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for source in (path_item.get("parameters", []), operation.get("parameters", [])):
        if not isinstance(source, list):
            continue
        for parameter in source:
            if not isinstance(parameter, dict):
                continue
            key = (str(parameter.get("in", "")), str(parameter.get("name", "")))
            result[key] = parameter
    return result


def compare(old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    changes: list[Change] = []
    old_paths, new_paths = old["paths"], new["paths"]

    for path in sorted(old_paths.keys() - new_paths.keys()):
        changes.append(Change("BREAKING: removed path", path, "endpoint no longer exists"))
    for path in sorted(new_paths.keys() - old_paths.keys()):
        changes.append(Change("ADDED: path", path, "new endpoint"))

    for path in sorted(old_paths.keys() & new_paths.keys()):
        o_item, n_item = old_paths[path], new_paths[path]
        if not isinstance(o_item, dict) or not isinstance(n_item, dict):
            continue
        old_methods = HTTP_METHODS & o_item.keys()
        new_methods = HTTP_METHODS & n_item.keys()
        for method in sorted(old_methods - new_methods):
            changes.append(Change("BREAKING: removed operation", f"{method.upper()} {path}", "operation no longer exists"))
        for method in sorted(new_methods - old_methods):
            changes.append(Change("ADDED: operation", f"{method.upper()} {path}", "new operation"))
        for method in sorted(old_methods & new_methods):
            loc = f"{method.upper()} {path}"
            o_op, n_op = o_item[method], n_item[method]
            if not isinstance(o_op, dict) or not isinstance(n_op, dict):
                continue
            _compare_parameters(o_item, o_op, n_item, n_op, loc, changes)
            _compare_request_body(o_op, n_op, loc, changes)
            _compare_responses(o_op, n_op, loc, changes)
    return changes


def _compare_parameters(
    old_item: dict[str, Any],
    old_op: dict[str, Any],
    new_item: dict[str, Any],
    new_op: dict[str, Any],
    loc: str,
    changes: list[Change],
) -> None:
    old_params = _parameters(old_item, old_op)
    new_params = _parameters(new_item, new_op)
    for parameter in sorted(old_params.keys() - new_params.keys()):
        changes.append(
            Change(
                "BREAKING: removed parameter",
                loc,
                f"{parameter[0]} parameter '{parameter[1]}' was removed",
            )
        )
    for parameter in sorted(old_params.keys() & new_params.keys()):
        old_required = old_params[parameter].get("required") is True
        new_required = new_params[parameter].get("required") is True
        if not old_required and new_required:
            changes.append(
                Change(
                    "BREAKING: required parameter",
                    loc,
                    f"existing {parameter[0]} parameter '{parameter[1]}' became required",
                )
            )
    for parameter in sorted(new_params.keys() - old_params.keys()):
        required = new_params[parameter].get("required") is True
        if required:
            changes.append(
                Change(
                    "BREAKING: required parameter",
                    loc,
                    f"new required {parameter[0]} parameter '{parameter[1]}'",
                )
            )
        else:
            changes.append(
                Change(
                    "ADDED: parameter",
                    loc,
                    f"optional {parameter[0]} parameter '{parameter[1]}'",
                )
            )


def _compare_request_body(old_op: dict[str, Any], new_op: dict[str, Any], loc: str, changes: list[Change]) -> None:
    old_body, new_body = old_op.get("requestBody"), new_op.get("requestBody")
    if old_body and not new_body:
        changes.append(Change("BREAKING: removed request body", loc, "request body was removed"))
    if not old_body and isinstance(new_body, dict) and new_body.get("required"):
        changes.append(Change("BREAKING: required request body", loc, "request body was introduced as required"))
    if isinstance(old_body, dict) and isinstance(new_body, dict):
        if not old_body.get("required") and new_body.get("required"):
            changes.append(Change("BREAKING: request body required", loc, "request body changed from optional to required"))


def _compare_responses(old_op: dict[str, Any], new_op: dict[str, Any], loc: str, changes: list[Change]) -> None:
    old_resp = old_op.get("responses", {})
    new_resp = new_op.get("responses", {})
    if not isinstance(old_resp, dict) or not isinstance(new_resp, dict):
        return
    for code in sorted(old_resp.keys() - new_resp.keys()):
        changes.append(Change("BREAKING: removed response", loc, f"response '{code}' was removed"))
    for code in sorted(new_resp.keys() - old_resp.keys()):
        changes.append(Change("ADDED: response", loc, f"response '{code}' was added"))


def render_json(changes: list[Change]) -> str:
    payload = {
        "summary": {
            "breaking": sum(change.breaking for change in changes),
            "changes": len(changes),
        },
        "changes": [change.as_dict() for change in changes],
    }
    return json.dumps(payload, indent=2, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="apiguard",
        description="Find breaking changes between OpenAPI JSON specs.",
    )
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--fail-on",
        choices=("breaking", "change"),
        default="breaking",
        help="exit 1 on breaking changes or on any detected change (default: breaking)",
    )
    args = parser.parse_args(argv)

    try:
        changes = compare(load(args.old), load(args.new))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(render_json(changes))
    elif not changes:
        print("No API surface changes detected.")
    else:
        for change in changes:
            print(f"{change.kind} | {change.location} | {change.detail}")

    should_fail = bool(changes) if args.fail_on == "change" else any(change.breaking for change in changes)
    return 1 if should_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
