from typing import List

from .models import IntegrityAlert


def detect_integrity(change_sets) -> List[IntegrityAlert]:
    alerts: List[IntegrityAlert] = []
    for change in change_sets:
        insert_len = sum(len(c.after.split()) for c in change.insertions)
        delete_len = sum(len(c.before.split()) for c in change.deletions)
        if insert_len + delete_len > 40:
            alerts.append(
                IntegrityAlert(
                    clause_id=change.clause_id,
                    alert_type="large_untracked_change",
                    rationale="Large insertion/deletion without explicit tracking metadata",
                )
            )
        if change.moved_blocks:
            alerts.append(
                IntegrityAlert(
                    clause_id=change.clause_id,
                    alert_type="moved_content",
                    rationale="Content moved between sections",
                )
            )
    return alerts
