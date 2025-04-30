import os
import sys
import pytest

# Ensure the project root is in sys.path for import safety
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app

@pytest.fixture(scope="function")
def client():
    """
    Provides a Flask test client for each test function.
    Ensures app is in TESTING mode and yields a fresh client per test.
    """
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client