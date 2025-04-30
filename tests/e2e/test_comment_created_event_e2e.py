from conftest import client
import json

def test_comment_created_event(client):
    request_body = {'id': 'defeaa07-e28c-4a51-a583-6e8382805672', 'timestamp': '2025-04-01T21:36:14.776Z', 'workspace_id': 'e83f67a4-b5c2-45ad-90ad-f8e8267e1123', 'workspace_name': "Ethan's Notion", 'subscription_id': '1c8d872b-594c-8191-b71e-0099b3881d3c', 'integration_id': '15fd872b-594c-81d1-9210-00378dd09e38', 'authors': [{'id': '59164cd3-f8de-49dc-a432-e8cb48b4a39d', 'type': 'person'}], 'attempt_number': 1, 'type': 'comment.created', 'entity': {'id': '1c8592a3-0352-805c-87af-001dd3026aa4', 'type': 'comment'}, 'data': {'page_id': '1c8592a3-0352-80bb-8b93-f41eb9732cf3', 'parent': {'id': '1c8592a3-0352-80bb-8b93-f41eb9732cf3', 'type': 'page'}}}
    response = client.post("/events", data=json.dumps(request_body), content_type="application/json")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["action"] == "processed_comment"
    assert data["result"] is not None