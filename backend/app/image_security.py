"""Upload image safety checks for the receipt-processing API."""


MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_DIMENSION = 12_000


def validate_image_dimensions(width: int, height: int) -> None:
    """Reject zero-sized, extremely wide/tall, or decompression-bomb images."""
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive.")

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValueError(
            f"Image width and height must each be at most {MAX_IMAGE_DIMENSION} pixels."
        )

    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(
            f"Image must contain no more than {MAX_IMAGE_PIXELS:,} pixels."
        )
