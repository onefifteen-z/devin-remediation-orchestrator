from pydantic import BaseModel, Field


class ScanResult(BaseModel):
    scanned: int = 0
    created: int = 0
    skipped: int = 0
    created_task_ids: list[int] = Field(default_factory=list)
    skipped_issues: list[str] = Field(default_factory=list)
