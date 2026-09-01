from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.storage import notes_storage as notes

router = APIRouter()


class NotePatch(BaseModel):
    title: str | None = None
    body: str | None = None


@router.get("/notes")
def list_notes() -> list[dict]:
    return notes.list_notes()


@router.post("/notes", status_code=201)
def create_note() -> dict:
    return notes.create_note()


@router.get("/notes/{note_id}")
def get_note(note_id: str) -> dict:
    row = notes.get_note(note_id)
    if not row:
        raise HTTPException(404, "노트를 찾을 수 없습니다.")
    return row


@router.patch("/notes/{note_id}")
def patch_note(note_id: str, body: NotePatch) -> dict:
    row = notes.update_note(note_id, body.title, body.body)
    if not row:
        raise HTTPException(404, "노트를 찾을 수 없습니다.")
    return row


@router.delete("/notes/{note_id}", status_code=204)
def remove_note(note_id: str) -> None:
    if not notes.delete_note(note_id):
        raise HTTPException(404, "노트를 찾을 수 없습니다.")
