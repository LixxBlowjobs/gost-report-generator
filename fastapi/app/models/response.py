from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class AnalyzeResponse(BaseModel):
    job_id: str
    code_summary: Dict[str, Any]

class GenerateResponse(BaseModel):
    job_id: str
    section: str
    content: Dict[str, Any]
    tokens_used: int

class BuildResponse(BaseModel):
    job_id: str
    download_url: str
    filename: str
    size_bytes: int
