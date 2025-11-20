    
from pydantic import Field
from .base_component import Base_component
from typing import Literal

class ats_component(Base_component):
    "This component adds people to AI Matching after extracting it from ATS"
    component_type: Literal['ats_component']
    num_of_peole_to_add: int = Field(
        ...,
        description="Number of people that must be added to AI Matching"
    )
