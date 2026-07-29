# Raw evidence rules

This folder accepts only real command/API output captured during Mandate 18 execution.

- No sample or invented output.
- Preserve failures and exit codes.
- Redact account ID, email, tokens, credentials and sensitive ARN segments.
- Keep resource names, region, timestamp, query/filter and decision-relevant fields.
- Match numeric prefixes with `EVIDENCE-INDEX.md` and `screenshots/README.md`.

Current expected-but-missing after/delivery files are deliberately not created:

- `04-orphans-after.json`
- `10-telemetry-after.txt`
- `13-noncompute-usage-after.json`
- `14-pr-ci.txt`

`14-pr-readiness-audit.txt` records the real pre-PR audit and must not be
confused with proof that a PR or CI run exists.
