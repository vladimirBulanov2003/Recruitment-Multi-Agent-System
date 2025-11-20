
from typing import List
from pydantic import BaseModel, Field
from .candidate_resume import Resume

class input_schema(BaseModel):
    desired_resume: str = Field(..., description="Text description of a desired candidate according to our recrutement")
    list_of_candidates: List[Resume] = Field(..., description="List of resumes")
