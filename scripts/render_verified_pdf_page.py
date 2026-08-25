#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

import pypdfium2 as pdfium


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render page 1 from PDF bytes bound to an expected SHA-256."
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("expected_sha256")
    return parser.parse_args()


def main() -> int:
    args = _args()
    pdf_bytes = args.pdf.read_bytes()
    actual_digest = "sha256:" + hashlib.sha256(pdf_bytes).hexdigest()
    if actual_digest != args.expected_sha256:
        raise ValueError("PDF bytes do not match the expected SHA-256")

    document = pdfium.PdfDocument(pdf_bytes)
    try:
        if len(document) < 1:
            raise ValueError("PDF has no renderable pages")
        page = document[0]
        try:
            bitmap = page.render(scale=2)
            try:
                image = bitmap.to_pil().convert("RGB").copy()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    try:
        image.save(temporary, format="PNG", optimize=False, compress_level=9)
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
