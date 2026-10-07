"Create editable OOXML Word and a typeset PDF from the assemb" "led manuscript."

import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/r"
"elationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
WIDTH = 487.3
BODY_TWIPS = 9746


def esc(value):
    return html.escape(str(value), quote=True)


def parse(root, filename="HalfTrend_NIFTY50_Publication_Candidate.html"):
    text = (root / filename).read_text(encoding="utf-8")
    body = text.split("<body>", 1)[1].split("</body>", 1)[0]
    body = body.replace("&nbsp;", "&#160;")
    body = re.sub(r"<img ([^>]+)>", r"<img \1/>", body)
    return list(ET.fromstring("<root>" + body + "</root>"))


def text_of(node):
    return "".join(node.itertext())


def image_path(node, root):
    filename = Path(unquote(urlparse(node.find("img").attrib["src"]).path)).name
    return root / "figures" / filename


def run(text, bold=False, size=None, color=None):
    properties = "<w:b/>" if bold else ""
    if size:
        properties += f'<w:sz w:val="{size}"/>'
    if color:
        properties += f'<w:color w:val="{color}"/>'
    return (
        f"<w:r><w:rPr>{properties}</w:rPr>"
        f'<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'
    )


def paragraph(text, style="Body", keep=False, align=None):
    properties = f'<w:pStyle w:val="{style}"/>'
    if keep:
        properties += "<w:keepNext/>"
    if align:
        properties += f'<w:jc w:val="{align}"/>'
    return f"<w:p><w:pPr>{properties}</w:pPr>{run(text)}</w:p>"


def style_def(
    name,
    size,
    *,
    bold=False,
    align="both",
    before=0,
    after=120,
    color="202020",
    outline=None,
    keep=False,
):
    p = (
        f'<w:jc w:val="{align}"/><w:spacing w:before="{before}" '
        f'w:after="{after}" w:line="276" w:lineRule="auto"/><w:widowControl/>'
    )
    if keep:
        p += "<w:keepNext/>"
    if outline is not None:
        p += f'<w:outlineLvl w:val="{outline}"/>'
    r = (
        f'<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
        f'<w:sz w:val="{size}"/><w:color w:val="{color}"/>'
    )
    if bold:
        r += "<w:b/>"
    return (
        f'<w:style w:type="paragraph" w:styleId="{name}">'
        f'<w:name w:val="{name}"/><w:pPr>{p}</w:pPr><w:rPr>{r}</w:rPr></w:style>'
    )


