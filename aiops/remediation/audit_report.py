"""Render the structured remediation JSONL trail as a Markdown incident artifact.

The runtime store remains append-only JSONL because it is cheap and survives malformed
individual records. This tool is the human-facing half of TF1-103: it correlates every
gate by ``remediation_id`` and states explicitly whether rollback happened.

Usage:
    python audit_report.py \
      --input /data/audit_log.jsonl \
      --output report/tf1-103-structured-audit/generated-postmortem.md
"""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


def load_jsonl(path):
    records = []
    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_no}: audit record must be an object")
        records.append(record)
    return records


def group_attempts(records):
    """Group new schema records and keep old TF1-112 evidence readable.

    Legacy records did not have ``remediation_id``. A new legacy group begins at every
    ``detect`` stage; subsequent records with the same rule/service/pod stay together.
    """
    groups = OrderedDict()
    legacy_current = {}
    legacy_count = 0
    missing_id_count = 0

    for record in sorted(records, key=lambda item: item.get("ts", 0)):
        remediation_id = record.get("remediation_id")
        if not remediation_id and record.get("schema_version") is not None:
            # Schema moi ma thieu ID la correlation gap, khong phai legacy. Tach
            # tung record de report lam lo loi thay vi gom no thanh attempt gia.
            missing_id_count += 1
            remediation_id = f"missing-remediation-id-{missing_id_count}"
        elif not remediation_id:
            target = (
                record.get("rule_id"),
                record.get("service"),
                record.get("pod"),
            )
            if record.get("stage") == "detect" or target not in legacy_current:
                legacy_count += 1
                legacy_current[target] = f"legacy-{legacy_count}"
            remediation_id = legacy_current[target]
        groups.setdefault(remediation_id, []).append(record)
    return groups


def attempt_outcome(records):
    # Lay record dau tien cua tung stage mot cach tuong minh. Khong dung dict
    # last-wins vi mot stage (vd circuit_breaker allow -> opened) co the lap lai.
    def first(stage):
        return next((record for record in records if record.get("stage") == stage), None)

    verify = first("verify")
    action = first("action")
    escalation = first("escalate")
    denied = next((r for r in records if r.get("decision") == "deny"), None)

    if verify and verify.get("decision") == "pass":
        return "recovered"
    if verify and verify.get("decision") == "fail":
        if escalation and escalation.get("decision") == "buffered":
            return "verify failed; escalation buffered"
        if escalation and escalation.get("decision") == "suppressed_by_cooldown":
            return "verify failed; escalation suppressed by cooldown"
        if escalation:
            return f"verify failed; escalation {escalation.get('decision', 'unknown')}"
        return "verify failed; escalation not recorded"
    if action and action.get("decision") == "error":
        return "action error"
    if denied:
        return f"blocked at {denied.get('stage', 'unknown')}"
    if first("dry_run"):
        return "dry-run only"
    return "incomplete/no terminal record"


def rollback_outcome(records):
    rollback = next((r for r in records if r.get("stage") == "rollback"), None)
    if not rollback:
        return "not recorded"
    performed = rollback.get("rollback_performed")
    if performed is True:
        return f"performed ({rollback.get('decision', 'recorded')})"
    return f"not performed ({rollback.get('decision', 'recorded')})"


def render_markdown(records, title="Structured remediation audit report",
                    source="audit_log.jsonl", generated_at=None):
    groups = group_attempts(records)
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {title}",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Source: `{source}`",
        f"- Records: **{len(records)}**",
        f"- Remediation attempts: **{len(groups)}**",
        "",
        "## Attempt summary",
        "",
        "| Remediation ID | Rule | Service / pod | Outcome | Rollback |",
        "|---|---|---|---|---|",
    ]

    for remediation_id, attempt in groups.items():
        first = attempt[0]
        target = f"{first.get('service') or '-'} / {first.get('pod') or '-'}"
        lines.append(
            f"| `{remediation_id}` | `{first.get('rule_id') or '-'}` | "
            f"{target} | {attempt_outcome(attempt)} | {rollback_outcome(attempt)} |"
        )

    for remediation_id, attempt in groups.items():
        lines.extend([
            "",
            f"## Attempt `{remediation_id}`",
            "",
            "| UTC time | Stage | Decision | Detail |",
            "|---|---|---|---|",
        ])
        for record in attempt:
            ignored = {
                "schema_version", "event_id", "remediation_id", "ts", "ts_utc",
                "stage", "decision", "rule_id", "service", "pod", "dry_run",
            }
            detail = {key: value for key, value in record.items() if key not in ignored}
            detail_text = json.dumps(detail, ensure_ascii=False, sort_keys=True)
            detail_text = detail_text.replace("|", "\\|")
            timestamp = record.get("ts_utc") or record.get("ts") or "-"
            lines.append(
                f"| `{timestamp}` | `{record.get('stage', '-')}` | "
                f"`{record.get('decision', '-')}` | `{detail_text}` |"
            )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- `rollback: not_required` means verification passed or the action never completed.",
        "- `rollback: not_available` means verification failed, but `restart_pod` made no "
        "configuration/release change that could honestly be reverted; the engine stopped "
        "automation and escalated instead.",
        "- `rollback: not recorded` identifies legacy or incomplete evidence. It must not be "
        "presented as proof that rollback occurred.",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="structured JSONL audit log")
    parser.add_argument("--output", required=True, help="Markdown report destination")
    parser.add_argument("--title", default="Structured remediation audit report")
    args = parser.parse_args()

    records = load_jsonl(args.input)
    output = render_markdown(records, title=args.title, source=args.input)
    Path(args.output).write_text(output, encoding="utf-8")
    print(f"wrote {args.output}: {len(records)} records, {len(group_attempts(records))} attempts")


if __name__ == "__main__":
    main()
