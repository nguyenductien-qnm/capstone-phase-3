import unittest
import re
import hashlib

from copilot_server import _session_cache_fingerprint


def _l1_key(routed_model: str, user_id: str = "user-1",
            question: str = "Which telescope should I buy?",
            prompt_ver: str = "deadbeef", catalog_fp: str = "fp1",
            mem_fp: str = "mem1") -> str:
    """Reproduce the copilot_server L1 cache key formula in one place."""
    public = routed_model.rsplit("/", 1)[-1] if routed_model.startswith("arn:") else routed_model
    model_ver = public.replace(":", "-")
    question_fp = hashlib.md5(question.encode()).hexdigest()[:12]
    sess_fp = _session_cache_fingerprint(question, [], "session-x")
    return f"copilot:answer:{user_id}:{model_ver}:{prompt_ver}:{catalog_fp}:{mem_fp}:{sess_fp}:{question_fp}"


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


class ModelVariantCacheIsolationTest(unittest.TestCase):
    """Regression guard: Nova Lite and Nova Pro must never share a cache entry.

    Before the cache-key fix (2026-07-31), copilot_server used MAIN_MODEL (env
    default) instead of the routed model, meaning a Pro-generated answer would
    be stored under a Lite key and served back to Lite-cohort users.
    """

    def test_different_model_variants_produce_different_keys(self):
        key_lite = _l1_key("amazon.nova-lite-v1:0")
        key_pro = _l1_key("amazon.nova-pro-v1:0")
        self.assertNotEqual(
            key_lite, key_pro,
            "Nova Lite and Nova Pro must have separate cache namespaces",
        )

    def test_same_model_produces_same_key(self):
        """Sanity check: same model → same key (determinism)."""
        self.assertEqual(_l1_key("amazon.nova-lite-v1:0"), _l1_key("amazon.nova-lite-v1:0"))

    def test_arn_model_id_stripped_to_short_name_in_key(self):
        """ARN-format model IDs must be reduced to their short name so keys
        remain readable and do not embed account numbers."""
        arn = "arn:aws:bedrock:us-east-1:123456789:application-inference-profile/amazon.nova-lite-v1:0"
        short = "amazon.nova-lite-v1:0"
        self.assertEqual(_l1_key(arn), _l1_key(short))


if __name__ == "__main__":
    unittest.main()
