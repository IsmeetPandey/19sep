import unittest
from apiguard import compare

BASE = {
    "openapi": "3.0.0",
    "paths": {
        "/users": {
            "get": {
                "parameters": [{"name": "limit", "in": "query", "required": False}],
                "responses": {"200": {"description": "ok"}},
            }
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

    def test_removed_response_is_breaking(self):
        new = {"openapi": "3.0.0", "paths": {"/users": {"get": {"parameters": BASE["paths"]["/users"]["get"]["parameters"], "responses": {}}}}}
        changes = compare(BASE, new)
        self.assertTrue(any(c.kind == "BREAKING: removed response" for c in changes))

if __name__ == "__main__":
    unittest.main()
