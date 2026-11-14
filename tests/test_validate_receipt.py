from decimal import Decimal

from backend.app.validate_receipt import validate_receipt


def test_valid_receipt_with_zero_balance():
    result = validate_receipt(
        subtotal=Decimal("6850.00"),
        cgst=Decimal("171.25"),
        sgst=Decimal("171.25"),
        advance=Decimal("2000.00"),
        final_payment=Decimal("5192.50"),
        total=Decimal("7192.50"),
        balance=Decimal("0.00"),
    )

    assert result["tax_validation"]["is_valid"] is True
    assert result["payment_validation"]["is_valid"] is True
    assert result["overall_status"] == "valid"


def test_nonzero_outstanding_balance_is_included():
    result = validate_receipt(
        subtotal=Decimal("100.00"),
        cgst=Decimal("0.00"),
        sgst=Decimal("0.00"),
        advance=Decimal("50.00"),
        final_payment=Decimal("30.00"),
        total=Decimal("100.00"),
        balance=Decimal("20.00"),
    )

    assert result["payment_validation"]["is_valid"] is True


def test_incorrect_tax_total_requires_review():
    result = validate_receipt(
        subtotal=Decimal("6850.00"),
        cgst=Decimal("181.25"),
        sgst=Decimal("171.25"),
        advance=Decimal("2000.00"),
        final_payment=Decimal("5192.50"),
        total=Decimal("7192.50"),
        balance=Decimal("0.00"),
    )

    assert result["tax_validation"]["is_valid"] is False
    assert result["overall_status"] == "review_required"
