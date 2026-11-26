import uuid
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import CurrentUser, current_user
from app.catalog import MATERIALS, ROOM_DEFAULTS, STYLES, SURFACES
from app.db import audit, service
from app.responses import ok
from app.routes.projects import _project_or_404
from app.schemas import Brief, FinishesBody, MoodboardBody

catalog_router = APIRouter(prefix="/v1/catalog")
router = APIRouter(prefix="/v1/projects/{project_id}")


def _writable_project(user: CurrentUser, project_id: UUID) -> dict:
    # Every service-role write path goes through here: nothing is written for a suspended studio.
    project = _project_or_404(user, project_id)
    if project["studio"]["status"] != "active":
        raise HTTPException(403, "This studio is not active")
    return project


@catalog_router.get("")
def get_catalog(_: CurrentUser = Depends(current_user)):
    room_defaults = {room: [{"type": kind, "count": count} for kind, count in items] for room, items in ROOM_DEFAULTS.items()}
    return ok({"styles": STYLES, "materials": MATERIALS, "surfaces": list(SURFACES), "room_defaults": room_defaults})


@router.get("/brief")
def get_brief(project_id: UUID, user: CurrentUser = Depends(current_user)):
    _project_or_404(user, project_id)
    rows = user.db.table("project_briefs").select("brief, updated_at").eq("project_id", str(project_id)).execute().data
    return ok(rows[0] if rows else {"brief": Brief().model_dump(), "updated_at": None})


@router.put("/brief")
def put_brief(project_id: UUID, body: Brief, user: CurrentUser = Depends(current_user)):
    project = _writable_project(user, project_id)
    row = (
        service()
        .table("project_briefs")
        .upsert({"project_id": project["id"], "brief": body.model_dump(), "updated_by": user.id, "updated_at": "now()"})
        .execute()
        .data[0]
    )
    audit("brief.saved", user.id, studio_id=project["studio_id"], project_id=project["id"])
    return ok({"brief": row["brief"], "updated_at": row["updated_at"]})


# ---- finishes ----------------------------------------------------------------------------------------------------


@router.get("/finishes")
def get_finishes(project_id: UUID, user: CurrentUser = Depends(current_user)):
    _project_or_404(user, project_id)
    rows = user.db.table("finish_selections").select("room_id, surface, material_id").eq("project_id", str(project_id)).execute().data
    return ok(rows)


@router.put("/finishes")
def put_finishes(project_id: UUID, body: FinishesBody, user: CurrentUser = Depends(current_user)):
    project = _writable_project(user, project_id)
    plan = user.db.table("plan_versions").select("geometry").eq("project_id", project["id"]).order("version_no", desc=True).limit(1).execute().data
    rooms = {room["id"] for room in plan[0]["geometry"]["rooms"]} if plan else set()
    if any(item.room_id not in rooms for item in body.selections):
        raise HTTPException(422, "Invalid input (selections): a room is not part of the saved plan")
    # ponytail: delete-then-insert is not atomic; a crash in between leaves the project without finishes, and the client can save again.
    service().table("finish_selections").delete().eq("project_id", project["id"]).execute()
    if body.selections:
        rows = [{**item.model_dump(), "project_id": project["id"], "updated_by": user.id} for item in body.selections]
        service().table("finish_selections").insert(rows).execute()
    audit("finishes.saved", user.id, studio_id=project["studio_id"], project_id=project["id"], count=len(body.selections))
    return get_finishes(project_id, user)


# ---- inspiration assets ------------------------------------------------------------------------------------------

BUCKET = "project-assets"
MAX_ASSET_BYTES = 5 * 1024 * 1024
MAX_ASSETS_PER_PROJECT = 30
SIGNED_URL_SECONDS = 600
ASSET_COLUMNS = "id, kind, mime, size_bytes, caption, created_at"


