"""Importiert die Uebungsbilder aus den NEOLYMP-Trainingsplan-PDFs nach instance/neolymp/.

Die Bilder sind © NEOLYMP GmbH und gehoeren NICHT ins Git-Repo (public). Sie liegen nur auf dem Server
(instance/ ist per .gitignore ausgeschlossen) und werden nach dem Login ausgeliefert.

Aufruf (PyMuPDF nur fuer diesen Import noetig: pip install pymupdf):
    python scripts/import_neolymp_pdf.py "Plan W 1-3.pdf" "Plan W 4-5.pdf" [--out instance/neolymp]

Je Uebungsseite steht unten "2.N. Titel" und es gibt zwei Bilder (Start-/Endposition). Der Titel wird
ueber backend/data/neolymp_exercises.json (Name oder `pdf_title`) dem Uebungsnamen der App zugeordnet.
Ergebnis: <out>/images/<slug>-1.jpg, -2.jpg und <out>/index.json (Uebungsname -> Dateiliste).
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "backend" / "data" / "neolymp_exercises.json"
CAPTION = re.compile(r"^\d+\.\d+\.\s*(.+)$")
LOGO_SIZE = (304, 96)  # NEOLYMP-Logo, steht auf jeder Seite
MIN_IMAGE_WIDTH = 400  # kleinere Bilder sind keine Uebungsfotos
JPG_QUALITY = 80


def slugify(title: str) -> str:
    """Dateiname-tauglicher Titel (Umlaute/ß aufgeloest)."""
    table = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"})
    return re.sub(r"[^a-z0-9]+", "-", title.translate(table).lower()).strip("-")


def exercise_pages(pdf_path: Path):
    """Liefert (Titel, [Bild-xrefs]) je Uebungsseite einer PDF."""
    import pymupdf

    doc = pymupdf.open(pdf_path)
    for page in doc:
        title = next(
            (m.group(1).strip() for line in reversed(page.get_text().splitlines()) if (m := CAPTION.match(line.strip()))),
            None,
        )
        if title is None:
            continue
        xrefs = []
        for image in page.get_images(full=True):
            info = doc.extract_image(image[0])
            if (info["width"], info["height"]) != LOGO_SIZE and info["width"] >= MIN_IMAGE_WIDTH:
                xrefs.append(image[0])
        if xrefs:
            yield doc, title, xrefs


def main(argv: list[str] | None = None) -> int:
    """Liest die PDFs und schreibt Bilder + index.json. Gibt 0 zurueck, wenn alle Manifest-Uebungen Bilder haben."""
    import pymupdf

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "instance" / "neolymp")
    args = parser.parse_args(argv)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_title = {entry.get("pdf_title", name): name for name, entry in manifest.items()}
    images_dir = args.out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    index: dict[str, list[str]] = {}
    for pdf in args.pdfs:
        for doc, title, xrefs in exercise_pages(pdf):
            name = by_title.get(title)
            if name is None or name in index:  # nicht benoetigt oder schon aus einer anderen PDF
                continue
            files = []
            for number, xref in enumerate(xrefs, start=1):
                file = f"{slugify(name)}-{number}.jpg"
                pymupdf.Pixmap(doc, xref).save(images_dir / file, jpg_quality=JPG_QUALITY)
                files.append(file)
            index[name] = files
            logger.info("%s -> %s", name, ", ".join(files))
    (args.out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = sorted(set(manifest) - set(index))
    for name in missing:
        logger.warning("kein Bild gefunden: %s", name)
    logger.info("%d von %d Übungen importiert nach %s", len(index), len(manifest), args.out)
    return 1 if missing else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
