from fastapi import APIRouter
from ..models.request import AnalyzeRequest
from ..models.response import AnalyzeResponse
from ..services.analyzer import analyze_code
from ..services.job_store import job_store
import uuid

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    job_id = str(uuid.uuid4())
    code_summary = analyze_code(req.source_code)
    
    # Сохраняем job
    job_store.create(job_id, {
        "metadata": req.metadata.model_dump(),
        "source_code": req.source_code,
        "description": req.description,
        "code_summary": code_summary,
        "sections": {},
    })
    
    return AnalyzeResponse(
        job_id=job_id,
        code_summary=code_summary
    )
