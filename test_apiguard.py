import json
import tempfile
import unittest
from pathlib import Path

from apiguard import compare, load, render_json


BASE = {
    "openapi": "3.0.0",
    "paths": {
        "/users": {
            "parameters": [{"name": "tenant", "in": "header", "required": False}],
            "get": {
                "parameters": [{"name": "limit", "in": "query", "required": False}],
                "responses": {"200": {"description": "ok"}},
            },
        }
    },
}


class ApiGuardTests(unittest.TestCase):
    def test_removed_path_is_breaking(self):
        changes = compare(BASE, {"openapi": "3.0.0", "paths": {}})
        self.assertTrue(any(c.kind.startswith("BREAKING") for c in changes))

    def test_optional_parameter_is_not_breaking(self):
        new = {"openapi": "3.0.0", "paths": {"/users": {"get": {"parameters": BASE["paths"]["/users"]["get"]["parameters"] + [{"name": "sort", "in": "query", "required": False}], "responses": {"200": {"description": "ok"}}}}}}
        changes = compare(BASE, new)
        self.assertTrue(any(c.kind == "ADDED: parameter" for c in changes))
        self.assertFalse(any(c.breaking for c in changes))

    def test_required_parameter_is_breaking(self):
        new = {"openapi": "3.0.0", "paths": {"/users": {"get": {"parameters": [{"name": "limit", "in": "query", "required": True}], "responses": {"200": {"description": "ok"}}}}}}
        changes = compare(BASE, new)
        self.assertTrue(any(c.kind == "BREAKING: required parameter" for c in changes))

    def test_path_level_parameter_is_checked(self):
        new = {"openapi": "3.0.0", "paths": {"/users": {"parameters": [], "get": BASE["paths"]["/users"]["get"]}}}
        changes = compare(BASE, new)
        self.assertTrue(any(c.kind == "BREAKING: removed parameter" for c in changes))

    def test_removed_response_is_breaking(self):
        new = {"openapi": "3.0.0", "paths": {"/users": {"get": {"parameters": BASE["paths"]["/users"]["get"]["parameters"], "responses": {}}}}}
        changes = compare(BASE, new)
        self.assertTrue(any(c.kind == "BREAKING: removed response" for c in changes))

    def test_required_request_body_is_breaking(self):
        old = {"openapi": "3.0.0", "paths": {"/users": {"post": {"requestBody": {"required": False}, "responses": {"200": {}}}}}}
        new = {"openapi": "3.0.0", "paths": {"/users": {"post": {"requestBody": {"required": True}, "responses": {"200": {}}}}}}
        changes = compare(old, new)
        self.assertTrue(any(c.kind == "BREAKING: request body required" for c in changes))

    def test_json_output_is_machine_readable(self):
        payload = json.loads(render_json(compare(BASE, {"openapi": "3.0.0", "paths": {}})))
        self.assertEqual(payload["summary"]["breaking"], 1)
        self.assertTrue(payload["changes"][0]["breaking"])

    def test_invalid_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                load(path)


if __name__ == "__main__":
    unittest.main()
