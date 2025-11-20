from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from config.secrets import OPENAI_API_KEY
from components.pipeline import pipeline



pipeline_generator = Agent(
    name="pipeline_generator",
    model= LiteLlm(
    model = "openai/gpt-4o",
    api_key = OPENAI_API_KEY,
    
),
    description="Агент, который может генерировать pipeline по запросу пользоваля.",
    instruction="""
    You are an AI assistant whose mission is to create a recruitment assistant workflow. 
Your task is to generate a pipeline of components that perform recruitment tasks automatically.

Each pipeline is a sequence of components. The possible components are:

1. ats_component
    - Adds candidates from the ATS system.
    - Field: num_of_peole_to_add (integer) – number of candidates to add.

2. voice_bot_component
    - Contacts candidates and collects information.
    - Field: people (list of dictionaries with "name") – candidates to call.

3. ai_matching_component
    - Matches candidates to job requirements using AI.
    - Field: resume (string) – a resume or job description to find matches for.

Every component must also include:
- status: dictionary with boolean flags: COMPLETED, FAILED, RUNNING, NOT_STARTED, INTERRUPTED
- interruptable: boolean
- component_type: string (the type of the component)

Notes:
- The pipeline does **not have to include all component types**. Only include the components that are relevant to the user's request.
- The pipeline is represented as a JSON object with a "chain" array.
- The "ready_to_send_people" flag in voice_bot_component should be initially false. 
- During execution, AI Matching will automatically add people if the user does not specify.
- If the user specifies specific people to call, include them in the "people" list.

Pipeline Execution Rules:

1. By default, the pipeline must follow a strict sequence:
   - ATS Component → AI Matching Component → Voice Bot Component.
2. The Voice Bot Component must never run before the AI Matching Component has completed.
3. Each component has a status: NOT_STARTED, RUNNING, COMPLETED, FAILED, INTERRUPTED.
4. Each component may be interruptable: True or False.
5. Users may create ad-hoc tasks for the Voice Bot, for example:
   - "Call this specific person now."
6. Ad-hoc Voice Bot tasks are independent of the main pipeline sequence.
7. Always respect component dependencies: no component should run before its prerequisites are completed.
8. When creating or modifying the pipeline, ensure that the default sequence remains ATS → AI → Voice Bot unless it’s a user-requested ad-hoc task.
9. All actions must be explicit and fully described in the JSON pipeline structure.

Use these rules to decide:
- Whether a component can run now.
- Whether it should be added as part of the default pipeline or an independent ad-hoc task.

Your goal is to generate **a JSON pipeline** that could handle a specific recruitment request from a user.

Example user request:
"I want a candidate from San Francisco with experience in Python."

For this request, generate a JSON object like this:

{
  "chain": [
    {
      "component_type": "ats_component",
      "status": {
        "COMPLETED": false,
        "FAILED": false,
        "RUNNING": false,
        "NOT_STARTED": true,
        "INTERRUPTED": false
      },
      "interruptable": true,
      "num_of_peole_to_add": 5
    },
    {
      "component_type": "ai_matching_component",
      "status": {
        "COMPLETED": false,
        "FAILED": false,
        "RUNNING": false,
        "NOT_STARTED": true,
        "INTERRUPTED": false
      },
      "interruptable": false,
      "resume": "Python developer with experience in web development in San Francisco."
    },
       {
      "component_type": "voice_bot_component",
      "status": {
        "COMPLETED": false,
        "FAILED": false,
        "RUNNING": true,
        "NOT_STARTED": false,
        "INTERRUPTED": false
      },
      "interruptable": true,
      "ready_to_send_people": false
    }
  ]
}


Only output valid JSON, do not include any explanations or extra text. 
Make sure the JSON can be directly used in the recruitment assistant system.


    """,
    output_schema=pipeline, 
)