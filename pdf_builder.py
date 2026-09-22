"""
Renders AI-generated markdown notes into a polished, cover-page-and-table-of-contents
style PDF using ReportLab (pure Python, no system dependencies - which is what makes
this safe to run on a free-tier host).
"""
from __future__ import annotations

import os
import re
import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Frame,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    ListFlowable,
    ListItem,
    Preformatted,
    PageBreak,
    HRFlowable,
    NextPageTemplate,
)
from reportlab.platypus.tableofcontents import TableOfContents

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
PRIMARY = colors.HexColor("#4F46E5")     # indigo-600
PRIMARY_DARK = colors.HexColor("#3730A3")  # indigo-800
TEXT = colors.HexColor("#1E293B")        # slate-800
MUTED = colors.HexColor("#64748B")       # slate-500
LIGHT_BG = colors.HexColor("#EEF2FF")    # indigo-50
CODE_BG = colors.HexColor("#F1F5F9")     # slate-100
RULE = colors.HexColor("#E2E8F0")        # slate-200

class _NotesDocTemplate(BaseDocTemplate):
    """BaseDocTemplate that resets heading/TOC bookkeeping on every multiBuild pass."""

    def __init__(self, *args, notes_pdf=None, **kwargs):
        self._notes_pdf = notes_pdf
        super().__init__(*args, **kwargs)

    def build(self, *args, **kwargs):
        self._notes_pdf._heading_counter = 0
        super().build(*args, **kwargs)

    def afterFlowable(self, flowable):
        self._notes_pdf._after_flowable(flowable)


_FONTS_REGISTERED = False


