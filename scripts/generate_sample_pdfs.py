from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from scripts.sample_content import SAMPLES


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "data/sample_documents"
NAVY = colors.HexColor("#11283C")
TEAL = colors.HexColor("#11665E")
INK = colors.HexColor("#263E50")
MUTED = colors.HexColor("#506475")


def paragraph(pdf, text, x, y, width, font, size, leading, color):
    style = ParagraphStyle("body", fontName=font, fontSize=size, leading=leading, textColor=color, alignment=TA_LEFT)
    block = Paragraph(escape(text), style)
    _, height = block.wrap(width, 450)
    block.drawOn(pdf, x, y - height)
    return y - height


def generate():
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for document in SAMPLES:
        target = SAMPLE_DIR / document["filename"]
        title = target.stem
        pdf = canvas.Canvas(str(target), pagesize=letter, invariant=1, pageCompression=1)
        pdf.setTitle(title)
        pdf.setAuthor("EduEvidence AI synthetic course library")
        pdf.setSubject("Original synthetic demonstration curriculum for Project 022")
        for number, (heading, subheading, paragraphs) in enumerate(document["pages"], 1):
            pdf.setFillColor(NAVY)
            pdf.rect(0, 650, 612, 142, fill=1, stroke=0)
            pdf.setFillColor(colors.HexColor("#71D6C3"))
            pdf.rect(52, 742, 26, 3, fill=1, stroke=0)
            paragraph(pdf, document["code"] + "  /  SYNTHETIC COURSE LIBRARY", 52, 728, 508, "Helvetica-Bold", 9, 12, colors.HexColor("#94D4CA"))
            paragraph(pdf, title, 52, 695, 508, "Helvetica-Bold", 20, 24, colors.white)
            y = paragraph(pdf, heading, 52, 600, 508, "Helvetica-Bold", 23, 28, NAVY)
            y = paragraph(pdf, subheading, 52, y - 12, 508, "Helvetica-Bold", 12, 18, TEAL)
            y -= 32
            for content in paragraphs:
                pdf.setFillColor(colors.HexColor("#90C7BE"))
                pdf.circle(56, y - 8, 2.25, stroke=0, fill=1)
                y = paragraph(pdf, content, 71, y, 482, "Helvetica", 12, 19, INK) - 19
            if y < 135:
                raise RuntimeError(f"Content overflows page {number} of {title}")
            pdf.setStrokeColor(colors.HexColor("#D9E4E8"))
            pdf.line(52, 82, 560, 82)
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 8)
            pdf.drawString(52, 60, "EduEvidence AI  /  Synthetic demonstration material")
            pdf.drawRightString(560, 60, f"Page {number} of {len(document['pages'])}")
            pdf.showPage()
        pdf.save()
        print(f"{target.name} ({len(document['pages'])} pages)")


if __name__ == "__main__":
    generate()

