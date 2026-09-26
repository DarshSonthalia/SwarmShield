from ..models import Destination

def expected_consequence(probabilities: dict[str,float], destinations: list[Destination]) -> float:
    return sum(probabilities[d.id] * d.weight for d in destinations)
