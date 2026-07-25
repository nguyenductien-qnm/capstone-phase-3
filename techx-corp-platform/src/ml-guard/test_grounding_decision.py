# Self-check for ml-guard's grounding decision rule (MANDATE-06 re-audit 18/07).
# Bug: entail >= PASS_ENTAIL alone let pure fabrications through — an answer that
# invents unsupported content (not contradicting the source, just not present in
# it) can score low contra AND an entail just above the floor while neutral is
# actually the dominant class. Fix requires entail to also be >= neutral.
# No model load needed: nli_scores is monkeypatched, so no torch/network dependency.
# Run: python3 test_grounding_decision.py
import server


def main():
    cases = [
        (0.98, 0.01, 0.01, "pass", "clearly grounded: entail dominant"),
        (0.02, 0.02, 0.96, "block", "clear contradiction"),
        (0.35, 0.60, 0.05, "judge", "repro: fabrication clears entail floor but neutral dominates"),
        (0.10, 0.85, 0.05, "judge", "neutral dominant, low entail"),
    ]
    
    # Test `_grounding_decision_sync` and `VietnameseMDeBERTaGrounding`
    validator = server.VietnameseMDeBERTaGrounding()
    
    for entail, neutral, contra, expected, note in cases:
        server._nli_scores_sync = lambda *a, **k: (entail, neutral, contra)
        
        # Test old raw decision (it returns string action now)
        action = server._grounding_decision_sync("source", "answer")
        assert action == expected, (
            f"{note}: got {action!r}, want {expected!r} "
            f"(entail={entail} neutral={neutral} contra={contra})"
        )
        
        # Test new validator
        metadata = {"grounding_source": "source"}
        res = validator.validate("answer", metadata=metadata)
        if expected == "block":
            assert isinstance(res, server.FailResult), f"{note}: expected FailResult, got {type(res)}"
        else:
            assert isinstance(res, server.PassResult), f"{note}: expected PassResult, got {type(res)}"
            assert res.metadata["action"] == expected, f"{note}: expected PassResult action {expected}, got {res.metadata['action']}"

    print("grounding_decision self-check: OK (4 cases)")

if __name__ == "__main__":
    main()
