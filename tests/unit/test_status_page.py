from conftest import client
import json


def test_status_page(client):
    response = client.get("/", content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data.keys()
    