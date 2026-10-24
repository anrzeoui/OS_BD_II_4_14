"""Build the two PDFs from Markdown. Dev-only: pip install reportlab pillow.

Run from project root: python3 docs/build_docs.py
FONT_DIR may point to a directory containing DejaVuSans*.ttf.
"""
import os
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                               TableStyle, PageBreak, Image, Preformatted, KeepTogether)
from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parent
FONTS = Path(os.environ.get("FONT_DIR", "/usr/share/fonts/truetype/dejavu"))
for name, file in [("D", "DejaVuSans.ttf"), ("DB", "DejaVuSans-Bold.ttf"),
                   ("DM", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
pdfmetrics.registerFontFamily("D", normal="D", bold="DB", italic="D", boldItalic="DB")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle("BodyMN", fontName="D", fontSize=10, leading=15,
                          textColor=colors.HexColor("#25354a"), spaceAfter=9))
styles.add(ParagraphStyle("TitleMN", fontName="DB", fontSize=27, leading=34,
                          textColor=colors.HexColor("#0f172a"), spaceAfter=20))
styles.add(ParagraphStyle("H2MN", fontName="DB", fontSize=16, leading=22,
                          textColor=colors.HexColor("#0f766e"), spaceBefore=7, spaceAfter=12, keepWithNext=True))
styles.add(ParagraphStyle("H3MN", fontName="DB", fontSize=11.5, leading=16,
                          textColor=colors.HexColor("#0f172a"), spaceBefore=8, spaceAfter=8, keepWithNext=True))
styles.add(ParagraphStyle("CellMN", fontName="D", fontSize=8.5, leading=12))
styles.add(ParagraphStyle("CaptionMN", fontName="D", fontSize=8, leading=11,
                          textColor=colors.HexColor("#64748b"), spaceAfter=12))
styles.add(ParagraphStyle("CodeMN", fontName="DM", fontSize=8, leading=12,
                          backColor=colors.HexColor("#f1f5f9"), borderPadding=10,
                          spaceBefore=6, spaceAfter=15))


def inline(text):
    text = escape(text)
    return re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)


def footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(48, 42, width - 48, 42)
    canvas.setFont("D", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(48, 29, "F.CSM302  /  II-4-14  /  MEMORY LAB")
    canvas.drawRightString(width - 48, 29, str(doc.page))
    canvas.restoreState()


def build(source, output):
    content = (ROOT / source).read_text(encoding="utf-8").replace("–", "-").replace("—", "-")
    story = []
    for page_index, section in enumerate(content.split("<!-- PAGE -->")):
        if page_index:
            story.append(PageBreak())
        lines = section.strip().splitlines()
        index = 0
        image_width = 350 if section.count("![") > 1 else 460
        while index < len(lines):
            line = lines[index].strip()
            if not line:
                index += 1
                continue
            if line.startswith("```"):
                code = []
                index += 1
                while index < len(lines) and not lines[index].startswith("```"):
                    code.append(lines[index])
                    index += 1
                story.append(Preformatted("\n".join(code), styles["CodeMN"]))
            elif line.startswith("|"):
                rows = []
                while index < len(lines) and lines[index].strip().startswith("|"):
                    values = [v.strip() for v in lines[index].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r"[-: ]+", value) for value in values):
                        rows.append([Paragraph(inline(v), styles["CellMN"]) for v in values])
                    index += 1
                count = len(rows[0])
                widths = [499 / count] * count
                if count == 3:
                    widths = [162, 229, 108] if source == "Report.md" and page_index == 4 else [143, 199, 157]
                table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9efec")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#80b6ac")),
                ]))
                story.extend([table, Spacer(1, 12)])
                continue
            elif line.startswith("!["):
                match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", line)
                if not match:
                    raise ValueError(line)
                caption, filename = match.groups()
                path = ROOT / filename
                with PILImage.open(path) as picture:
                    w, h = picture.size
                image = Image(str(path), width=image_width, height=image_width * h / w)
                image.hAlign = "CENTER"
                story.append(KeepTogether([image, Spacer(1, 5), Paragraph(inline(caption), styles["CaptionMN"])]))
            elif line.startswith("### "):
                story.append(Paragraph(inline(line[4:]), styles["H3MN"]))
            elif line.startswith("## "):
                story.append(Paragraph(inline(line[3:]), styles["H2MN"]))
            elif line.startswith("# "):
                story.append(Spacer(1, 25) if page_index == 0 else Spacer(1, 5))
                story.append(Paragraph(inline(line[2:]), styles["TitleMN"]))
            elif line.startswith("- "):
                story.append(Paragraph("• " + inline(line[2:]), styles["BodyMN"]))
            else:
                paragraph = [line]
                while index + 1 < len(lines) and lines[index + 1].strip() and not re.match(r"[#|!`-]", lines[index + 1]):
                    index += 1
                    paragraph.append(lines[index].strip())
                story.append(Paragraph(inline(" ".join(paragraph)), styles["BodyMN"]))
            index += 1
    doc = SimpleDocTemplate(str(ROOT / output), pagesize=A4,
                            leftMargin=48, rightMargin=48, topMargin=43, bottomMargin=56,
                            title="Memory Lab - " + source.removesuffix(".md"), author="II-4-14 / draft")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(ROOT / output)


if __name__ == "__main__":
    build("Report.md", "II-4-14_BD1_Report.pdf")
    build("Manual.md", "II-4-14_Manual.pdf")
