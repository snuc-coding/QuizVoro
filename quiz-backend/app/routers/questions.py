"""
routers/questions.py — Question management endpoints.

Endpoints:
  POST   /api/v1/rounds/{roundId}/questions        ← Required (original endpoint)
  GET    /api/v1/rounds/{roundId}/questions        ← Additional
  GET    /api/v1/questions/{questionId}            ← Additional
  PATCH  /api/v1/questions/{questionId}            ← Additional
  DELETE /api/v1/questions/{questionId}            ← Additional
  POST   /api/v1/questions/{questionId}/media      ← Additional (multimedia upload)
  GET    /api/v1/questions/{questionId}/media      ← Additional (serve media file)
"""

import mimetypes
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_admin
from app.models import Admin
from app.schemas import AdminQuestionOut, MediaUploadOut, QuestionIn, QuestionUpdate
from app.services import question_service

settings = get_settings()

# Allowed MIME types for multimedia uploads.
ALLOWED_MIME_TYPES = {
    "image/jpeg": ("image", ".jpg"),
    "image/png": ("image", ".png"),
    "image/gif": ("image", ".gif"),
    "image/webp": ("image", ".webp"),
    "audio/mpeg": ("audio", ".mp3"),
    "audio/wav": ("audio", ".wav"),
    "audio/ogg": ("audio", ".ogg"),
    "video/mp4": ("video", ".mp4"),
    "video/webm": ("video", ".webm"),
}

# Two routers for two path prefixes.
round_router = APIRouter(
    prefix="/rounds",
    tags=["Questions"],
)

question_router = APIRouter(
    prefix="/questions",
    tags=["Questions"],
)

media_router = APIRouter(
    prefix="/questions",
    tags=["Media"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Required endpoint
# ─────────────────────────────────────────────────────────────────────────────

@round_router.post(
    "/{roundId}/questions",
    response_model=AdminQuestionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add Question to Round",
    description=(
        "Add a new MCQ question to a round. "
        "Requires exactly 2–6 options with exactly one marked as correct. "
        "Both the question and its options are saved atomically."
    ),
    responses={
        201: {"description": "Question created."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Round not found."},
        409: {"description": "Duplicate question_order within the round."},
        422: {"description": "Validation error (wrong option count, no correct answer, etc)."},
    },
)
def create_question(
    roundId: int,
    question_in: QuestionIn,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminQuestionOut:
    """POST /api/v1/rounds/{roundId}/questions"""
    return question_service.create_question(db, roundId, question_in, admin)


@round_router.get(
    "/{roundId}/questions",
    response_model=list[AdminQuestionOut],
    summary="List Questions in Round",
    description="Return all questions in a round, ordered by question_order.",
)
def list_questions(
    roundId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminQuestionOut]:
    """GET /api/v1/rounds/{roundId}/questions"""
    return question_service.list_questions_for_round(db, roundId, admin)


# ─────────────────────────────────────────────────────────────────────────────
# Additional endpoints
# ─────────────────────────────────────────────────────────────────────────────

@question_router.get(
    "/{questionId}",
    response_model=AdminQuestionOut,
    summary="Get Question",
    description=(
        "Return a single question with all its options and the correct-answer flag. "
        "Admin-only. Never expose this endpoint to participants."
    ),
    responses={
        200: {"description": "Question returned."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Question not found."},
    },
)
def get_question(
    questionId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminQuestionOut:
    """GET /api/v1/questions/{questionId}"""
    return question_service.get_question_and_verify_ownership(db, questionId, admin)


@question_router.patch(
    "/{questionId}",
    response_model=AdminQuestionOut,
    summary="Update Question",
    description=(
        "Partially update a question's metadata (text, time limit, points, order). "
        "To update options, delete and recreate the question."
    ),
    responses={
        200: {"description": "Question updated."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Question not found."},
        409: {"description": "Duplicate question_order."},
    },
)
def update_question(
    questionId: int,
    question_update: QuestionUpdate,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminQuestionOut:
    """PATCH /api/v1/questions/{questionId}"""
    question = question_service.get_question_and_verify_ownership(db, questionId, admin)
    return question_service.update_question(db, question, question_update, admin)


@question_router.delete(
    "/{questionId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Question",
    description="Delete a question and all its options.",
    responses={
        204: {"description": "Question deleted."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Question not found."},
    },
)
def delete_question(
    questionId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """DELETE /api/v1/questions/{questionId}"""
    question = question_service.get_question_and_verify_ownership(db, questionId, admin)
    question_service.delete_question(db, question)


# ─────────────────────────────────────────────────────────────────────────────
# Media upload and serving
# ─────────────────────────────────────────────────────────────────────────────

@media_router.post(
    "/{questionId}/media",
    response_model=MediaUploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Question Media",
    description=(
        "Upload an image, audio, or video file for a question. "
        "Supported formats: JPEG, PNG, GIF, WebP, MP3, WAV, OGG, MP4, WebM. "
        "Maximum file size is configurable via MAX_UPLOAD_SIZE_MB in .env (default: 10 MB). "
        "The file is stored on the local filesystem and a URL reference is saved in the database."
    ),
    responses={
        201: {"description": "Media uploaded and linked to question."},
        400: {"description": "Unsupported file type or file too large."},
        403: {"description": "Not the quiz owner."},
        404: {"description": "Question not found."},
    },
)
async def upload_media(
    questionId: int,
    file: UploadFile = File(..., description="The media file to upload"),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MediaUploadOut:
    """POST /api/v1/questions/{questionId}/media"""
    question = question_service.get_question_and_verify_ownership(db, questionId, admin)

    # ── Validate MIME type ────────────────────────────────────────────────────
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{content_type}'. "
                f"Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}."
            ),
        )

    media_category, extension = ALLOWED_MIME_TYPES[content_type]

    # ── Read and validate size ────────────────────────────────────────────────
    content = await file.read()
    max_bytes = settings.max_upload_size_bytes
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File is too large ({len(content) / 1024 / 1024:.1f} MB). "
                f"Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )

    # ── Generate a safe random filename ──────────────────────────────────────
    # Using uuid4 prevents path traversal and filename collisions.
    safe_filename = f"{uuid.uuid4().hex}{extension}"
    media_dir = Path(settings.MEDIA_DIR)
    media_dir.mkdir(parents=True, exist_ok=True)
    file_path = media_dir / safe_filename

    # ── Write to disk ─────────────────────────────────────────────────────────
    file_path.write_bytes(content)

    # ── Save reference in DB ──────────────────────────────────────────────────
    # Store a relative URL, not the absolute filesystem path.
    media_url = f"/media/{safe_filename}"
    updated_question = question_service.attach_media_to_question(
        db, question, media_url, media_category
    )

    return MediaUploadOut(
        question_id=updated_question.id,
        media_url=media_url,
        media_type=media_category,
    )


@media_router.get(
    "/{questionId}/media",
    summary="Serve Question Media",
    description="Download the media file attached to a question.",
    responses={
        200: {"description": "Media file returned."},
        404: {"description": "No media attached to this question, or question not found."},
    },
)
def serve_media(
    questionId: int,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    """GET /api/v1/questions/{questionId}/media"""
    question = question_service.get_question_and_verify_ownership(db, questionId, admin)

    if not question.media_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No media file is attached to this question.",
        )

    # Strip the leading slash from "/media/filename.jpg" → "media/filename.jpg"
    relative_path = question.media_url.lstrip("/")
    file_path = Path(relative_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found on server.",
        )

    mime_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=str(file_path), media_type=mime_type or "application/octet-stream")
