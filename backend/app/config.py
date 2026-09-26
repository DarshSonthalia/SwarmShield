from pathlib import Path
from .models import SimulationConfig

def load_config() -> SimulationConfig:
    return SimulationConfig.model_validate_json(Path(__file__).with_name('config.json').read_text())
