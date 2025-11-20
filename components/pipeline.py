    
from pydantic import Field, BaseModel
from .ats_component import ats_component
from .ai_matching_component import ai_matching_component
from .voice_bot_component import voice_bot_component
from typing import List, Union

class pipeline(BaseModel):
   chain: List[Union[ats_component, voice_bot_component, ai_matching_component]] = Field(..., 
                description= "This thing for creating pipeline")

