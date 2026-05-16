from typing import Dict, Any, Optional
import json
import os


class JobStore:
    """Хранилище результатов генерации (в файлах)."""
    
    def __init__(self, storage_dir: str = "/tmp/jobs"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
    
    def _path(self, job_id: str) -> str:
        return os.path.join(self.storage_dir, f"{job_id}.json")
    
    def create(self, job_id: str, data: Dict[str, Any]):
        with open(self._path(job_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            with open(self._path(job_id), encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    def update(self, job_id: str, data: Dict[str, Any]):
        self.create(job_id, data)


job_store = JobStore()
