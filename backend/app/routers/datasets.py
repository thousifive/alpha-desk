from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.auth import AuthRequired
from app.deps import SettingsDep
from app.grading.dataset import TABLES

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.get("/meridian/{table}.parquet")
async def get_table(table: str, _: AuthRequired, settings: SettingsDep) -> FileResponse:
    # Allow-list the name. Never build a filesystem path from raw user input
    # (e.g. "../../backend/.env") without checking it first.
    if table not in TABLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown table")
    return FileResponse(
        settings.dataset_dir / f"{table}.parquet",
        media_type="application/vnd.apache.parquet",
        headers={"Cache-Control": "private, max-age=3600"},
    )
