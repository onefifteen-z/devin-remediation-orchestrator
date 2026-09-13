from tests.conftest import make_issue_labeled_payload, signed_webhook_request


def test_duplicate_delivery_does_not_create_two_tasks(client, webhook_secret):
    payload = make_issue_labeled_payload()
    delivery_id = "delivery-dedup-001"

    response1 = signed_webhook_request(client, payload, webhook_secret, delivery_id)
    response2 = signed_webhook_request(client, payload, webhook_secret, delivery_id)

    assert response1.json()["outcome"] == "accepted"
    assert response2.json()["outcome"] == "duplicate"
    assert response1.json()["task_id"] == response2.json().get("task_id", response1.json()["task_id"])

    tasks_response = client.get("/api/tasks")
    assert tasks_response.json()["total"] == 1
