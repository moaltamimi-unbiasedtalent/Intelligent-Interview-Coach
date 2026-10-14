"""An HTTP error that carries a stable, bounded machine code in the standard envelope (W12.4C)."""

from __future__ import annotations

from fastapi import HTTPException


class CodedHTTPException(HTTPException):
    """``error_code`` becomes ``error.code`` in the response envelope. Messages stay fixed, user-safe copy."""

    def __init__(self, status_code: int, error_code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
