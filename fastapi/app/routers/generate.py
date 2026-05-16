from fastapi import APIRouter, HTTPException
from ..models.request import GenerateRequest
from ..models.response import GenerateResponse
from ..services.prompt_builder import prompt_builder
from ..services.llm import llm_client
from ..services.job_store import job_store

router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate/{section}", response_model=GenerateResponse)
async def generate(section: str, req: GenerateRequest):
    # Получаем данные job
    job = job_store.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Формируем промпт в зависимости от раздела
    system_prompt = prompt_builder.get_system_prompt()
    
    metadata = job.get("metadata", {})
    code_summary = job.get("code_summary", {})
    topic = metadata.get("topic", "")
    description = metadata.get("description", "")
    
    if section == "introduction":
        user_prompt = prompt_builder.build_introduction(
            topic=topic,
            description=description,
            code_summary=str(code_summary)
        )
    
    elif section in ("chapter1", "chapter2", "chapter3"):
        chapter_names = {
            "chapter1": "Анализ предметной области",
            "chapter2": "Проектирование системы",
            "chapter3": "Реализация и тестирование",
        }
        num = int(section[-1])
        name = chapter_names.get(section, f"Глава {num}")
        
        prev_key = f"chapter{num-1}" if num > 1 else "introduction"
        prev_summary = str(job.get("sections", {}).get(prev_key, ""))[:500]
        
        user_prompt = prompt_builder.build_chapter(
            num=num,
            name=name,
            topic=topic,
            code_summary=str(code_summary),
            prev_summary=prev_summary
        )
    
    elif section == "conclusion":
        tasks = str(job.get("sections", {}).get("introduction", ""))[:500]
        chapters = str(job.get("sections", {}))[:1000]
        user_prompt = prompt_builder.build_conclusion(
            tasks=tasks,
            chapters_summary=chapters
        )
    
    elif section == "abstract":
        full = str(job.get("sections", {}))[:1500]
        user_prompt = prompt_builder.build_abstract(summary=full)
    
    elif section == "references":
        chapters = str(job.get("sections", {}))[:1000]
        user_prompt = prompt_builder.build_references(
            topic=topic,
            chapters_summary=chapters
        )

    elif section == "terms":
        user_prompt = prompt_builder.build_terms(
            topic=topic,
            code_summary=str(code_summary)
        )

    elif section == "abbreviations":
        user_prompt = prompt_builder.build_abbreviations(
            topic=topic,
            code_summary=str(code_summary)
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown section: {section}")
    
    # Вызываем LLM
    try:
        result = await llm_client.generate(system_prompt, user_prompt)
        
        # Сохраняем результат
        if "sections" not in job:
            job["sections"] = {}
        job["sections"][section] = result["content"]
        job_store.update(req.job_id, job)
        
        return GenerateResponse(
            job_id=req.job_id,
            section=section,
            content=result["content"],
            tokens_used=result["tokens_used"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")
