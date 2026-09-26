import pytest
from app.config import load_config
from app.simulation.world import World

@pytest.fixture
def config():
    return load_config()

@pytest.fixture(scope='session')
def world():
    return World(load_config())
