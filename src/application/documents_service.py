"""Document lifecycle orchestration (Capstone P4/E2).

Upload → validate → private store → parse (native) or OCR → deterministic extraction →
persist claims for review; plus replace/version, review actions, owner-scoped download,
and delete (purges files + re-derives story evidence). Processing is synchronous and
bounded (declared file types + size/page limits), so no background-job infrastructure is
introduced; failures are captured as a safe FAILED state and never crash the request.

Documents are untrusted DATA: their text is never placed in an LLM prompt here.
"""

from __future__ import annotations

from src.application.errors import ValidationError
from src.documents.extraction import extract_claims
from src.documents.ocr import OcrError, ocr_parse
from src.documents.parsing import ParseError, needs_ocr, parse_document
from src.documents.repository import DocumentRepository, StoryRepository
from src.documents.storage import DocumentStore, new_storage_key
from src.documents.validation import DocumentValidationError, validate_upload
from src.persistence import (
    CLAIM_ACCEPTED,
    CLAIM_EDITED,
    CLAIM_PENDING,
    CLAIM_REJECTED,
    DOC_CATEGORIES,
    DOC_CATEGORY_OTHER,
    DOC_STATUS_FAILED,
    DOC_STATUS_READY,
    DOC_STATUS_REVIEW_REQUIRED,
    EXTRACTION_ORIGIN_NATIVE,
    EXTRACTION_ORIGIN_OCR,
    SUPPORTED_LOCALES,
)

__all__ = ["DocumentsApplicationService"]

_REVIEW_ACTIONS = {
    "accept": CLAIM_ACCEPTED,
    "edit": CLAIM_EDITED,
    "reject": CLAIM_REJECTED,
    "reset": CLAIM_PENDING,
}


class DocumentsApplicationService:
    def __init__(self, *, repo: DocumentRepository, stories: StoryRepository, store: DocumentStore, ocr) -> None:
        self._repo = repo
        self._stories = stories
        self._store = store
        self._ocr = ocr

    # -- upload / process -----------------------------------------------------

    def upload(self, *, user_id: int, filename: str, data: bytes, category: str, language_hint: str | None = None) -> dict:
        cat = category if category in DOC_CATEGORIES else DOC_CATEGORY_OTHER
        lang = language_hint if language_hint in SUPPORTED_LOCALES else None
        try:
            validated = validate_upload(filename, data)
        except DocumentValidationError as exc:
            raise ValidationError(str(exc)) from exc

        document_id = self._repo.create_document(user_id=user_id, category=cat, title=validated.safe_filename)
        storage_key = new_storage_key()
        self._store.save(storage_key, data)
        version_id = self._repo.add_version(
            user_id=user_id, document_id=document_id, version=1,
            original_filename=validated.safe_filename, storage_key=storage_key,
            mime_type=validated.mime_type, size_bytes=validated.size_bytes, language_hint=lang,
        )
        self._process(user_id=user_id, document_id=document_id, version_id=version_id,
                      data=data, extension=validated.extension, lang=lang or "en")
        return self._repo.get_document(user_id=user_id, document_id=document_id)

    def replace(self, *, user_id: int, document_id: int, filename: str, data: bytes, language_hint: str | None = None) -> dict | None:
        existing = self._repo.get_document(user_id=user_id, document_id=document_id)
        if existing is None:
            return None
        lang = language_hint if language_hint in SUPPORTED_LOCALES else None
        try:
            validated = validate_upload(filename, data)
        except DocumentValidationError as exc:
            raise ValidationError(str(exc)) from exc
        new_version = existing["current_version"] + 1
        storage_key = new_storage_key()
        self._store.save(storage_key, data)
        version_id = self._repo.add_version(
            user_id=user_id, document_id=document_id, version=new_version,
            original_filename=validated.safe_filename, storage_key=storage_key,
            mime_type=validated.mime_type, size_bytes=validated.size_bytes, language_hint=lang,
        )
        if version_id is None:
            return None
        # New version's new claims reference the new version; older versions/claims are
        # RETAINED for provenance (historical outputs keep their supporting version).
        self._process(user_id=user_id, document_id=document_id, version_id=version_id,
                      data=data, extension=validated.extension, lang=lang or "en")
        return self._repo.get_document(user_id=user_id, document_id=document_id)

    def _process(self, *, user_id: int, document_id: int, version_id: int, data: bytes, extension: str, lang: str) -> None:
        try:
            native = parse_document(data, extension)
            if needs_ocr(extension, native):
                try:
                    parsed = ocr_parse(self._ocr, data, extension, lang=lang)
                    origin = EXTRACTION_ORIGIN_OCR
                except OcrError as exc:
                    self._fail(user_id, document_id, version_id, str(exc))
                    return
            else:
                parsed = native
                origin = EXTRACTION_ORIGIN_NATIVE

            if not parsed.has_text:
                self._fail(user_id, document_id, version_id,
                           "No readable text was found in this document.")
                return

            claims = extract_claims(parsed, category="cv")
            self._repo.add_claims(user_id=user_id, document_id=document_id, version_id=version_id, claims=claims)
            self._repo.set_version_result(
                version_id=version_id, status=DOC_STATUS_READY, extraction_origin=origin,
                page_count=parsed.page_count,
            )
            status = DOC_STATUS_REVIEW_REQUIRED if claims else DOC_STATUS_READY
            self._repo.set_document_status(user_id=user_id, document_id=document_id, status=status)
        except ParseError as exc:
            self._fail(user_id, document_id, version_id, str(exc))
        except Exception:  # noqa: BLE001 - never leak internals; safe generic failure
            self._fail(user_id, document_id, version_id, "This document could not be processed.")

    def _fail(self, user_id: int, document_id: int, version_id: int, reason: str) -> None:
        self._repo.set_version_result(version_id=version_id, status=DOC_STATUS_FAILED, failure_reason=reason[:255])
        self._repo.set_document_status(user_id=user_id, document_id=document_id, status=DOC_STATUS_FAILED)

    # -- read / review / download / delete ------------------------------------

    def get(self, *, user_id: int, document_id: int) -> dict | None:
        return self._repo.get_document(user_id=user_id, document_id=document_id)

    def list(self, user_id: int) -> list[dict]:
        return self._repo.list_documents(user_id)

    def review_claim(self, *, user_id: int, claim_id: int, action: str, edited_text: str | None = None) -> dict | None:
        state = _REVIEW_ACTIONS.get(action)
        if state is None:
            raise ValidationError("Unknown review action.")
        if state == CLAIM_EDITED and not (edited_text or "").strip():
            raise ValidationError("Edited text is required.")
        return self._repo.update_claim(
            user_id=user_id, claim_id=claim_id, review_state=state,
            edited_text=(edited_text.strip() if edited_text else None),
        )

    def download(self, *, user_id: int, document_id: int, version: int | None = None) -> tuple[bytes, str, str] | None:
        info = self._repo.get_download(user_id=user_id, document_id=document_id, version=version)
        if info is None:
            return None
        try:
            data = self._store.read(info["storage_key"])
        except (FileNotFoundError, ValueError):
            return None
        return data, info["mime_type"], info["filename"]

    def delete(self, *, user_id: int, document_id: int) -> bool:
        keys = self._repo.delete_document(user_id=user_id, document_id=document_id)
        if keys is None:
            return False
        for key in keys:
            self._store.delete(key)
        # A deleted source must not leave a story silently "verified".
        self._stories.rederive_all_for_user(user_id)
        return True
