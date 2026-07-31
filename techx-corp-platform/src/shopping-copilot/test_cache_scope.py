import unittest
import re

from copilot_server import _session_cache_fingerprint


class SessionCacheFingerprintTest(unittest.TestCase):
    def test_context_fingerprint_uses_strong_fixed_length_digest(self):
        session_id = "user-session-sensitive-123"
        fingerprint = _session_cache_fingerprint(
            "How much is the first one?", [], session_id
        )

        self.assertRegex(fingerprint, re.compile(r"^[0-9a-f]{64}$"))
        self.assertNotIn(session_id, fingerprint)

    def test_repeated_standalone_question_ignores_growing_session(self):
        question = "Recommend a beginner telescope under $200."
        empty = []
        populated = [{"role": "user", "content": [{"text": question}]}]
        self.assertEqual(
            _session_cache_fingerprint(question, empty, "session-a"),
            _session_cache_fingerprint(question, populated, "session-a"),
        )

    def test_context_dependent_question_is_scoped_to_session(self):
        question = "How much is the first one?"
        session_a = [{"role": "assistant", "content": [{"text": "Product A"}]}]
        session_b = [{"role": "assistant", "content": [{"text": "Product B"}]}]
        self.assertNotEqual(
            _session_cache_fingerprint(question, session_a, "session-a"),
            _session_cache_fingerprint(question, session_b, "session-a"),
        )
    def test_standalone_question_can_hit_across_sessions_for_same_user(self):
        self.assertEqual(
            _session_cache_fingerprint("Recommend a telescope", [], "session-a"),
            _session_cache_fingerprint("Recommend a telescope", [], "session-b"),
        )


if __name__ == "__main__":
    unittest.main()
