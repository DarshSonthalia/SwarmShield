import numpy as np

def normalized_entropy(probabilities: np.ndarray) -> float:
    p = np.asarray(probabilities, dtype=float)
    if len(p) <= 1:
        return 0.0
    positive = p[p > 0]
    return float(-np.sum(positive * np.log(positive)) / np.log(len(p)))

def heading_statistics(headings: list[float]) -> tuple[float,float]:
    if len(headings) < 2:
        return 0.0, 1.0
    resultant = abs(np.mean(np.exp(1j * np.asarray(headings))))
    variance = float(np.clip(1 - resultant, 0, 1))
    return variance, float(np.exp(-12 * variance))

def angular_difference(a: float, b: float) -> float:
    return float(abs(np.arctan2(np.sin(a-b), np.cos(a-b))))
