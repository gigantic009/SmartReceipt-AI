
import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


# Supported receipt image formats
SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png",
    ".bmp", ".tif", ".tiff", ".webp"
}

log = logging.getLogger("receipt_preprocessor")


# ==================================================
# CONFIGURATION
# ==================================================

@dataclass
class PreprocessConfig:

    target_width: int = 1600

    # Disabled by default to preserve thin text
    denoise_strength: int = 0

    # Improve local image contrast
    clahe_clip_limit: float = 2.0

    # Correct tilted receipt images
    deskew: bool = True
    max_skew_degrees: float = 10.0

    # Keep grayscale as the default
    binarize: bool = False


# ==================================================
# IMAGE INPUT / OUTPUT
# ==================================================

def load_image(path: Path) -> np.ndarray:
    """
    Read an image safely, including Unicode Windows paths.
    """

    if not path.is_file():
        raise FileNotFoundError(
            f"Image not found: {path}"
        )

    data = np.fromfile(str(path), dtype=np.uint8)

    image = cv2.imdecode(
        data,
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise ValueError(
            f"Could not decode image: {path}"
        )

    return image


def save_image(path: Path, image: np.ndarray) -> None:
    """
    Save image as lossless PNG.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    success, buffer = cv2.imencode(
        ".png",
        image
    )

    if not success:
        raise ValueError(
            f"Could not encode image: {path}"
        )

    buffer.tofile(str(path))


# ==================================================
# IMAGE PROCESSING FUNCTIONS
# ==================================================

def to_grayscale(image: np.ndarray) -> np.ndarray:
    """
    Convert colour image into grayscale.
    """

    return cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )


def resize_to_width(
    gray: np.ndarray,
    target_width: int
) -> np.ndarray:
    """
    Resize receipt to a consistent width.
    """

    height, width = gray.shape

    if width == target_width:
        return gray

    scale = target_width / width

    interpolation = (
        cv2.INTER_CUBIC
        if scale > 1
        else cv2.INTER_AREA
    )

    return cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=interpolation
    )


def denoise(
    gray: np.ndarray,
    strength: int
) -> np.ndarray:
    """
    Remove image noise while preserving text.
    """

    return cv2.fastNlMeansDenoising(
        gray,
        None,
        h=strength,
        templateWindowSize=7,
        searchWindowSize=21
    )


def enhance_contrast(
    gray: np.ndarray,
    clip_limit: float
) -> np.ndarray:
    """
    Improve local contrast using CLAHE.
    """

    clahe = cv2.createCLAHE(
        clipLimit=clip_limit,
        tileGridSize=(8, 8)
    )

    return clahe.apply(gray)


def rotate(
    image: np.ndarray,
    angle: float,
    border_value: int
) -> np.ndarray:
    """
    Rotate image without changing its dimensions.
    """

    height, width = image.shape[:2]

    matrix = cv2.getRotationMatrix2D(
        (width / 2, height / 2),
        angle,
        1.0
    )

    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_value
    )


# ==================================================
# SKEW DETECTION
# ==================================================

def estimate_skew_angle(
    gray: np.ndarray,
    max_angle: float
) -> float:
    """
    Estimate receipt rotation using projection profiles.

    Text lines should be approximately horizontal.
    The best angle produces the strongest row projection.
    """

    small = resize_to_width(
        gray,
        400
    )

    _, binary = cv2.threshold(
        small,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    best_angle = 0.0
    best_score = -1.0

    angles = np.arange(
        -max_angle,
        max_angle + 0.01,
        0.5
    )

    for angle in angles:

        rotated = rotate(
            binary,
            float(angle),
            0
        )

        row_projection = rotated.sum(axis=1)

        score = np.var(row_projection)

        if score > best_score:
            best_score = score
            best_angle = float(angle)

    return best_angle


def deskew(
    gray: np.ndarray,
    max_angle: float
) -> np.ndarray:
    """
    Correct small receipt rotation.
    """

    angle = estimate_skew_angle(
        gray,
        max_angle
    )

    if abs(angle) < 0.5:
        log.debug("No significant skew detected")
        return gray

    log.debug(
        "Correcting image rotation by %.1f degrees",
        angle
    )

    return rotate(
        gray,
        angle,
        255
    )


# ==================================================
# OPTIONAL BINARIZATION
# ==================================================

def binarize(gray: np.ndarray) -> np.ndarray:
    """
    Convert grayscale image into black and white.
    """

    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        15
    )


# ==================================================
# COMPLETE PREPROCESSING PIPELINE
# ==================================================

def preprocess_receipt(
    image: np.ndarray,
    config: PreprocessConfig
) -> np.ndarray:

    # Step 1: Convert to grayscale
    gray = to_grayscale(image)

    # Step 2: Standardize image width
    gray = resize_to_width(
        gray,
        config.target_width
    )

    # Step 3: Denoise only when requested
    if config.denoise_strength > 0:

        gray = denoise(
            gray,
            config.denoise_strength
        )

    # Step 4: Improve local contrast
    gray = enhance_contrast(
        gray,
        config.clahe_clip_limit
    )

    # Step 5: Correct image rotation
    if config.deskew:

        gray = deskew(
            gray,
            config.max_skew_degrees
        )

    # Step 6: Optional black-and-white conversion
    if config.binarize:

        gray = binarize(gray)

    return gray


# ==================================================
# FIND RECEIPT IMAGES
# ==================================================

def find_images(
    input_dir: Path
) -> list[Path]:

    return sorted(
        path
        for path in input_dir.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    )


# ==================================================
# BATCH PROCESSING
# ==================================================

def process_folder(
    input_dir: Path,
    output_dir: Path,
    config: PreprocessConfig,
    overwrite: bool = False
) -> None:

    if not input_dir.is_dir():

        raise NotADirectoryError(
            f"Input folder not found: {input_dir}"
        )

    images = find_images(input_dir)

    if not images:

        log.warning(
            "No supported images found in %s",
            input_dir
        )

        return

    processed = 0
    skipped = 0
    failed = 0

    for index, path in enumerate(
        images,
        start=1
    ):

        output_path = (
            output_dir / f"{path.stem}.png"
        )

        prefix = (
            f"[{index}/{len(images)}] {path.name}"
        )

        # Avoid unnecessary repeated processing
        if output_path.exists() and not overwrite:

            log.info(
                "%s -> skipped (already processed)",
                prefix
            )

            skipped += 1
            continue

        try:

            # Load original receipt
            image = load_image(path)

            # Preprocess image
            result = preprocess_receipt(
                image,
                config
            )

            # Save processed image
            save_image(
                output_path,
                result
            )

            log.info(
                "%s -> saved %s",
                prefix,
                output_path.name
            )

            processed += 1

        except Exception as error:

            log.error(
                "%s -> FAILED: %s",
                prefix,
                error
            )

            failed += 1

    log.info(
        "Finished. processed=%d skipped=%d failed=%d",
        processed,
        skipped,
        failed
    )


# ==================================================
# MAIN PROGRAM
# ==================================================

def main():

    parser = argparse.ArgumentParser(
        description="SmartReceipt AI - Receipt Image Preprocessor"
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("backend/receipts_raw")
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/ocr_ready")
    )

    parser.add_argument(
        "--width",
        type=int,
        default=1600
    )

    parser.add_argument(
        "--denoise-strength",
        type=int,
        default=0
    )

    parser.add_argument(
        "--binarize",
        action="store_true"
    )

    parser.add_argument(
        "--no-deskew",
        action="store_true"
    )

    parser.add_argument(
        "--overwrite",
        action="store_true"
    )

    parser.add_argument(
        "--verbose",
        action="store_true"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.width <= 0:
        parser.error("--width must be greater than zero")

    if args.denoise_strength < 0:
        parser.error("--denoise-strength cannot be negative")

    logging.basicConfig(
        level=(
            logging.DEBUG
            if args.verbose
            else logging.INFO
        ),
        format="%(levelname)s: %(message)s"
    )

    # Create configuration
    config = PreprocessConfig(
        target_width=args.width,
        denoise_strength=args.denoise_strength,
        binarize=args.binarize,
        deskew=not args.no_deskew
    )

    # Process receipt folder
    process_folder(
        args.input,
        args.output,
        config,
        args.overwrite
    )


if __name__ == "__main__":
    main()