def _sniff(data: bytes) -> tuple[str, str] | None:
    """Mime type and extension from the file's own bytes; the client's declared type is never trusted."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def _signed_urls(paths: list[str]) -> dict[str, str]:
    if not paths:
        return {}
    results = service().storage.from_(BUCKET).create_signed_urls(paths, SIGNED_URL_SECONDS)
    return {item["path"]: item["signedURL"] for item in results if item.get("signedURL")}


def _drain_storage_deletions() -> None:
    """Removes files whose asset rows are gone (deleted asset, or cascade from a project or user)."""
    queued = [row["path"] for row in service().table("storage_deletions").select("path").limit(100).execute().data]
    if queued:
        service().storage.from_(BUCKET).remove(queued)
        service().table("storage_deletions").delete().in_("path", queued).execute()


@router.get("/assets")
def list_assets(project_id: UUID, user: CurrentUser = Depends(current_user)):
    _project_or_404(user, project_id)
    rows = user.db.table("inspiration_assets").select(f"{ASSET_COLUMNS}, storage_path").eq("project_id", str(project_id)).order("created_at").execute().data
    urls = _signed_urls([row["storage_path"] for row in rows])
    return ok([{**{k: v for k, v in row.items() if k != "storage_path"}, "url": urls.get(row["storage_path"], "")} for row in rows])


@router.post("/assets", status_code=201)
def add_asset(
    project_id: UUID,
    file: UploadFile = File(...),
    kind: Literal["inspiration", "existing_item"] = Form(...),
    caption: str = Form("", max_length=200),
    user: CurrentUser = Depends(current_user),
):
    project = _writable_project(user, project_id)
    data = file.file.read(MAX_ASSET_BYTES + 1)
    if not data:
        raise HTTPException(422, "The file is empty")
    if len(data) > MAX_ASSET_BYTES:
        raise HTTPException(413, "Images can be at most 5 MB")
    sniffed = _sniff(data)
    if sniffed is None:
        raise HTTPException(415, "Only JPEG, PNG and WebP images are accepted")
    existing = user.db.table("inspiration_assets").select("id").eq("project_id", project["id"]).execute().data
    if len(existing) >= MAX_ASSETS_PER_PROJECT:
        raise HTTPException(409, "This project has reached its limit of images")
    mime, extension = sniffed
    path = f"{project['id']}/{uuid.uuid4()}.{extension}"
    service().storage.from_(BUCKET).upload(path, data, {"content-type": mime})
    try:
        row = (
            service()
            .table("inspiration_assets")
            .insert({"project_id": project["id"], "kind": kind, "storage_path": path, "mime": mime, "size_bytes": len(data), "caption": caption.strip(), "uploaded_by": user.id})
            .execute()
            .data[0]
        )
    except Exception as error:
        service().storage.from_(BUCKET).remove([path])
        if getattr(error, "code", None) == "P0001":  # the database quota trigger: parallel uploads raced past the check above
            raise HTTPException(409, "This project has reached its limit of images") from None
        raise
    audit("asset.added", user.id, studio_id=project["studio_id"], project_id=project["id"], asset_id=row["id"])
    return ok({key: row[key] for key in ASSET_COLUMNS.split(", ")})


@router.delete("/assets/{asset_id}")
def delete_asset(project_id: UUID, asset_id: UUID, user: CurrentUser = Depends(current_user)):
    project = _writable_project(user, project_id)
    found = user.db.table("inspiration_assets").select("id").eq("project_id", project["id"]).eq("id", str(asset_id)).execute().data
    if not found:
        raise HTTPException(404, "Image not found")
    service().table("inspiration_assets").delete().eq("id", str(asset_id)).execute()  # the trigger queues the file
    _drain_storage_deletions()
    audit("asset.removed", user.id, studio_id=project["studio_id"], project_id=project["id"], asset_id=str(asset_id))
    return ok({"id": str(asset_id)})


# ---- moodboard ---------------------------------------------------------------------------------------------------


@router.get("/moodboard")
def get_moodboard(project_id: UUID, user: CurrentUser = Depends(current_user)):
    _project_or_404(user, project_id)
    items = user.db.table("moodboard_items").select("kind, ref, note, position").eq("project_id", str(project_id)).order("position").execute().data
    assets = {
        row["id"]: row["storage_path"]
        for row in user.db.table("inspiration_assets").select("id, storage_path").eq("project_id", str(project_id)).execute().data
    }
    urls = _signed_urls([assets[i["ref"]] for i in items if i["kind"] == "asset" and i["ref"] in assets])
    result = []
    for item in items:
        entry = {"kind": item["kind"], "ref": item["ref"], "note": item["note"]}
        if item["kind"] == "asset":
            entry["url"] = urls.get(assets.get(item["ref"], ""), "")
        result.append(entry)
    return ok(result)


@router.put("/moodboard")
def put_moodboard(project_id: UUID, body: MoodboardBody, user: CurrentUser = Depends(current_user)):
    project = _writable_project(user, project_id)
    mine = {row["id"] for row in user.db.table("inspiration_assets").select("id").eq("project_id", project["id"]).execute().data}
    if any(item.kind == "asset" and item.ref not in mine for item in body.items):
        raise HTTPException(422, "Invalid input (items): an image is not part of this project")
    # ponytail: delete-then-insert is not atomic; the board can be saved again if it fails in between.
    service().table("moodboard_items").delete().eq("project_id", project["id"]).execute()
    if body.items:
        rows = [
            {"project_id": project["id"], "kind": item.kind, "ref": item.ref, "note": item.note, "position": index,
             "asset_id": item.ref if item.kind == "asset" else None}
            for index, item in enumerate(body.items)
        ]
        service().table("moodboard_items").insert(rows).execute()
    audit("moodboard.saved", user.id, studio_id=project["studio_id"], project_id=project["id"], count=len(body.items))
    return get_moodboard(project_id, user)
