"""Render the concise brief and candidate appendix as submission-sized PDFs."""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BriefTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#173D4C"), spaceAfter=16))
styles.add(ParagraphStyle(name="BriefSection", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor("#173D4C"), spaceAfter=12))
styles.add(ParagraphStyle(name="BriefBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.4, leading=13.7, spaceAfter=11))
styles.add(ParagraphStyle(name="BriefCode", fontName="Courier", fontSize=7.1, leading=10, textColor=colors.HexColor("#173D4C"), backColor=colors.HexColor("#EFF5F6"), leftIndent=8, rightIndent=8, spaceBefore=4, spaceAfter=11))


def markup(value: str) -> str:
    escaped = html.escape(value)
    return re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", escaped)


def footer(canvas, document) -> None:
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#637985"))
    canvas.drawString(0.75 * inch, 0.5 * inch, "Evidence Ledger · synthetic prototype")
    canvas.drawRightString(A4[0] - 0.75 * inch, 0.5 * inch, str(document.page))


def build(source: Path, dest: Path, page_sections: bool) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    story = []
    paragraph = []
    code = []
    in_code = False
    section_count = 0

    def flush() -> None:
        if paragraph:
            story.append(Paragraph(markup(" ".join(paragraph)), styles["BriefBody"]))
            paragraph.clear()

    for line in lines:
        if line.startswith("```"):
            flush()
            if in_code:
                story.append(Preformatted("\n".join(code), styles["BriefCode"]))
                code.clear()
            in_code = not in_code
        elif in_code:
            code.append(line)
        elif line.startswith("# "):
            flush()
            story.append(Paragraph(markup(line[2:]), styles["BriefTitle"]))
        elif line.startswith("## "):
            flush()
            if page_sections and section_count:
                story.append(PageBreak())
            section_count += 1
            story.append(Paragraph(markup(line[3:]), styles["BriefSection"]))
        elif not line.strip():
            flush()
        else:
            paragraph.append(line.strip())
    flush()
    document = SimpleDocTemplate(str(dest), pagesize=A4, rightMargin=0.75 * inch, leftMargin=0.75 * inch, topMargin=0.75 * inch, bottomMargin=0.72 * inch)
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    build(DOCS / "problem_brief.md", DOCS / "problem_brief.pdf", True)
    build(DOCS / "ai_use_appendix.md", DOCS / "ai_use_appendix.pdf", False)
    print("Created problem_brief.pdf and ai_use_appendix.pdf")


if __name__ == "__main__":
    main()