def export_docx(root, nodes):
    styles = (
        XML_DECL
        + f'<w:styles xmlns:w="{W}">'
        + "".join(
            [
                style_def("Body", 22),
                style_def(
                    "Heading1",
                    32,
                    bold=True,
                    align="left",
                    before=240,
                    color="173B55",
                    outline=0,
                    keep=True,
                ),
                style_def(
                    "Heading2",
                    24,
                    bold=True,
                    align="left",
                    before=180,
                    color="173B55",
                    outline=1,
                    keep=True,
                ),
                style_def(
                    "Title",
                    48,
                    bold=True,
                    align="center",
                    before=700,
                    after=300,
                    color="173B55",
                ),
                style_def("Subtitle", 30, align="center", before=160, after=250),
                style_def("Center", 22, align="center", after=160),
                style_def("Review", 20, align="left", before=200, color="924500"),
                style_def("Caption", 19, align="left", before=100, after=100),
                style_def("Note", 18, align="left", after=150),
                style_def("Reference", 20, align="left", after=80),
                style_def("Equation", 21, align="center", before=120, after=120),
                style_def("TableText", 18, align="left", after=0),
            ]
        )
        + "</w:styles>"
    )
    parts, images, links = [], [], []
    classes = {
        "title": "Title",
        "subtitle": "Subtitle",
        "center": "Center",
        "review": "Review",
        "caption": "Caption",
        "note": "Note",
        "reference": "Reference",
        "equation": "Equation",
    }
    for index, node in enumerate(nodes):
        tag, cls = node.tag, node.attrib.get("class", "")
        if tag in ["h1", "h2"]:
            parts.append(paragraph(text_of(node), "Heading" + tag[-1]))
        elif tag == "p" and cls == "pagebreak":
            parts.append(
                '<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
                '<w:r><w:br w:type="page"/></w:r></w:p>'
            )
        elif tag == "p" and cls == "figure":
            file = image_path(node, root)
            images.append(file)
            rid = f"image{len(images)}"
            with PILImage.open(file) as image:
                cx = int(6.6 * 914400)
                cy = int(cx * image.height / image.width)
            number = len(images)
            drawing = f"""<w:p><w:pPr><w:jc w:val="center"/><w:keepNext/></w:pPr><w:r>
            <w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">
            <wp:extent cx="{cx}" cy="{cy}"/>
            <wp:docPr id="{number}" name="Figure {number}" descr="{esc(file.stem)}"/>
            <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="{esc(file.name)}"/>
            <pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/>
            <a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr>
            <a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
            <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
            </pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"""
            parts.append(drawing)
        elif tag == "p":
            link = node.find("a")
            if link is not None:
                links.append(link.attrib["href"])
                rid = f"link{len(links)}"
                parts.append(
                    '<w:p><w:pPr><w:pStyle w:val="Reference"/></w:pPr>'
                    f'<w:hyperlink r:id="{rid}">{run(text_of(node), color="176B87")}'
                    "</w:hyperlink></w:p>"
                )
            else:
                keep = (
                    cls == "caption"
                    and index + 1 < len(nodes)
                    and nodes[index + 1].tag == "table"
                )
                parts.append(paragraph(text_of(node), classes.get(cls, "Body"), keep))
        elif tag == "table":
            rows = node.findall(".//tr")
            count = len(list(rows[0]))
            weights = [max(8, min(34, len(text_of(cell)))) for cell in rows[0]]
            total_weight = sum(weights)
            widths = [BODY_TWIPS * weight // total_weight for weight in weights]
            widths[-1] += BODY_TWIPS - sum(widths)
            table = [
                "<w:tbl><w:tblPr>",
                f'<w:tblW w:w="{BODY_TWIPS}" w:type="dxa"/>',
                '<w:tblLayout w:type="fixed"/><w:tblBorders>',
            ]
            for edge in ["top", "left", "bottom", "right", "insideH", "insideV"]:
                table.append(f'<w:{edge} w:val="single" w:sz="4" w:color="B7C4CE"/>')
            table += [
                '</w:tblBorders><w:tblCellMar><w:top w:w="65" w:type="dxa"/>',
                '<w:left w:w="65" w:type="dxa"/><w:bottom w:w="65" w:typ' 'e="dxa"/>',
                '<w:right w:w="65" w:type="dxa"/></w:tblCellMar></w:tblP'
                "r><w:tblGrid>",
            ]
            table += [f'<w:gridCol w:w="{width}"/>' for width in widths]
            table.append("</w:tblGrid>")
            for i, row in enumerate(rows):
                table.append(
                    "<w:tr><w:trPr><w:cantSplit/>"
                    + ("<w:tblHeader/>" if i == 0 else "")
                    + "</w:trPr>"
                )
                for j, (width, cell) in enumerate(zip(widths, row)):
                    fill = "173B55" if i == 0 else "F4F7F9" if i % 2 == 0 else "FFFFFF"
                    value = text_of(cell)
                    numeric = bool(
                        re.fullmatch(
                            r"(?:[-+]?\d[\d,]*(?:\.\d+)?%?|N/A|Unavailable)",
                            value.strip(),
                        )
                    )
                    alignment = "center" if i == 0 else "right" if numeric else "left"
                    table.append(
                        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
                        f'<w:shd w:fill="{fill}"/><w:vAlign w:val="center"/></w:tcPr>'
                        f'<w:p><w:pPr><w:pStyle w:val="TableText"/><w:jc w:val="{alignment}"/></w:pPr>'
                        + run(
                            value,
                            bold=i == 0,
                            color="FFFFFF" if i == 0 else "202020",
                        )
                        + "</w:p></w:tc>"
                    )
                table.append("</w:tr>")
            table.append("</w:tbl>")
            parts.append("".join(table))
            parts.append('<w:p><w:pPr><w:spacing w:after="80"/></w:pPr></w:p>')
    section = """<w:sectPr><w:headerReference w:type="default" r:id="header"/>
    <w:footerReference w:type="default" r:id="footer"/><w:pgSz w:w="11906" w:h="16838"/>
    <w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"
    w:header="540" w:footer="540" w:gutter="0"/></w:sectPr>"""
    document = (
        XML_DECL + f'<w:document xmlns:w="{W}" xmlns:r="{R}" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/w'
        'ordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/20'
        '06/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/'
        '2006/picture">'
        "<w:body>" + "".join(parts) + section + "</w:body></w:document>"
    )
    relationships = [
        f'<Relationship Id="{name}" Type="{R}/{kind}" Target="{target}"/>'
        for name, kind, target in [
            ("styles", "styles", "styles.xml"),
            ("settings", "settings", "settings.xml"),
            ("header", "header", "header1.xml"),
            ("footer", "footer", "footer1.xml"),
        ]
    ]
    relationships += [
        f'<Relationship Id="image{i}" Type="{R}/image" Target="media/{file.name}"/>'
        for i, file in enumerate(images, 1)
    ]
    relationships += [
        f'<Relationship Id="link{i}" Type="{R}/hyperlink" '
        f'Target="{esc(url)}" TargetMode="External"/>'
        for i, url in enumerate(links, 1)
    ]
    types = [
        '<Default Extension="rels" ContentType="application/vnd.openx'
        'mlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Default Extension="png" ContentType="image/png"/>',
    ]
    for part, kind in [
        ("document", "document.main"),
        ("styles", "styles"),
        ("settings", "settings"),
        ("header1", "header"),
        ("footer1", "footer"),
    ]:
        types.append(
            f'<Override PartName="/word/{part}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml"/>'
        )
    types.append(
        '<Override PartName="/docProps/core.xml" ContentType="applica'
        'tion/vnd.openxmlformats-package.core-properties+xml"/>'
    )
    header = (
        XML_DECL
        + f'<w:hdr xmlns:w="{W}">'
        + paragraph(
            "HALFTREND ON NIFTY 50 | WORKING PAPER", "Note", align="right"
        )
        + "</w:hdr>"
    )
    footer = (
        XML_DECL + f'<w:ftr xmlns:w="{W}"><w:p><w:pPr><w:jc w:val="center"/>'
        '<w:pStyle w:val="Note"/></w:pPr>'
        + run("Mohd Bilal | Working paper | Page ", size=16)
        + '<w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fld'
        "Simple></w:p></w:ftr>"
    )
    core = (
        XML_DECL + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.o'
        'rg/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>HalfTrend on NIFTY 50: Transaction Costs, Execution Sensitivity, "
        "and Simulated Call Calendar Spreads</dc:title>"
        "<dc:creator>Mohd Bilal</dc:creator><dc:description>Working paper; "
        "index-based futures proxy and SIMULATED call calendars.</dc:"
        "description></cp:coreProperties>"
    )
    file = root / "HalfTrend_NIFTY50_Publication_Candidate.docx"
    with ZipFile(file, "w", ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            XML_DECL + '<Types xmlns="http://schemas.openxmlformats.org/package/2006'
            '/content-types">' + "".join(types) + "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            XML_DECL + f'<Relationships xmlns="{REL}">'
            f'<Relationship Id="document" Type="{R}/officeDocument" '
            'Target="word/document.xml"/>'
            '<Relationship Id="core" Type="http://schemas.openxmlformats.'
            'org/package/2006/relationships/metadata/core-properties" Tar'
            'get="docProps/core.xml"/>'
            "</Relationships>",
        )
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles)
        z.writestr(
            "word/settings.xml",
            XML_DECL
            + f'<w:settings xmlns:w="{W}"><w:updateFields w:val="true"/></w:settings>',
        )
        z.writestr("word/header1.xml", header)
        z.writestr("word/footer1.xml", footer)
        z.writestr(
            "word/_rels/document.xml.rels",
            XML_DECL
            + f'<Relationships xmlns="{REL}">'
            + "".join(relationships)
            + "</Relationships>",
        )
        z.writestr("docProps/core.xml", core)
        for image in images:
            z.write(image, "word/media/" + image.name)
    return len(images)


