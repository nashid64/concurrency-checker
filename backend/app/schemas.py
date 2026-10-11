from typing import List, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    code: str = Field(..., description="Full source code of the file")
    language: str = "java"
    filename: Optional[str] = None
    mode: Optional[str] = Field(None, description="mock | llm | model | hybrid (optional override)")


class Bug(BaseModel):
    type: str  # race_condition | deadlock | concurrency_issue
    line: int = 1  # 1-based
    end_line: Optional[int] = None
    severity: str = "warning"  # error | warning | info
    message: str
    suggestion: Optional[str] = None


class AnalyzeResponse(BaseModel):
    bugs: List[Bug]
    verdict: str  # safe | race_condition | deadlock | concurrency_issue
    confidence: Optional[float] = None
    detector: str
    elapsed_ms: int
    note: Optional[str] = None
