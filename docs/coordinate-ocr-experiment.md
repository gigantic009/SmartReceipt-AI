# Coordinate-aware receipt OCR experiment

This tool is an isolated experiment. It does not change the production upload
pipeline or the existing receipt parser.

## Run locally

From the repository root, with the virtual environment active:

    python -m backend.app.coordinate_extractor "backend\uploads\YOUR_RECEIPT_IMAGE.jpg" --diagnostics

Replace the example image path with a local receipt image. Do not commit
personal receipts or financial documents to the repository.

## What it does

- Runs Tesseract PSM 6 and PSM 11 on the tax/total region for comparison.
- Uses PSM 6 for subtotal, CGST, round-off, total, and amount paid.
- Uses PSM 11 for SGST label detection because the sample experiment showed
  that PSM 11 detected the SGST label when PSM 6 did not.
- Tracks OCR word coordinates and confidence.
- Finds multiword labels by spatial proximity rather than relying only on
  Tesseract's word-list order.
- Rejects percentage tokens as monetary values.
- Does not concatenate split tokens such as 684 and 00.
- Keeps low-confidence amounts as proposals for human review, not final values.

## Receipt-layout limitation

The default crop coordinates are based on the 500x333 hotel receipt used
during development. They are not a universal receipt template. Adjust
DEFAULT_REGIONS in the module for a different image layout.

## Safety

This is not production-ready. It does not infer missing tax amounts, repair
malformed decimal values, or use arithmetic to manufacture OCR results.
Ambiguous and low-confidence values remain flagged for review. The original
image should be inspected before confirming any financial field.
