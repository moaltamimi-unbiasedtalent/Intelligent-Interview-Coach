#!/usr/bin/env python
"""07C: real LOCAL OCR on synthetic image/PDF samples, no network or paid service.

Records observations, not a language/production qualification. No real candidate
file is read. Outputs only to an explicit --out path; temp inputs stay in memory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import textwrap
import time
import unicodedata
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SAMPLES = {
    "en": "Synthetic OCR sample. The candidate explains a project and its results.",
    "de": "Synthetisches OCR-Beispiel. Die Person beschreibt ein Projekt und seine Ergebnisse.",
    "fr": "Exemple OCR artificiel. La personne explique un projet et ses résultats.",
    "es": "Ejemplo OCR sintético. La persona explica un proyecto y sus resultados.",
    "it": "Esempio OCR sintetico. La persona descrive un progetto e i suoi risultati.",
    "pt": "Exemplo OCR sintético. A pessoa descreve um projeto e os seus resultados.",
    "nl": "Synthetisch OCR-voorbeeld. De kandidaat beschrijft een project en de resultaten.",
}


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def distance(left: Sequence, right: Sequence) -> int:
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        next_row = [i]
        for j, b in enumerate(right, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = next_row
    return row[-1]


def run(font_path: Path) -> dict:
    # Apply the existing no-.env, no-development-DB isolation boundary first.
    import tests.conftest  # noqa: F401
    import pytesseract
    from PIL import Image, ImageDraw, ImageFont
    from src.documents.ocr import TesseractOcrEngine, ocr_parse, ocr_runtime_status

    engine = TesseractOcrEngine()
    font = ImageFont.truetype(str(font_path), 42)
    rows = []
    for locale, expected in SAMPLES.items():
        lines = textwrap.wrap(expected, width=58)
        image = Image.new("RGB", (1600, 120 + 70 * len(lines)), "white")
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            draw.text((60, 55 + index * 70), line, fill="black", font=font)
        for fmt in ("png", "pdf"):
            content = BytesIO()
            if fmt == "pdf":
                image.save(content, format="PDF", resolution=200.0,
                           creationDate=time.gmtime(0), modDate=time.gmtime(0))
            else:
                image.save(content, format="PNG")
            data = content.getvalue()
            entry = {"locale": locale, "format": fmt, "expected": expected,
                     "input_sha256": hashlib.sha256(data).hexdigest()}
            try:
                parsed = ocr_parse(engine, data, fmt, lang=locale)
                observed = " ".join(segment.text for segment in parsed.segments)
                reference, actual = normalize(expected), normalize(observed)
                entry.update(status="OBSERVED", observed=observed,
                             character_error_rate=round(distance(reference, actual) / len(reference), 6),
                             word_error_rate=round(distance(reference.split(), actual.split()) / len(reference.split()), 6),
                             pages=[segment.page for segment in parsed.segments], origin=parsed.origin)
            except Exception as exc:
                entry.update(status="NOT VERIFIED", error_type=type(exc).__name__)
            rows.append(entry)
    return {"sample_set": "07C-local-synthetic-v1", "observed_at": datetime.now(timezone.utc).isoformat(),
            "mode": "REAL LOCAL OCR / SYNTHETIC DOCUMENTS", "paid_calls": 0, "network_calls": 0,
            "real_candidate_documents": 0, "human_quality_review": "NOT RUN", "staging": "NOT RUN",
            "qualification": "No gate or language approved; no acceptance threshold invented",
            "font": font_path.name, "tesseract_version": str(pytesseract.get_tesseract_version()),
            "pillow_version": importlib.metadata.version("Pillow"), "runtime": ocr_runtime_status(),
            "ocr_adapter_sha256": hashlib.sha256((ROOT / "src/documents/ocr.py").read_bytes()).hexdigest(),
            "normalization": "NFKC, casefold, collapse whitespace; punctuation retained",
            "results": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", required=True, type=Path, help="Existing local TrueType font; no download")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.font)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    measured = sum(row["status"] == "OBSERVED" for row in report["results"])
    print(f"Recorded {measured}/{len(report['results'])} actual local OCR observations; zero paid/network calls; no gate approved.")
    return 0 if measured == len(report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
