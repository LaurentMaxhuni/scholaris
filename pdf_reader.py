from tkinter import filedialog

import numpy as np
import pypdfium2 as pdfium


OCR_SCALE = 2.0
_ocr_engine = None
_ocr_engine_name = None


def choose_pdf():
	file_path = filedialog.askopenfilename(
		title="Select a PDF",
		filetypes=[("PDF files", "*.pdf")]
	)
	return file_path


def _clean_text(text):
	if not text:
		return ""
	return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _get_ocr_engine():
	global _ocr_engine, _ocr_engine_name
	if _ocr_engine is not None:
		return _ocr_engine, _ocr_engine_name

	try:
		from paddleocr import PaddleOCR

		_ocr_engine = PaddleOCR(use_angle_cls=True, lang="en")
		_ocr_engine_name = "PaddleOCR"
		return _ocr_engine, _ocr_engine_name
	except Exception:
		from rapidocr_onnxruntime import RapidOCR

		_ocr_engine = RapidOCR()
		_ocr_engine_name = "RapidOCR"
		return _ocr_engine, _ocr_engine_name


def _extract_page_with_ocr(document, page_index):
	page = document[page_index]
	try:
		bitmap = page.render(scale=OCR_SCALE)
		image = np.array(bitmap.to_pil())
	finally:
		page.close()

	engine, engine_name = _get_ocr_engine()
	lines = []

	if engine_name == "PaddleOCR":
		result = engine.ocr(image, cls=True)
		if result:
			for block in result:
				for line in block:
					if len(line) > 1 and line[1]:
						lines.append(str(line[1][0]).strip())
	else:
		result, _elapsed = engine(image)
		if result:
			for line in result:
				if len(line) > 1:
					lines.append(str(line[1]).strip())

	return _clean_text("\n".join(lines))


def extract_text_from_pdf(file_path):
	try:
		document = pdfium.PdfDocument(file_path)
		try:
			pages = []
			for index in range(len(document)):
				page_text = _extract_page_with_ocr(document, index)
				if page_text:
					pages.append(f"--- Page {index + 1} ---\n{page_text}")
		finally:
			document.close()

		if pages:
			return "\n\n".join(pages)

		return "No text was found in this PDF with OCR."
	except FileNotFoundError:
		return "File not found."
	except Exception as error:
		return f"Could not read PDF with OCR: {error}"
