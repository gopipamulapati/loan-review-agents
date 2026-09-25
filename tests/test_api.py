from fastapi.testclient import TestClient

from loan_review.api import app

client = TestClient(app)


def test_health():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["llm"] == "offline"


def test_review_endpoint(sample):
    resp = client.post("/review", json={"text": sample("02_borderline_applicant.txt")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "refer_to_underwriter"
    assert body["risk"]["band"] in {"low", "moderate", "high"}


def test_rejects_short_input():
    assert client.post("/review", json={"text": "too short"}).status_code == 422
