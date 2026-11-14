
from decimal import Decimal


def validate_tax_total(
    subtotal: Decimal,
    cgst: Decimal,
    sgst: Decimal,
    total: Decimal
) -> dict:
    """
    Validate whether subtotal + CGST + SGST equals total.
    """

    calculated_total = subtotal + cgst + sgst

    difference = abs(calculated_total - total)

    is_valid = difference == Decimal("0.00")

    return {
        "subtotal": str(subtotal),
        "cgst": str(cgst),
        "sgst": str(sgst),
        "expected_total": str(calculated_total),
        "receipt_total": str(total),
        "difference": str(difference),
        "is_valid": is_valid
    }


def validate_payment(
    advance: Decimal,
    final_payment: Decimal,
    total: Decimal
) -> dict:
    """
    Validate whether advance + final payment equals total.
    """

    calculated_payment = advance + final_payment

    difference = abs(calculated_payment - total)

    is_valid = difference == Decimal("0.00")

    return {
        "advance": str(advance),
        "final_payment": str(final_payment),
        "expected_total": str(calculated_payment),
        "receipt_total": str(total),
        "difference": str(difference),
        "is_valid": is_valid
    }


def validate_receipt(
    subtotal: Decimal,
    cgst: Decimal,
    sgst: Decimal,
    advance: Decimal,
    final_payment: Decimal,
    total: Decimal
) -> dict:
    """
    Run all financial validation checks
    and generate one combined report.
    """

    tax_result = validate_tax_total(
        subtotal,
        cgst,
        sgst,
        total
    )

    payment_result = validate_payment(
        advance,
        final_payment,
        total
    )

    overall_valid = (
        tax_result["is_valid"]
        and payment_result["is_valid"]
    )

    return {
        "tax_validation": tax_result,
        "payment_validation": payment_result,
        "overall_status": (
            "valid" if overall_valid else "review_required"
        )
    }

if __name__ == "__main__":

    # Sample receipt values
    subtotal = Decimal("6850.00")
    cgst = Decimal("171.25")
    sgst = Decimal("171.25")
    total = Decimal("7192.50")

    # Test 1: Tax validation
    result = validate_tax_total(
        subtotal,
        cgst,
        sgst,
        total
    )

    print("\n===== TAX VALIDATION RESULT =====\n")

    for key, value in result.items():
        print(f"{key}: {value}")

    print("\n=================================\n")

    # Sample payment values
    advance = Decimal("2000.00")
    final_payment = Decimal("5192.50")

    # Test 2: Payment validation
    payment_result = validate_payment(
        advance,
        final_payment,
        total
    )

    print("\n===== PAYMENT VALIDATION RESULT =====\n")

    for key, value in payment_result.items():
        print(f"{key}: {value}")

    print("\n======================================\n")	

    # Test 3: Complete receipt validation

    final_result = validate_receipt(
        subtotal,
        cgst,
        sgst,
        advance,
        final_payment,
        total
    )

    print("\n===== COMPLETE RECEIPT VALIDATION =====\n")

    print("Tax validation:",
          final_result["tax_validation"]["is_valid"])

    print("Payment validation:",
          final_result["payment_validation"]["is_valid"])

    print("Overall status:",
          final_result["overall_status"])

    print("\n========================================\n")
