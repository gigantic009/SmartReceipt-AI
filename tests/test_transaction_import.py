import asyncio
from io import BytesIO
from starlette.datastructures import UploadFile

from backend.app import main


def test_bank_csv_import_supports_debit_amount_and_currency(monkeypatch):
    captured = {}
    def fake_save(records):
        captured["records"] = records
        return len(records)
    monkeypatch.setattr(main, "save_bank_transactions", fake_save)
    payload = (
        "Transaction Date,Description,Debit Amount,Credit Amount,Currency Code,Reference\n"
        "2026-11-15,ACME STORE,1,250.00,,INR,REF-1\n"
    )
    # Use a simpler header shape with a single debit amount column.
    payload = (
        "Transaction Date,Description,Debit Amount,Currency Code,Reference\n"
        "2026-11-15,ACME STORE,1,250.00,INR,REF-1\n"
    )
    upload = UploadFile(file=BytesIO(payload.encode()), filename="statement.csv")
    result = asyncio.run(main.import_transactions_csv(upload))
    assert result["imported"] == 1
    assert captured["records"][0]["amount"] == "1250.00"
    assert captured["records"][0]["currency_code"] == "INR"


def test_bank_csv_import_rejects_wrong_extension():
    upload = UploadFile(file=BytesIO(b"a,b\n1,2"), filename="statement.xlsx")
    try:
        asyncio.run(main.import_transactions_csv(upload))
    except Exception as error:
        assert getattr(error, "status_code", None) == 400
    else:
        raise AssertionError("Expected unsupported file type to be rejected")
