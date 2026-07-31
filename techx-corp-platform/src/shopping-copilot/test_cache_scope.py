import unittest

from copilot_server import _session_cache_fingerprint


class SessionCacheFingerprintTest(unittest.TestCase):
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
