import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pb"))

from memory import (
    _parse_semantic_results, _scope_hash, _vector_bytes,
    extract_user_preferences, format_memory_for_prompt,
)


class SemanticCacheHelpersTest(unittest.TestCase):
    def test_parses_valkey_search_rows(self):
        raw = [1, "copilot:semantic:item:key", [
            "question", "Giá bao nhiêu?",
            "answer", "100 USD",
            "distance", "0.12",
        ]]
        self.assertEqual(
            _parse_semantic_results(raw),
            [("Giá bao nhiêu?", "100 USD", 0.12)],
        )

    def test_scope_hash_is_stable_and_vector_is_float32(self):
        self.assertEqual(_scope_hash("scope"), _scope_hash("scope"))
        self.assertEqual(len(_vector_bytes([1.0, 2.0, 3.0])), 12)

    def test_extracts_english_stargazing_preference_and_formats_english_context(self):
        prefs = extract_user_preferences(
            "I am a beginner interested in stargazing with a budget under 150 USD.", ""
        )
        self.assertEqual(prefs["experience_level"], "beginner")
        self.assertEqual(prefs["use_case"], "stargazing")
        context = format_memory_for_prompt(prefs)
        self.assertIn("Known customer preferences", context)
        self.assertIn("Experience level: beginner", context)
        self.assertIn("Intended use: stargazing", context)


if __name__ == "__main__":
    unittest.main()