def export_pdf(root, nodes, *, filename, title):
    for name, file in [
        ("TNR", "times.ttf"),
        ("TNR-Bold", "timesbd.ttf"),
        ("TNR-Italic", "timesi.ttf"),
    ]:
        pdfmetrics.registerFont(TTFont(name, str(Path("C:/Windows/Fonts") / file)))
    pdfmetrics.registerFontFamily(
        "TNR", normal="TNR", bold="TNR-Bold", italic="TNR-Italic"
    )
    base = dict(
        fontName="TNR",
        fontSize=11,
        leading=13.2,
        spaceAfter=7,
        alignment=TA_JUSTIFY,
        allowWidows=0,
        allowOrphans=0,
    )
    body = ParagraphStyle("Body", **base)
    styles = {
        "": body,
        "title": ParagraphStyle(
            "Title",
            parent=body,
            fontName="TNR-Bold",
            fontSize=24,
            leading=28,
            spaceBefore=30,
            spaceAfter=20,
            textColor=colors.HexColor("#173b55"),
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=body,
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=15,
        ),
        "center": ParagraphStyle(
            "Center", parent=body, alignment=TA_CENTER, spaceAfter=10
        ),
        "review": ParagraphStyle(
            "Review",
            parent=body,
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#924500"),
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=body,
            fontSize=9.5,
            leading=11.5,
            alignment=TA_LEFT,
            spaceBefore=5,
            spaceAfter=9,
        ),
        "note": ParagraphStyle(
            "Note", parent=body, fontSize=9, leading=11, alignment=TA_LEFT
        ),
        "reference": ParagraphStyle(
            "Reference", parent=body, fontSize=10, leading=12, alignment=TA_LEFT
        ),
        "equation": ParagraphStyle(
            "Equation", parent=body, fontSize=10.5, leading=13, alignment=TA_CENTER
        ),
        "h1": ParagraphStyle(
            "Heading1",
            parent=body,
            fontName="TNR-Bold",
            fontSize=16,
            leading=19,
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#173b55"),
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=body,
            fontName="TNR-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#173b55"),
        ),
    }
    cell = ParagraphStyle(
        "Cell", fontName="TNR", fontSize=9, leading=11, alignment=TA_LEFT
    )
    numeric_cell = ParagraphStyle("NumericCell", parent=cell, alignment=2)
    head = ParagraphStyle(
        "Head", parent=cell, fontName="TNR-Bold", textColor=colors.white, alignment=TA_CENTER
    )
    story = []
    index = 0
    while index < len(nodes):
        node = nodes[index]
        tag, cls = node.tag, node.attrib.get("class", "")
        if tag == "p" and cls == "pagebreak":
            story.append(PageBreak())
        elif tag == "p" and cls == "figure":
            file = image_path(node, root)
            with PILImage.open(file) as im:
                width, height = 480, 480 * im.height / im.width
            image = Image(str(file), width=width, height=height)
            caption = nodes[index + 1]
            assert caption.attrib.get("class") == "caption"
            story.append(
                KeepTogether(
                    [
                        Spacer(1, 6),
                        image,
                        Paragraph(esc(text_of(caption)), styles["caption"]),
                    ]
                )
            )
            index += 1
        elif tag == "table":
            rows = node.findall(".//tr")
            maximums = [
                max(len(text_of(row[j])) for row in rows) for j in range(len(rows[0]))
            ]
            weights = [max(8, min(36, n)) for n in maximums]
            col_widths = [WIDTH * w / sum(weights) for w in weights]
            values = []
            for i, row in enumerate(rows):
                cells = []
                for j, column in enumerate(row):
                    value = text_of(column)
                    numeric = bool(
                        re.fullmatch(
                            r"(?:[-+]?\d[\d,]*(?:\.\d+)?%?|N/A|Unavailable)",
                            value.strip(),
                        )
                    )
                    style = head if i == 0 else numeric_cell if numeric else cell
                    cells.append(Paragraph(esc(value), style))
                values.append(cells)
            count = len(values[0])
            table = LongTable(
                values, colWidths=col_widths, repeatRows=1, hAlign="LEFT"
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b55")),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#f4f7f9")],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b7c4ce")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.extend([table, Spacer(1, 8)])
        else:
            style = styles[tag if tag in ["h1", "h2"] else cls]
            if (
                cls == "caption"
                and index + 1 < len(nodes)
                and nodes[index + 1].tag == "table"
            ):
                style = ParagraphStyle(
                    "TableCaption",
                    parent=style,
                    keepWithNext=len(nodes[index + 1].findall(".//tr")) <= 40,
                )
            text = esc(text_of(node))
            link = node.find("a")
            if link is not None:
                target = esc(link.attrib["href"])
                text = f'<link href="{target}" color="#176b87">{text}</link>'
            story.append(Paragraph(text, style))
        index += 1
    pages = []

    def page_footer(canvas, doc):
        pages.append(doc.page)
        canvas.setFont("TNR", 8)
        canvas.setFillColor(colors.HexColor("#4c5962"))
        canvas.drawRightString(
            A4[0] - 54,
            A4[1] - 30,
            "HALFTREND ON NIFTY 50 | WORKING PAPER",
        )
        canvas.drawCentredString(
            A4[0] / 2, 29, f"Mohd Bilal | Working paper | Page {doc.page}"
        )

    doc = SimpleDocTemplate(
        str(root / filename),
        pagesize=A4,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
        title=title,
        author="Mohd Bilal",
    )
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return max(pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    root = parser.parse_args().directory.resolve()
    nodes = parse(root)
    supplementary = parse(root, "Supplementary_Results.html")
    image_count = export_docx(root, nodes)
    pages = export_pdf(
        root,
        nodes,
        filename="HalfTrend_NIFTY50_Publication_Candidate.pdf",
        title="HalfTrend on NIFTY 50: Transaction Costs, Execution Sensitivity, and Simulated Call Calendar Spreads",
    )
    supplementary_pages = export_pdf(
        root,
        supplementary,
        filename="Supplementary_Results.pdf",
        title="Supplementary Results and Research Audit",
    )
    with ZipFile(root / "HalfTrend_NIFTY50_Publication_Candidate.docx") as z:
        assert z.testzip() is None
        for name in z.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(z.read(name))
        document = ET.fromstring(z.read("word/document.xml"))
        tables = len(document.findall(f".//{{{W}}}tbl"))
        assert tables >= 10 and image_count == 11
        assert len([n for n in z.namelist() if n.startswith("word/media/")]) == 11
    proof = {
        "editable_docx_created": True,
        "ooxml_parts_well_formed": True,
        "embedded_figures": image_count,
        "tables": tables,
        "main_pdf_pages": pages,
        "supplementary_pdf_pages": supplementary_pages,
        "main_tables": tables,
        "supplementary_tables": len([n for n in supplementary if n.tag == "table"]),
        "pdf_renderer": "ReportLab; same manuscript source, independent pagination",
        "word_automation_available": False,
        "word_native_pagination_not_verified": True,
    }
    (root / "document_export_verification.json").write_text(json.dumps(proof, indent=2))
    print(
        f"Created {pages}-page working-paper PDF and "
        f"{supplementary_pages}-page supplement: {tables} main tables, "
        f"{image_count} figures."
    )


if __name__ == "__main__":
    main()
