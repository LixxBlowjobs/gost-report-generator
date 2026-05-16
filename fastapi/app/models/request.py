from pydantic import BaseModel
from typing import Optional, Dict, Any

class Metadata(BaseModel):
    topic: str
    student_name: str
    group: str
    supervisor: str
    university: str
    year: int

class AnalyzeRequest(BaseModel):
    job_id: Optional[str] = None
    metadata: Metadata
    source_code: str
    description: Optional[str] = None

class GenerateRequest(BaseModel):
    job_id: str
    previous_sections: Optional[Dict[str, Any]] = None

class BuildRequest(BaseModel):
    job_id: str
