# 🛡️ APIGuard

**Catch breaking OpenAPI changes before they reach consumers.**

APIGuard is a dependency-free Python CLI for fast, deterministic API-contract preflight checks. Compare two OpenAPI JSON documents locally or in CI and get a clear compatibility signal without uploading your specification anywhere.

## Why APIGuard?

A small contract change can break generated clients, integrations, or downstream services even when application tests are green. Larger tools already cover broad API-diff and governance workflows; APIGuard deliberately stays narrow: a zero-dependency, offline-friendly guardrail that is easy to understand, audit, vendor, and run anywhere Python is available.

## Quick start

```bash
python apiguard.py old.json new.json
```

For automation-friendly output:

```bash
python apiguard.py old.json new.json --format json
```

To fail on any detected API-surface change rather than only breaking changes:

```bash
python apiguard.py old.json new.json --fail-on change
```

### Exit codes

- `0` — no changes, or only changes below the selected failure policy.
- `1` — the selected failure policy was triggered.
- `2` — invalid input or an unreadable specification.

## Current checks

- Removed paths
- Removed HTTP operations
- Removed path- or operation-level parameters
- Existing optional parameters becoming required
- Newly introduced required parameters
- Removed request bodies
- Request bodies becoming required
- Removed responses
- Added paths, operations, parameters, and responses are reported separately
- Human-readable text or structured JSON output

## Example

```text
BREAKING: required parameter | GET /users | new required query parameter 'limit'
```

The JSON mode is intended for CI wrappers and other tooling:

```json
{
  "summary": {"breaking": 1, "changes": 1},
  "changes": [
    {
      "kind": "BREAKING: required parameter",
      "location": "GET /users",
      "detail": "new required query parameter 'limit'",
      "breaking": true
    }
  ]
}
```

## Design

The comparison engine is deterministic and separated from CLI I/O. The project intentionally uses only the Python standard library, keeps specification data local, and avoids network access during comparison.

### Scope and non-goals

APIGuard is a focused preflight detector, not a complete OpenAPI semantic-compatibility engine. It does not currently resolve `$ref` graphs, compare recursive schemas, parse YAML, or infer every media-type compatibility rule. Those are explicit future extensions rather than hidden heuristics.

## CI

A GitHub Actions workflow runs the unit suite and Python compilation check on pushes and pull requests to `main`.

You can also use APIGuard directly as a CI gate:

```yaml
- name: Check API contract
  run: python apiguard.py openapi.previous.json openapi.json
```

## Development

```bash
python -m unittest -v
python -m py_compile apiguard.py test_apiguard.py
```

## Security

APIGuard reads only the files supplied by the caller. It does not execute specification content, make network requests, or require credentials. Keep untrusted specification files in ordinary read-only CI workspaces where practical.

## Roadmap

- Recursive request/response schema compatibility
- `$ref` resolution with cycle protection
- Content-type compatibility checks
- SARIF output for code-scanning workflows
- GitHub Action with a copy-paste configuration
- Configurable compatibility policies
