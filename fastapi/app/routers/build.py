from fastapi import APIRouter, HTTPException
from ..models.request import BuildRequest
from ..models.response import BuildResponse
from ..services.job_store import job_store
from ..builders.docx_builder import build_report

router = APIRouter(prefix="/api", tags=["build"])


@router.post("/build-docx", response_model=BuildResponse)
async def build(req: BuildRequest):
    job = job_store.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        docx_bytes = build_report(job)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build error: {str(e)}")
    
    # Сохраняем файл
    filepath = f"/tmp/jobs/{req.job_id}.docx"
    with open(filepath, "wb") as f:
        f.write(docx_bytes)
    
    return BuildResponse(
        job_id=req.job_id,
        download_url=f"/api/download/{req.job_id}",
        filename=f"report_{job.get('metadata', {}).get('year', '2026')}.docx",
        size_bytes=len(docx_bytes)
    )
