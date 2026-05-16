from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/download/{job_id}")
async def download(job_id: str):
    filepath = f"/tmp/jobs/{job_id}.docx"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"report.docx"
    )
