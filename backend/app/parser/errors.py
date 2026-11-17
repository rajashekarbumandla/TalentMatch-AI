"""Exceptions raised by the document parsers.

Each error carries a message that is safe to show to the recruiter in the UI.
"""


class DocumentParseError(Exception):
    """Base class for all document-parsing problems."""


class CorruptedFileError(DocumentParseError):
    """The file could not be opened (damaged, wrong format or password protected)."""


class EmptyDocumentError(DocumentParseError):
    """The file opened fine but contains no usable text."""


class OCRRequiredError(DocumentParseError):
    """The PDF looks scanned (images only) and OCR is not available."""
