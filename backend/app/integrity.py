from typing import List

from .models import IntegrityAlert


def detect_integrity(change_sets) -> List[IntegrityAlert]:
    alerts: List[IntegrityAlert] = []
    for change in change_sets:
        insert_len = sum(len(c.after.split()) for c in change.insertions)
        delete_len = sum(len(c.before.split()) for c in change.deletions)
        substitution_len = sum(
            max(len(c.before.split()), len(c.after.split()))
            for c in change.substitutions
        )

        if insert_len + delete_len > 40 or substitution_len > 50:
            alerts.append(
                IntegrityAlert(
                    clause_id=change.clause_id,
                    alert_type="ghost_change_candidate",
                    rationale="Large textual change detected without explicit tracking metadata",
                )
            )

        if delete_len >= 20 and insert_len == 0:
            alerts.append(
                IntegrityAlert(
                    clause_id=change.clause_id,
                    alert_type="silent_deletion",
                    rationale="Material deletion detected with no offsetting insertion",
                )
            )

        if insert_len >= 20 and delete_len == 0:
            alerts.append(
                IntegrityAlert(
                    clause_id=change.clause_id,
                    alert_type="untracked_insertion",
                    rationale="Material insertion detected with no corresponding tracked deletion",
                )
            )

        if change.moved_blocks:
            alerts.append(
                IntegrityAlert(
                    clause_id=change.clause_id,
                    alert_type="moved_content",
                    rationale="Content appears to have moved between sections",
                )
            )
    return alerts
