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

def _validate_magic_bytes(header: bytes, extension: str) -> bool:
    """Validate file content against magic byte signatures for security."""
    if len(header) < 4:
        return False
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in (".jpg", ".jpeg"):
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".gif":
        return header.startswith(b"GIF87a") or header.startswith(b"GIF89a")
    if extension == ".webp":
        return header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP"
    if extension == ".mp3":
        return header.startswith(b"ID3") or header.startswith(b"\xff\xfb") or header.startswith(b"\xff\xf3") or header.startswith(b"\xff\xf2")
    if extension == ".wav":
        return header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE"
    if extension == ".ogg":
        return header.startswith(b"OggS")
    if extension == ".mp4":
        return len(header) >= 8 and (header[4:8] == b"ftyp" or header.startswith(b"\x00\x00\x00"))
    if extension == ".webm":
        return header.startswith(b"\x1a\x45\xdf\xa3")
    return True


@media_router.post(
    "/{questionId}/media",
    response_model=MediaUploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Question Media",
    description=(
        "Upload an image, audio, or video file for a question. "
        "Streamed in chunks with strict size, MIME-type, and magic-byte checks."
    ),
    responses={
        201: {"description": "Media uploaded and linked to question."},
        400: {"description": "Unsupported file type, corrupted file, or file too large."},
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

    # ── Prepare safe storage path ─────────────────────────────────────────────
    safe_filename = f"{uuid.uuid4().hex}{extension}"
    media_dir = Path(settings.MEDIA_DIR).resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    file_path = media_dir / safe_filename

    # ── Stream upload in chunks with size and magic-byte check ─────────────────
    max_upload_mb = (
        settings.MAX_VIDEO_UPLOAD_SIZE_MB
        if media_category == "video"
        else settings.MAX_UPLOAD_SIZE_MB
    )
    max_bytes = max_upload_mb * 1024 * 1024
    accumulated_bytes = 0
    first_chunk = True

    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(64 * 1024):
                accumulated_bytes += len(chunk)
                if accumulated_bytes > max_bytes:
                    buffer.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"File is too large. Maximum allowed size is "
                            f"{max_upload_mb} MB."
                        ),
                    )

                if first_chunk:
                    if not _validate_magic_bytes(chunk[:32], extension):
                        buffer.close()
                        file_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="File content does not match the declared MIME type signature.",
                        )
                    first_chunk = False

                buffer.write(chunk)

        if accumulated_bytes == 0:
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # ── Save reference in DB ──────────────────────────────────────────────
        media_url = f"/media/{safe_filename}"
        updated_question = question_service.attach_media_to_question(
            db, question, media_url, media_category
        )
    except HTTPException:
        raise
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process media upload: {str(e)}",
        )

    return MediaUploadOut(
        question_id=updated_question.id,
        media_url=media_url,
        media_type=media_category,
    )


@media_router.get(
    "/{questionId}/media",
    summary="Serve Question Media",
    description=(
        "Stream/download the media file attached to a question. "
        "Publicly accessible to allow participants and the stage display to load media."
    ),
    responses={
        200: {"description": "Media file returned."},
        404: {"description": "No media attached to this question, or question not found."},
    },
)
def serve_media(
    questionId: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    """GET /api/v1/questions/{questionId}/media"""
    question = question_service.get_question_by_id(db, questionId)

    if not question.media_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No media file is attached to this question.",
        )

    safe_filename = Path(question.media_url).name
    media_dir = Path(settings.MEDIA_DIR).resolve()
    file_path = media_dir / safe_filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found on server.",
        )

    mime_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=str(file_path), media_type=mime_type or "application/octet-stream")
