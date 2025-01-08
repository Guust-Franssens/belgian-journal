"""
contains helper functions to extract text from digital/searchable pdf and scanned pdf.
"""

import io
from pathlib import Path
from statistics import mode
from typing import Optional

import pymupdf
from azure.ai.formrecognizer import AnalyzeResult
from azure.ai.formrecognizer.aio import DocumentAnalysisClient
from azure.identity import DefaultAzureCredential

PAGE_0_REL_COORDS = (0.15966, 0.20485, 0.95000, 0.91950)
PAGE_N_REL_COORDS = (0.15966, 0.04899, 0.95000, 0.91950)

__all__ = [
    "extract_text_digital",
    "extract_text_scan",
    "extract_text",
]


def is_same_line(py0: Optional[float], py1: Optional[float], y0: float, y1: float, line_height: float) -> bool:
    """Checks if two lines previous line with py0 and py1 and current line y0 and y1 are on the same
    height and are not too big in height difference comparing to a standard line_height

    :return: bool
    """
    same_line = bool(
        py0
        and py1
        and abs(py0 - y0) / y0 <= 0.05
        and abs(py1 - y1) / y1 <= 0.05
        and (max(y1, py1) - min(y0, py0)) <= line_height * 1.25
    )
    return same_line


def add_text_line(text: str, line_text: str, same_line: bool) -> str:
    """adds the line_text to the general text. If it's the same line it uses \t otherwise \n"""
    if same_line:
        text += "\t" + line_text
    else:
        line_text = line_text if not text or text.endswith("\n") or line_text.startswith("\n") else "\n" + line_text
        text += line_text
    return text


async def ocr_pdf(pdf: pymupdf.Document, endpoint: str, credential: DefaultAzureCredential) -> AnalyzeResult:
    """OCRs the PDF using Azure Document Intelligence OCR.

    :param pdf: pymupdf.Document
    """
    pdf_bytes_io = io.BytesIO()
    pdf.save(pdf_bytes_io)
    pdf_bytes = pdf_bytes_io.getvalue()
    di_client = DocumentAnalysisClient(endpoint=endpoint, credential=credential)
    async with di_client:
        poller = await di_client.begin_analyze_document(model_id="prebuilt-read", document=pdf_bytes)
        result = await poller.result()
    return result


def extract_text_digital(pdf: pymupdf.Document) -> str:
    """extracts the text from within the dotted line from a digital/searchable pdf.

    :param pdf: pymupdf.Document
    :return: str
    """
    text = ""
    for page in pdf:
        if page.number == 0:
            rel_coords = PAGE_0_REL_COORDS
        else:
            rel_coords = PAGE_N_REL_COORDS

        _, _, width, height = page.rect
        clip = (width, height, width, height)
        clip = tuple(left * right for left, right in zip(clip, rel_coords))

        page_text = page.get_textbox(clip)
        page_text = page_text if not text or text.endswith("\n") or page_text.startswith("\n") else "\n" + page_text
        text += page_text
    return text


async def extract_text_scan(pdf: pymupdf.Document, endpoint: str, credential: DefaultAzureCredential) -> str:
    """1st submits the pdf to the Azure Document Intelligence OCR engine afterwhich
    the text within the dotted lines is extracted.

    :param pdf: pymupdf.Document
    :return: str
    """
    ocred = await ocr_pdf(pdf, endpoint, credential)
    text = ""
    for ocr_page, scan_page in zip(ocred.pages, pdf):
        _, _, width, height = scan_page.rect
        sf_x, sf_y = width / ocr_page.width, height / ocr_page.height  # scaling factor
        line_coords = [[point.y for point in line.polygon] for line in ocr_page.lines]
        line_height = mode([max(coords) - min(coords) for coords in line_coords]) * sf_y
        rel_coords = PAGE_0_REL_COORDS if scan_page.number == 0 else PAGE_N_REL_COORDS
        crop = (rel_coords[0] * width, rel_coords[1] * height, rel_coords[2] * width, rel_coords[3] * height)

        # sort lines from top left to bottom right.
        lines = sorted(ocr_page.lines, key=lambda l: (min(p.y for p in l.polygon), min(p.x for p in l.polygon)))  # noqa
        py0 = py1 = None
        for line in lines:
            x_coords = [point.x for point in line.polygon]
            y_coords = [point.y for point in line.polygon]
            x0, y0, x1, y1 = min(x_coords) * sf_x, min(y_coords) * sf_y, max(x_coords) * sf_x, max(y_coords) * sf_y
            same_line = is_same_line(py0, py1, y0, y1, line_height)
            within_crop = crop[0] <= x0 and x1 <= crop[2] and crop[1] <= y0 and y1 <= crop[3]
            if not within_crop:
                continue
            text = add_text_line(text, line.content, same_line)
            py0, py1 = y0, y1
    return text


async def extract_text(
    pdf: pymupdf.Document | str | Path,
    do_ocr: bool = True,
    endpoint: Optional[str] = None,
    credential: Optional[DefaultAzureCredential] = None,
) -> tuple[Optional[str], bool]:
    """extracts text from a pdf. If the pdf is digital, the text will be extracted straight from the
    pdf. If  the pdf is a scan, the pdf will be submitted to Azure Document Intelligence OCR
    after which the text is extracted.

    :param pdf: pymupdf.Document | str | Path
    :param do_ocr: boolean if set to False no OCR will be performed when the provided pdf is a scan.
    :return: tuple(text, is_digital)
    """
    if isinstance(pdf, (str, Path)):
        assert Path(pdf).exists(), pdf
        pdf = pymupdf.open(pdf)

    text = extract_text_digital(pdf)
    if text:
        is_digital = True
    elif not text and do_ocr:
        text = await extract_text_scan(pdf, endpoint, credential)
        is_digital = False
    else:
        text, is_digital = None, False

    return text, is_digital
