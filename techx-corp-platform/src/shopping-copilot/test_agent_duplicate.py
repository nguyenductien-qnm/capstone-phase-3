import json
import unittest

from agent import _duplicate_tool_fallback


class DuplicateToolFallbackTest(unittest.TestCase):
    def test_formats_search_results_instead_of_exposing_json(self):
        out = json.dumps({
            "status": "ok",
            "products": [
                {"name": "Explorascope", "price": "$99.00"},
                {"name": "Astrograph", "price": "$199.00"},
            ],
        })
        text = _duplicate_tool_fallback("search_products", out, "Cho mình xem kính")
        self.assertIn("Explorascope", text)
        self.assertIn("$99.00", text)
        self.assertNotIn('"products"', text)


if __name__ == "__main__":
    unittest.main()
