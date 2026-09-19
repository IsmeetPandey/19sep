# 🛡️ APIGuard

**Catch breaking OpenAPI changes before they reach consumers.**

APIGuard is a dependency-free Python CLI that compares two OpenAPI JSON documents and reports API-surface changes with a non-zero exit code when a breaking change is detected.

## Why

API changes can break generated clients, integrations, and downstream services even when application tests are green. APIGuard is designed for a fast CI preflight: compare the last known contract with the proposed contract and fail the build when compatibility is reduced.

## Quick start

```bash
python apiguard.py old.json new.json
```

Exit codes:

- `0` — no changes, or only additive/non-breaking changes.
- `1` — at least one breaking change was detected.
- `2` — invalid input or an unreadable specification.

## Current checks

- Removed paths
- Removed HTTP operations
- Removed parameters
- Existing optional parameters becoming required
- Newly introduced required parameters
- Removed responses
- Added paths, operations, parameters, and responses are reported separately

## Example

```text
BREAKING: required parameter | GET /users | new required query parameter 'limit'
```

That makes APIGuard suitable for a simple CI guardrail:

```bash
python apiguard.py openapi.previous.json openapi.json
```

## Design

The first release intentionally uses only the Python standard library. The comparison engine is deterministic and separated from CLI I/O, making the core easy to test and extend.

### Non-goals

This version does not claim full semantic OpenAPI compatibility analysis. Schema-level compatibility, `$ref` resolution, media-type changes, and YAML parsing are deliberate future extensions rather than hidden heuristics.

## Development

```bash
python -m unittest -v
```

## Security

APIGuard reads the two files supplied by the caller and does not execute specification content or make network requests. Keep untrusted specification files in ordinary read-only CI workspaces where possible.

## Roadmap

- Recursive request/response schema compatibility
- `$ref` resolution with cycle protection
- Content-type compatibility checks
- GitHub Actions example
- Machine-readable JSON output
- Configurable compatibility policy
