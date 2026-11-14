import pytest

from backend.app.image_security import validate_image_dimensions


def test_accepts_normal_receipt_dimensions():
    validate_image_dimensions(4000, 6000)


@pytest.mark.parametrize(
    "width,height",
    [(0, 100), (100, 0), (-1, 100), (100, -1)],
)
def test_rejects_non_positive_dimensions(width, height):
    with pytest.raises(ValueError):
        validate_image_dimensions(width, height)


def test_rejects_image_over_pixel_limit():
    with pytest.raises(ValueError, match="pixels"):
        validate_image_dimensions(5000, 5001)


def test_rejects_extreme_single_dimension():
    with pytest.raises(ValueError, match="at most"):
        validate_image_dimensions(12_001, 100)
