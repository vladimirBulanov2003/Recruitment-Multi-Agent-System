    
from pydantic import Field
from .base_component import Base_component
from typing import Literal

class ai_matching_component(Base_component):
    "This component adds people to AI Matching after extracting it from ATS"
    component_type: Literal['ai_matching_component']
    resume: str =  Field(
        ...,
        description="It's a resume based on which we will be searching for our candidates"
    )
    number_of_candidates: int = Field(
        ...,
        description="It's a number of people that we are supposed to find"
    )
 
