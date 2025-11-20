    
from pydantic import Field, BaseModel
from .base_component import Base_component
from models.candidate_resume import Resume
from typing import List, Optional, Literal


class voice_bot_component(Base_component):
    "This component adds people to AI Matching after extracting it from ATS"
    component_type: Literal['voice_bot_component']
    ready_to_send_people: bool =  Field(
            ...,
            description="Indicates if we know people we are going to call with confidence"
        )

 
