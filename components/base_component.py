
from pydantic import BaseModel, Field

from pydantic import BaseModel, Field

class component_status(BaseModel):
        COMPLETED: bool = Field(
            ...,
            description="Indicates that the component has successfully completed its execution and produced the expected results."
        )
        FAILED: bool = Field(
            ...,
            description="Indicates that the component encountered an error or exception during execution and was unable to complete its task."
        )
        RUNNING: bool = Field(
            ...,
            description="Indicates that the component is currently active and performing its assigned task."
        )
        NOT_STARTED: bool = Field(
            ...,
            description="Indicates that the component has been initialized but has not yet started its execution."
        )
        INTERRUPTED: bool = Field(
            ...,
            description="Indicates that the component's execution was forcefully stopped or interrupted before completion."
        )

class Base_component(BaseModel):
    
    status: component_status = Field(
        ...,
        description="Represents the current operational state of the component (e.g., RUNNING, COMPLETED, FAILED)."
    )
    interruptable: bool = Field(
        ...,
        description="Specifies whether the component can be safely interrupted during its execution without corrupting its state or data."
    )

