from ..models import AuditEntry, Track, Resource

def record(audit: list[AuditEntry], time: int, track: Track, resource: Resource | None, action: str, reason: str, assignments: dict[str,str], previous: str | None = None):
    lead = max(track.probabilities, key=track.probabilities.get)
    entry = AuditEntry(id=len(audit)+1,time=time,track_id=track.id,resource_id=resource.id if resource else None,
        action=action,leading_destination=lead,previous_leading_destination=previous,probability=track.probabilities[lead],
        factors=track.factors.model_copy(deep=True),priority=track.priority,reason=reason,assignments=dict(assignments))
    audit.append(entry)
    return entry
