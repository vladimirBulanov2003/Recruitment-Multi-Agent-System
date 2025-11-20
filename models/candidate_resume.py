
from typing import List, Optional
from pydantic import BaseModel, Field

class Resume(BaseModel):
    class PositionDescription(BaseModel):
        company_name: str = Field(..., description="Name of the company where the candidate worked")
        position_title: str = Field(..., description="Name of the position the candidate worked in")
        start_date: str = Field(..., description="Start date for position")
        end_date: str = Field(..., description="End date for position, 'current' if not specified")

    class EducationInfo(BaseModel):
        institution_name: str = Field(..., description="Name of the educational institution")
        degree_name: str = Field(..., description="Name of the degree obtained")
        education_level: Optional[str] = Field(None, description="Level of education (e.g., Bachelor's, Master's, PhD)")
        start_year: Optional[int] = Field(None, description="Year of starting education")
        end_year: Optional[int] = Field(None, description="Year of completing education")

    id: int = Field(..., description="Unique ID of the resume in ATS")
    person_name: str = Field(..., description="Full name of the candidate")
    headline: Optional[str] = Field(None, description="Short LinkedIn-style title e.g. 'Senior Data Scientist at Yandex'")
    location: Optional[str] = Field(None, description="City and country of the candidate")
    summary: Optional[str] = Field(None, description="Short bio or 'About' section from LinkedIn")

    telephone_number: Optional[str] = Field(None, description="Formatted phone number of the candidate")
    contact_email: str = Field(..., description="Email of the candidate")

    skills: List[str] = Field(..., description="List of skills found on resume")
    languages: List[str] = Field(..., description="Languages spoken by the candidate (e.g., 'Russian (native)', 'English (C1)')")

    work_experience: List[PositionDescription] = Field(..., description="List of positions in which the candidate worked")
    education: List[EducationInfo] = Field(..., description="List of educational information")

    revision_date: Optional[str] = Field(None, description="Date of last profile update")