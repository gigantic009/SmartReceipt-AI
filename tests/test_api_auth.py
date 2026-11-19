import os
import tempfile
from pathlib import Path

_TEST_DIR = Path(tempfile.mkdtemp(prefix="smartreceipt-api-tests-"))
os.environ["SMARTRECEIPT_DB_PATH"] = str(_TEST_DIR / "api.sqlite3")
os.environ["SMARTRECEIPT_UPLOAD_DIR"] = str(_TEST_DIR / "uploads")
os.environ["SMARTRECEIPT_OCR_READY_DIR"] = str(_TEST_DIR / "processed")

from fastapi.testclient import TestClient
from backend.app.database import create_session, create_user, save_receipt
from backend.app.main import app

client = TestClient(app)


def test_auth_lifecycle_and_static_workspace():
    blocked = client.post("/auth/register", headers={"Origin": "https://attacker.example"}, json={
        "name": "Blocked", "email": "blocked@example.com", "password": "long-password-123"
    })
    assert blocked.status_code == 403
    anonymous = client.get("/receipts")
    assert anonymous.status_code == 401
    registered = client.post("/auth/register", json={
        "name": "API Test", "email": "api@example.com", "password": "long-password-123"
    })
    assert registered.status_code == 201
    assert "sr_session" in registered.cookies
    assert client.get("/auth/me").status_code == 200
    assert len(client.get("/auth/sessions").json()["sessions"]) == 1
    history_response = client.get("/receipts")
    assert history_response.json()["total"] == 0
    assert history_response.headers["Cache-Control"] == "private, no-store"
    workspace = client.get("/app/")
    assert workspace.status_code == 200
    assert "Content-Security-Policy" in workspace.headers
    assert workspace.headers["X-Frame-Options"] == "DENY"
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_receipt_detail_and_review_are_owner_scoped():
    owner = create_user("Receipt Owner", "receipt-owner@example.com", "owner-password-123",
                        Path(os.environ["SMARTRECEIPT_DB_PATH"]))
    other = create_user("Receipt Other", "receipt-other@example.com", "other-password-123",
                        Path(os.environ["SMARTRECEIPT_DB_PATH"]))
    save_receipt(
        receipt_id="private-receipt", user_id=owner["id"],
        original_filename="private.jpg", processed_filename="private.png",
        status="review_required", ocr_text="Total 50.00",
        receipt={"merchant": "Example Store", "date": "2026-11-18", "total": "50.00"}, validation={"overall_status": "review_required"},
        ocr={"average_confidence": 60}, database_path=Path(os.environ["SMARTRECEIPT_DB_PATH"]),
    )
    owner_token = create_session(owner["id"], Path(os.environ["SMARTRECEIPT_DB_PATH"]))
    other_token = create_session(other["id"], Path(os.environ["SMARTRECEIPT_DB_PATH"]))
    owner_client = TestClient(app)
    other_client = TestClient(app)
    owner_client.cookies.set("sr_session", owner_token)
    other_client.cookies.set("sr_session", other_token)
    assert owner_client.get("/receipts/private-receipt").status_code == 200
    assert other_client.get("/receipts/private-receipt").status_code == 404
    assert other_client.patch("/receipts/private-receipt/review",
        json={"status":"approved","fields":{"total":"999.00"}}).status_code == 404
    invalid_approval = owner_client.patch("/receipts/private-receipt/review",
        json={"status":"approved","fields":{"total":"not-an-amount"}})
    assert invalid_approval.status_code == 422
    approved = owner_client.patch("/receipts/private-receipt/review",
        json={"status":"approved","fields":{"total":"50.50"}})
    assert approved.status_code == 200
    assert approved.json()["receipt"]["total"] == "50.50"

    history = owner_client.get("/receipts/private-receipt/review-history")
    assert history.status_code == 200
    assert len(history.json()["events"]) == 1
    exported = owner_client.get("/receipts/export.csv")
    assert exported.status_code == 200
    assert "Example Store" in exported.text
    matches = owner_client.post("/reconciliation/suggest", json={"lines":[{
        "description":"EXAMPLE STORE CARD", "amount":"50.00", "date":"2026-11-18"
    }]})
    assert matches.status_code == 200
    suggestion = matches.json()["suggestions"][0]
    assert suggestion["requires_human_confirmation"] is True
    assert suggestion["candidates"][0]["receipt_id"] == "private-receipt"

