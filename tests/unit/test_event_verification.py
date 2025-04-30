import pytest
from flask import json
from conftest import client
import os

def test_event_verification_valid_token(client):
    payload = {"verification_token": "testtoken123"}
    response = client.post("/events", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert os.environ["NOTION_VERIFICATION_TOKEN"] == "testtoken123"
    
# TODO: Implement request signing using the verification token.
#  This test should supply an invalid token in the request header of an event payload.
#  The app should respond by denying the request.
# def test_event_verification_invalid_token(client):
#     payload = {"verification_token": "invalidtoken123"}
#     response = client.post("/events", data=json.dumps(payload), content_type="application/json")
#     assert response.status_code == 200
#     data = response.get_json()
#     assert data["status"] == "error"
#     assert "Invalid verification token" in data["message"]

def test_event_verification_empty_payload(client):
    response = client.post("/events", data=json.dumps({}), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "error"
    assert "Invalid event type" in data["message"]
