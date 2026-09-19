#!/usr/bin/env python3
"""Detect potentially breaking changes between OpenAPI JSON documents."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HTTP_METHODS = {"get", "put", "post", "patch", "delete", "options", "head", "trace"}

@dataclass(frozen=True)
class Change:
    kind: str
    location: str
    detail: str

    @property
    def breaking(self) -> bool:
        return self.kind.startswith("BREAKING")


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read OpenAPI JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("paths"), dict):
        raise ValueError("document must be an OpenAPI JSON object with a 'paths' object")
    if data.get("openapi") is None and data.get("swagger") is None:
        raise ValueError("document must declare 'openapi' or 'swagger'")
    return data


def compare(old: dict, new: dict) -> list[Change]:
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
            _compare_parameters(o_op, n_op, loc, changes)
            _compare_request_body(o_op, n_op, loc, changes)
            _compare_responses(o_op, n_op, loc, changes)
    return changes


def _compare_parameters(old_op: dict, new_op: dict, loc: str, changes: list[Change]) -> None:
    def key(p: dict) -> tuple[str, str]:
        return (str(p.get("in", "")), str(p.get("name", "")))
    old_params = {key(p): p for p in old_op.get("parameters", []) if isinstance(p, dict)}
    new_params = {key(p): p for p in new_op.get("parameters", []) if isinstance(p, dict)}
    for p in sorted(old_params.keys() - new_params.keys()):
        changes.append(Change("BREAKING: removed parameter", loc, f"{p[0]} parameter '{p[1]}' was removed"))
    for p in sorted(old_params.keys() & new_params.keys()):
        if old_params[p].get("required") is not True and new_params[p].get("required") is True:
            changes.append(Change("BREAKING: required parameter", loc, f"existing {p[0]} parameter '{p[1]}' became required"))
    for p in sorted(new_params.keys() - old_params.keys()):
        if new_params[p].get("required") is True:
            changes.append(Change("BREAKING: required parameter", loc, f"new required {p[0]} parameter '{p[1]}'"))
        else:
            changes.append(Change("ADDED: parameter", loc, f"optional {p[0]} parameter '{p[1]}'"))


def _compare_request_body(old_op: dict, new_op: dict, loc: str, changes: list[Change]) -> None:
    old_body, new_body = old_op.get("requestBody"), new_op.get("requestBody")
    if old_body and not new_body:
        changes.append(Change("BREAKING: removed request body", loc, "request body was removed"))
    if not old_body and isinstance(new_body, dict) and new_body.get("required"):
        changes.append(Change("BREAKING: required request body", loc, "request body was introduced as required"))
    if isinstance(old_body, dict) and isinstance(new_body, dict) and not old_body.get("required") and new_body.get("required"):
        changes.append(Change("BREAKING: request body required", loc, "request body changed from optional to required"))


def _compare_responses(old_op: dict, new_op: dict, loc: str, changes: list[Change]) -> None:
    old_resp, new_resp = old_op.get("responses", {}), new_op.get("responses", {})
    for code in sorted(old_resp.keys() - new_resp.keys()):
        changes.append(Change("BREAKING: removed response", loc, f"response '{code}' was removed"))
    for code in sorted(new_resp.keys() - old_resp.keys()):
        changes.append(Change("ADDED: response", loc, f"response '{code}' was added"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apiguard", description="Find breaking changes between OpenAPI JSON specs.")
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    args = parser.parse_args(argv)
    try:
        changes = compare(load(args.old), load(args.new))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not changes:
        print("No API surface changes detected.")
        return 0
    for change in changes:
        print(f"{change.kind} | {change.location} | {change.detail}")
    return 1 if any(c.breaking for c in changes) else 0

if __name__ == "__main__":
    raise SystemExit(main())
