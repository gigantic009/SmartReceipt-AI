from decimal import Decimal


def validate_tax_total(
    subtotal: Decimal,
    cgst: Decimal,
    sgst: Decimal,
    total: Decimal
) -> dict:
    """Check whether subtotal plus CGST and SGST equals the receipt total."""
    calculated_total = subtotal + cgst + sgst
    difference = abs(calculated_total - total)

    return {
        "subtotal": str(subtotal),
        "cgst": str(cgst),
        "sgst": str(sgst),
        "expected_total": str(calculated_total),
        "receipt_total": str(total),
        "difference": str(difference),
        "is_valid": difference == Decimal("0.00")
    }


def validate_payment(
    advance: Decimal,
    final_payment: Decimal,
    total: Decimal,
    balance: Decimal | None = None
) -> dict:
    """Reconcile advance, final payment, and optional outstanding balance."""
    calculated_payment = advance + final_payment
    if balance is not None:
        calculated_payment += balance

    difference = abs(calculated_payment - total)

    result = {
        "advance": str(advance),
        "final_payment": str(final_payment),
        "expected_total": str(calculated_payment),
        "receipt_total": str(total),
        "difference": str(difference),
        "is_valid": difference == Decimal("0.00")
    }
    if balance is not None:
        result["balance"] = str(balance)

    return result


def validate_receipt(
    subtotal: Decimal,
    cgst: Decimal,
    sgst: Decimal,
    advance: Decimal,
    final_payment: Decimal,
    total: Decimal,
    balance: Decimal | None = None
) -> dict:
    """Run tax and payment checks and return a combined validation report."""
    tax_result = validate_tax_total(subtotal, cgst, sgst, total)
    payment_result = validate_payment(
        advance,
        final_payment,
        total,
        balance
    )

    overall_valid = tax_result["is_valid"] and payment_result["is_valid"]

    return {
        "tax_validation": tax_result,
        "payment_validation": payment_result,
        "overall_status": "valid" if overall_valid else "review_required"
    }
