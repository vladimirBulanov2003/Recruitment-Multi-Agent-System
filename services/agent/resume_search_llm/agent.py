from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.models.lite_llm import LiteLlm
from config.secrets import OPENAI_API_KEY
from models.input_schema import input_schema
from models.output_schema_for_agent import output_schema 


model = LiteLlm(
    model = "openai/gpt-4o-mini",
    api_key = OPENAI_API_KEY
)

root_agent = Agent(
    name="resume_search_llm",
    model=model,
    description="Agent that finds the most suitable resumes for a given job description or candidate requirements.",
    instruction="""
    You are an AI agent that helps recruiters search for appropriate resumes.

    Your job:
    - Analyze the provided job description and user preferences.
    - Select the most relevant resumes from the available pool of candidates.
    - Focus on matching required skills, years of experience, and role responsibilities.
    - Return a structured list of candidates in JSON format with fields.

    Be precise and concise. Do not invent irrelevant data. Always justify why the resume fits.

    You should return just the list of the cadndiates in json format that matches the text in the field called "desired resume" in the input schema! Don't change the initial jsons just return the list of json that matches my requrements!
 
    If candidates that match our desired description don't exist just 
    """,

    input_schema= input_schema,
    output_schema= output_schema,
    disallow_transfer_to_parent=True, disallow_transfer_to_peers=True
)


