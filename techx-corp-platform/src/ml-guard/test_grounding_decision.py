# Offline self-check for ml-guard's current NLI grounding decision rule.
# No model load needed: _nli_scores_sync is monkeypatched, so no torch/network.
# Run: python3 test_grounding_decision.py
import server


def main():
    cases = [
        (0.98, 0.01, 0.01, "pass", "entailment dominant"),
        (0.35, 0.60, 0.05, "judge", "neutral dominates"),
        (0.10, 0.85, server.BLOCK_CONTRA - 0.01, "judge", "below contradiction threshold"),
        (0.02, 0.02, server.BLOCK_CONTRA, "block", "contradiction reaches threshold"),
    ]

    original = server._nli_scores_sync
    try:
        for entail, neutral, contra, expected, note in cases:
            server._nli_scores_sync = lambda *a, scores=(entail, neutral, contra), **k: scores
            action = server._grounding_decision_sync("source", "answer")
            assert action == expected, (
                f"{note}: got {action!r}, want {expected!r} "
                f"(entail={entail} neutral={neutral} contra={contra})"
            )
    finally:
        server._nli_scores_sync = original

    print(f"grounding_decision self-check: OK ({len(cases)} cases; contradiction path covered)")


if __name__ == "__main__":
    main()
