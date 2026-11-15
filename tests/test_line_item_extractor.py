from backend.app.line_item_extractor import extract_line_items
from backend.app.global_billing import parse_global_document


def test_line_items_extract_amount_and_description_without_inventing_quantity():
    items = extract_line_items("Organic Apples 12.50\nWhole Milk 4.25\nSubtotal 16.75\nVAT 10% 1.68")
    assert len(items) == 2
    assert items[0]["description"] == "Organic Apples"
    assert items[0]["line_total"] == "12.50"
    assert items[0]["quantity"] is None
    assert items[0]["needs_review"] is True


def test_quantity_prefix_is_preserved_as_candidate():
    items = extract_line_items("2 x Filter Coffee 180.00")
    assert len(items) == 1
    assert items[0]["quantity"] == "2"
    assert items[0]["description"] == "Filter Coffee"


def test_global_parser_includes_line_items_and_payment_hints():
    result = parse_global_document(
        "Corner Cafe\nFilter Coffee 180.00\nSandwich 220.00\nPaid by UPI\nTotal INR 400.00"
    )
    assert len(result["line_items"]) == 2
    assert result["payments"][0]["method"] == "upi"