def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    try:
        pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(BASE_DIR, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(
            TTFont("DejaVuSans-Bold", os.path.join(BASE_DIR, "DejaVuSans-Bold.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("DejaVuSans-Oblique", os.path.join(BASE_DIR, "DejaVuSans-Oblique.ttf"))
        )
        pdfmetrics.registerFontFamily(
            "DejaVuSans",
            normal="DejaVuSans",
            bold="DejaVuSans-Bold",
            italic="DejaVuSans-Oblique",
            boldItalic="DejaVuSans-Bold",
        )
    except Exception:
        # Fall back to built-in Helvetica if the ttf files are missing for any reason.
        pass
    _FONTS_REGISTERED = True


def _body_font():
    return "DejaVuSans" if "DejaVuSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"


def _bold_font():
    return (
        "DejaVuSans-Bold"
        if "DejaVuSans-Bold" in pdfmetrics.getRegisteredFontNames()
        else "Helvetica-Bold"
    )


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def _build_styles():
    body = _body_font()
    bold = _bold_font()
    return {
        "CoverTitle": ParagraphStyle(
            "CoverTitle", fontName=bold, fontSize=30, leading=36, textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "CoverSubtitle": ParagraphStyle(
            "CoverSubtitle", fontName=body, fontSize=14, leading=20,
            textColor=colors.HexColor("#E0E7FF"), alignment=TA_CENTER,
        ),
        "CoverMeta": ParagraphStyle(
            "CoverMeta", fontName=body, fontSize=10.5, leading=16,
            textColor=colors.HexColor("#C7D2FE"), alignment=TA_CENTER,
        ),
        "TOCHeading": ParagraphStyle(
            "TOCHeading", fontName=bold, fontSize=20, leading=26, textColor=PRIMARY_DARK,
            spaceAfter=14,
        ),
        "TOC1": ParagraphStyle(
            "TOC1", fontName=bold, fontSize=11.5, leading=18, textColor=TEXT, leftIndent=0,
        ),
        "TOC2": ParagraphStyle(
            "TOC2", fontName=body, fontSize=10.5, leading=16, textColor=MUTED, leftIndent=14,
        ),
        "DocTitle": ParagraphStyle(
            "DocTitle", fontName=bold, fontSize=22, leading=28, textColor=PRIMARY_DARK,
            spaceAfter=10,
        ),
        "Overview": ParagraphStyle(
            "Overview", fontName=body, fontSize=11, leading=16.5, textColor=MUTED,
            spaceAfter=14, alignment=TA_JUSTIFY,
        ),
        "H1": ParagraphStyle(
            "H1", fontName=bold, fontSize=17, leading=22, textColor=PRIMARY_DARK,
            spaceBefore=6, spaceAfter=10,
        ),
        "H2": ParagraphStyle(
            "H2", fontName=bold, fontSize=13.5, leading=18, textColor=PRIMARY,
            spaceBefore=14, spaceAfter=6,
        ),
        "H3": ParagraphStyle(
            "H3", fontName=bold, fontSize=11.5, leading=16, textColor=TEXT,
            spaceBefore=10, spaceAfter=4,
        ),
        "Body": ParagraphStyle(
            "Body", fontName=body, fontSize=10.3, leading=15.5, textColor=TEXT,
            spaceAfter=7, alignment=TA_JUSTIFY,
        ),
        "Bullet": ParagraphStyle(
            "Bullet", fontName=body, fontSize=10.3, leading=15, textColor=TEXT,
            spaceAfter=3,
        ),
        "Quote": ParagraphStyle(
            "Quote", fontName=body, fontSize=10.3, leading=15.5,
            textColor=PRIMARY_DARK, alignment=TA_LEFT,
        ),
        "Code": ParagraphStyle(
            "Code", fontName="Courier", fontSize=8.8, leading=12.5, textColor=TEXT,
        ),
        "TableCell": ParagraphStyle(
            "TableCell", fontName=body, fontSize=9.3, leading=13, textColor=TEXT,
        ),
        "TableHeader": ParagraphStyle(
            "TableHeader", fontName=bold, fontSize=9.3, leading=13, textColor=colors.white,
        ),
    }


# ---------------------------------------------------------------------------
# Inline markdown -> ReportLab mini-markup
# ---------------------------------------------------------------------------
def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    text = _escape(text.strip())
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier" size="9">\1</font>', text)
    return text


_BULLET_RE = re.compile(r"^(\s*)([-*])\s+(.*)$")
_NUMBERED_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
_QUOTE_RE = re.compile(r"^>\s?(.*)$")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
_TABLE_SEP_RE = re.compile(r"^\|?[\s:|-]+\|?$")
_HR_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
_FENCE_RE = re.compile(r"^```")


class NotesPDF:
    """Builds a designed PDF from markdown notes text."""

    def __init__(self, title: str, source_label: str | None = None):
        _register_fonts()
        self.title = title.strip() or "Video Notes"
        self.source_label = source_label
        self.styles = _build_styles()
        self.toc = TableOfContents()
        self.toc.levelStyles = [self.styles["TOC1"], self.styles["TOC2"]]
        self._heading_counter = 0

    # -- page templates -----------------------------------------------------
    def _on_cover(self, canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(PRIMARY)
        canvas.rect(0, 0, width, height, stroke=0, fill=1)
        canvas.setFillColor(PRIMARY_DARK)
        canvas.rect(0, height - 3.2 * cm, width, 3.2 * cm, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#818CF8"))
        canvas.rect(0, 0, width, 0.6 * cm, stroke=0, fill=1)
        canvas.restoreState()

    def _on_content(self, canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(2 * cm, height - 1.6 * cm, width - 2 * cm, height - 1.6 * cm)
        canvas.setFont(_body_font(), 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(2 * cm, height - 1.35 * cm, "AutoNote")
        canvas.drawRightString(width - 2 * cm, height - 1.35 * cm, self.title[:70])

        canvas.line(2 * cm, 1.5 * cm, width - 2 * cm, 1.5 * cm)
        canvas.drawCentredString(width / 2, 1.05 * cm, f"Page {doc.page}")
        canvas.drawString(2 * cm, 1.05 * cm, "Generated by AutoNote")
        canvas.drawRightString(
            width - 2 * cm, 1.05 * cm, datetime.date.today().strftime("%d %b %Y")
        )
        canvas.restoreState()

    def _after_flowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style_name = getattr(flowable.style, "name", "")
        if style_name not in ("H1", "H2"):
            return
        text = flowable.getPlainText()
        level = 0 if style_name == "H1" else 1
        self._heading_counter += 1
        key = f"h-{self._heading_counter}"
        doc = self._current_doc
        doc.canv.bookmarkPage(key)
        doc.canv.addOutlineEntry(text, key, level=level, closed=False)
        doc.notify("TOCEntry", (level, text, doc.page, key))

    # -- markdown -> flowables -----------------------------------------------
    def _heading_flowable(self, level: int, text: str):
        style_key = {1: "H1", 2: "H2", 3: "H3", 4: "H3"}.get(level, "H3")
        style = self.styles[style_key]
        para = Paragraph(_inline(text), style)
        flows = []
        if level == 1 and self._heading_counter > 0:
            flows.append(PageBreak())
        flows.append(para)
        if level == 1:
            flows.append(
                HRFlowable(width="100%", thickness=1.4, color=PRIMARY, spaceAfter=8, spaceBefore=2)
            )
        return flows

    def _quote_flowable(self, lines: list[str]):
        text = _inline(" ".join(lines))
        para = Paragraph(text, self.styles["Quote"])
        bar = Table(
            [["", para]],
            colWidths=[0.2 * cm, None],
            style=TableStyle(
                [
                    ("BACKGROUND", (1, 0), (1, 0), LIGHT_BG),
                    ("BACKGROUND", (0, 0), (0, 0), PRIMARY),
                    ("LEFTPADDING", (1, 0), (1, 0), 10),
                    ("RIGHTPADDING", (1, 0), (1, 0), 10),
                    ("TOPPADDING", (1, 0), (1, 0), 8),
                    ("BOTTOMPADDING", (1, 0), (1, 0), 8),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 0),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            ),
        )
        return [Spacer(1, 4), bar, Spacer(1, 8)]

    def _code_flowable(self, lines: list[str]):
        code = "\n".join(lines)
        pre = Preformatted(code, self.styles["Code"])
        wrapped = Table(
            [[pre]],
            colWidths=[None],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), CODE_BG),
                    ("LEFTPADDING", (0, 0), (0, 0), 10),
                    ("RIGHTPADDING", (0, 0), (0, 0), 10),
                    ("TOPPADDING", (0, 0), (0, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (0, 0), 8),
                    ("BOX", (0, 0), (0, 0), 0.6, RULE),
                ]
            ),
        )
        return [Spacer(1, 4), wrapped, Spacer(1, 8)]

    def _table_flowable(self, rows: list[list[str]]):
        data = []
        for r_idx, row in enumerate(rows):
            style = self.styles["TableHeader"] if r_idx == 0 else self.styles["TableCell"]
            data.append([Paragraph(_inline(cell), style) for cell in row])
        table = Table(data, hAlign="LEFT", repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                    ("GRID", (0, 0), (-1, -1), 0.5, RULE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return [Spacer(1, 4), table, Spacer(1, 10)]

    def _list_flowable(self, items: list[tuple[int, str]], ordered: bool):
        bullet_style = self.styles["Bullet"]
        list_items = []
        for indent, text in items:
            para = Paragraph(_inline(text), bullet_style)
            list_items.append(ListItem(para, leftIndent=10 + indent * 14))
        kwargs = dict(
            bulletFontName=_body_font(),
            bulletFontSize=9,
            leftIndent=16,
            spaceBefore=2,
            spaceAfter=6,
            bulletColor=PRIMARY,
        )
        if ordered:
            return [ListFlowable(list_items, bulletType="1", **kwargs)]
        return [ListFlowable(list_items, bulletType="bullet", start="•", **kwargs)]

    def parse(self, markdown_text: str) -> list:
        lines = markdown_text.replace("\r\n", "\n").split("\n")
        flowables: list = []
        i, n = 0, len(lines)

        paragraph_buffer: list[str] = []
        list_buffer: list[tuple[int, str]] = []
        list_ordered = False

        def flush_paragraph():
            if paragraph_buffer:
                text = " ".join(paragraph_buffer).strip()
                if text:
                    flowables.append(Paragraph(_inline(text), self.styles["Body"]))
                paragraph_buffer.clear()

        def flush_list():
            nonlocal list_ordered
            if list_buffer:
                flowables.extend(self._list_flowable(list_buffer, list_ordered))
                list_buffer.clear()

        while i < n:
            raw = lines[i]
            line = raw.rstrip()
            stripped = line.strip()

            if not stripped:
                flush_paragraph()
                flush_list()
                i += 1
                continue

            if _FENCE_RE.match(stripped):
                flush_paragraph()
                flush_list()
                i += 1
                code_lines = []
                while i < n and not _FENCE_RE.match(lines[i].strip()):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing fence
                flowables.extend(self._code_flowable(code_lines))
                continue

            heading_match = _HEADING_RE.match(stripped)
            if heading_match:
                flush_paragraph()
                flush_list()
                level = len(heading_match.group(1))
                flowables.extend(self._heading_flowable(level, heading_match.group(2)))
                i += 1
                continue

            if _HR_RE.match(stripped):
                flush_paragraph()
                flush_list()
                flowables.append(Spacer(1, 4))
                flowables.append(HRFlowable(width="100%", thickness=0.6, color=RULE))
                flowables.append(Spacer(1, 8))
                i += 1
                continue

            quote_match = _QUOTE_RE.match(stripped)
            if quote_match:
                flush_paragraph()
                flush_list()
                quote_lines = [quote_match.group(1)]
                i += 1
                while i < n and _QUOTE_RE.match(lines[i].strip()):
                    quote_lines.append(_QUOTE_RE.match(lines[i].strip()).group(1))
                    i += 1
                flowables.extend(self._quote_flowable(quote_lines))
                continue

            if _TABLE_ROW_RE.match(stripped) and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1].strip()):
                flush_paragraph()
                flush_list()
                rows = [
                    [c.strip() for c in _TABLE_ROW_RE.match(stripped).group(1).split("|")]
                ]
                i += 2
                while i < n and _TABLE_ROW_RE.match(lines[i].strip()):
                    rows.append(
                        [c.strip() for c in _TABLE_ROW_RE.match(lines[i].strip()).group(1).split("|")]
                    )
                    i += 1
                flowables.extend(self._table_flowable(rows))
                continue

            bullet_match = _BULLET_RE.match(line)
            numbered_match = _NUMBERED_RE.match(line)
            if bullet_match or numbered_match:
                flush_paragraph()
                is_ordered = bool(numbered_match)
                if list_buffer and list_ordered != is_ordered:
                    flush_list()
                list_ordered = is_ordered
                match = bullet_match or numbered_match
                indent_str, content = match.group(1), match.group(3)
                indent_level = min(len(indent_str) // 2, 3)
                list_buffer.append((indent_level, content))
                i += 1
                continue

            paragraph_buffer.append(stripped)
            i += 1

        flush_paragraph()
        flush_list()
        return flowables

    # -- build ---------------------------------------------------------------
    def build(self, markdown_text: str, output_path: str, source_label: str | None = None):
        source_label = source_label or self.source_label
        page_w, page_h = A4
        margin = 2 * cm

        doc = _NotesDocTemplate(
            output_path,
            notes_pdf=self,
            pagesize=A4,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=2.1 * cm,
            bottomMargin=2 * cm,
            title=self.title,
            author="AutoNote",
        )
        self._current_doc = doc

        cover_frame = Frame(0, 0, page_w, page_h, id="cover", leftPadding=0, rightPadding=0)
        content_frame = Frame(
            margin, margin, page_w - 2 * margin, page_h - margin - 2.1 * cm, id="content"
        )

        doc.addPageTemplates(
            [
                PageTemplate(id="Cover", frames=[cover_frame], onPage=self._on_cover),
                PageTemplate(id="Content", frames=[content_frame], onPage=self._on_content),
            ]
        )
        story = self._build_cover(source_label)
        story.append(NextPageTemplate("Content"))
        story.append(PageBreak())
        story.extend(self._build_toc())
        story.append(PageBreak())
        story.extend(self.parse(markdown_text))

        doc.multiBuild(story)
        return output_path

    def _build_cover(self, source_label: str | None):
        width, _ = A4
        usable = width - 6 * cm
        flows = [Spacer(1, 8.5 * cm)]
        flows.append(Paragraph(_escape(self.title), self.styles["CoverTitle"]))
        flows.append(Spacer(1, 14))
        flows.append(Paragraph("AI-Generated Detailed Notes", self.styles["CoverSubtitle"]))
        flows.append(Spacer(1, 40))
        if source_label:
            flows.append(Paragraph(_escape(source_label), self.styles["CoverMeta"]))
        flows.append(
            Paragraph(datetime.date.today().strftime("Generated on %d %B %Y"), self.styles["CoverMeta"])
        )
        flows.append(Spacer(1, 6))
        flows.append(Paragraph("autonote", self.styles["CoverMeta"]))
        # Wrap in a frame-width-agnostic container by centering via style alignment already set.
        return flows

    def _build_toc(self):
        flows = [Spacer(1, 4), Paragraph("Table of Contents", self.styles["TOCHeading"])]
        flows.append(self.toc)
        return flows


def build_notes_pdf(markdown_text: str, output_path: str, title: str, source_label: str | None = None) -> str:
    pdf = NotesPDF(title=title, source_label=source_label)
    return pdf.build(markdown_text, output_path, source_label=source_label)
