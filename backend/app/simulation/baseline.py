from ..models import Track, Resource

def first_come_first_served(tracks: list[Track], resources: list[Resource], time: int, start: int) -> dict[str,str]:
    """Simultaneous detections are tied by ID. Baseline never revisits commitments."""
    if time < start:
        return {}
    return {r.id:t.id for r,t in zip(resources,sorted(tracks,key=lambda t:t.id))}
