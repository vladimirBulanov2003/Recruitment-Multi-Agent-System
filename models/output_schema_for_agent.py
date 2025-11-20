from typing import List
from pydantic import BaseModel, Field
from typing import Optional
from .candidate_resume import Resume

class output_schema(BaseModel):
    list_of_candidates: Optional[List[Resume]] = Field(None, description="List of resumes, that matches the desired one")