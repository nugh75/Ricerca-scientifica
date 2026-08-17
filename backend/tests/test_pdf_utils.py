from unittest.mock import Mock, patch

import pytest
import requests
from fpdf import FPDF
from pypdf import PdfWriter

from litreview import pdf_utils


def _make_text_pdf(tmp_path, text="Hello world. " * 50):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    path = tmp_path / "text.pdf"
    pdf.output(str(path))
    return path


def _make_blank_pdf(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "blank.pdf"
    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_download_pdf_writes_content(tmp_path):
    mock_resp = Mock()
    mock_resp.content = b"%PDF-1.4 fake content"
    mock_resp.raise_for_status.return_value = None
    dest = tmp_path / "out" / "file.pdf"
    with patch.object(pdf_utils.requests, "get", return_value=mock_resp):
        result = pdf_utils.download_pdf("https://example.org/a.pdf", dest)
    assert result == dest
    assert dest.read_bytes() == b"%PDF-1.4 fake content"


def test_download_pdf_raises_on_request_exception(tmp_path):
    dest = tmp_path / "file.pdf"
    with patch.object(
        pdf_utils.requests, "get", side_effect=requests.RequestException("timeout")
    ):
        with pytest.raises(pdf_utils.PdfDownloadError):
            pdf_utils.download_pdf("https://example.org/a.pdf", dest)


def test_extract_text_returns_pdf_content(tmp_path):
    path = _make_text_pdf(tmp_path)
    text = pdf_utils.extract_text(path)
    assert "Hello world" in text


def test_extract_text_respects_max_pages(tmp_path):
    path = _make_text_pdf(tmp_path)
    text = pdf_utils.extract_text(path, max_pages=0)
    assert text == ""


def test_has_extractable_text_true_for_normal_pdf(tmp_path):
    path = _make_text_pdf(tmp_path)
    text = pdf_utils.extract_text(path)
    assert pdf_utils.has_extractable_text(text) is True


def test_has_extractable_text_false_for_blank_pdf(tmp_path):
    path = _make_blank_pdf(tmp_path)
    text = pdf_utils.extract_text(path)
    assert pdf_utils.has_extractable_text(text) is False


def test_has_extractable_text_false_for_short_text():
    assert pdf_utils.has_extractable_text("too short") is False
