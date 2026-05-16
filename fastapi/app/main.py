from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="GOST Report Generator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import analyze, generate, build, download

app.include_router(analyze.router)
app.include_router(generate.router)
app.include_router(build.router)
app.include_router(download.router)

@app.get("/api/health")
async def health():
    return {"status": "ok", "gost_rules_loaded": True, "openrouter": "ok"}
