

from google.adk.tools.tool_context import ToolContext
from typing import Optional, List
import json
from google.adk.tools.tool_context import ToolContext
import httpx
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any


client = httpx.AsyncClient(base_url= "http://127.0.0.1:7999", 
                                              timeout=None)

async def toll_for_calling_task_manager(tool_context: ToolContext, params: dict, json_data: Optional[List[int]] = None):
        """
          Sends an asynchronous request to the Task Manager to create or execute a recruitment task.

          This function acts as a communication layer between the orchestrator agent and the backend Task Manager.
          It takes in component parameters (`params`) and, if necessary, augments them with candidate data stored
          in the `ToolContext` (for Voice_bot components). It then sends a POST request to the `/create_tasks` endpoint.

          Behavior:
              - For "Voice_bot" components:
                  * Automatically attaches candidate data from `tool_context.state["сandidates"]` based on `index_of_pipeline`.
              - For other components:
                  * Simply forwards the provided parameters and `json_data` to the Task Manager.

          Args:
              tool_context (ToolContext): The current execution context containing shared state and candidate buffers.
              params (dict): Parameters describing which task/component should be executed.
                  Must include at least:
                      - "type_of_component" (str): Type of recruitment component (e.g. "ATS", "AI_Matching", "Voice_bot")
                      - "index_of_pipeline" (str): Identifier of the current pipeline.
                      - "index_of_component": (int) Index of the component in the array of the pipeline 
              json_data (Optional[List[int]]): Optional JSON payload with extra task data.
                  For Voice_bot, this is automatically filled with candidate information.

          Returns:
              dict: A dictionary containing:
                  - "Status": The result of the request ("OK" or "Error").
                  - "params": The parameters used in the request.
                  - "json_data": The JSON payload sent.
                  - "response_from_server": The response returned from the Task Manager (if successful).

          Raises:
              Exception: If the POST request fails or Task Manager is unreachable.
        """
        
        if params["type_of_component"] == "Voice_bot":
              json_data = {}
              index_of_pipeline = params["index_of_pipeline"]
              json_data["candidates"] = {"candidates" : tool_context.state["сandidates"][index_of_pipeline]}
        try:      
           responce = await client.post("/create_tasks", params=params, json={"data": json_data})
           return {"Status": f"OK", "params: " : params, "json_data: ": json_data, "responce_from_server": responce.json()}

        except Exception as e:
         return {"Status": f"Error : {e}", "params: " : params, "json_data: ": json_data}


async def tool_for_killing_voice_bot_task(params: dict):
        """This tool is needed for cancelling our call. You should put here as the parameters :
              params (dict): Parameters describing the index of the pipline where the user is willing to interupt our calling operation. And the index of the voice bot component in the array.
                      Must include:
                          - "index_of_pipeline" (str): Identifier of the current pipeline.
                          - "index_of_component": (int) Index of the component in the array of the pipeline 
        """ 
        try:      
           responce = await client.post("/kill_voice_bot_task", params=params)
           return {"Status": f"OK", "params: " : params, "responce_from_server": responce.json()}

        except Exception as e:
         return {"Status": f"Error : {e}", "params: " : params}



def before_tool_callback(
    tool: BaseTool, args: Dict[Any, Any], tool_context: ToolContext
) -> Optional[Dict]:
    agent_name = tool_context.agent_name
    tool_name = tool.name
    print(f"[Callback] Before tool call for tool '{tool_name}' in agent '{agent_name}'")
    print(f"[Callback] Original args: {args}")

    pipelines = tool_context.state["pipelines"]
    params = args.get("params", "")

    print(f"параметры которые вставил агент - {params}")

    
    if tool_name == 'toll_for_calling_task_manager' and params["type_of_component"] == "Voice_bot" and tool_context.state["сandidates"][params["index_of_pipeline"]] == None:
        return {"Status: ": "Error, it's imposible to call because there are not candidates to call for that pipeline "}
  
    return None
 


def put_pipeline_in_state(tool_context: ToolContext, pipeline: str):
        "Function for adding pipeline in the state. You must put the pipeleine as a string!!!!"
        pipelines = tool_context.state["pipelines"]
        candidates_truncated = tool_context.state["candidates_truncated"]
        candidates_screened  = tool_context.state["candidates_screened"]
        сandidates  = tool_context.state["сandidates"]
        candidates_approved_offer  = tool_context.state["candidates_approved_offer"]


        if pipelines:
            max_index = max(map(int, pipelines.keys()))
            index_generated = str(max_index + 1)
        else:
            index_generated = "0"

        pipelines[index_generated] = json.loads(pipeline)
        candidates_truncated[index_generated] = []
        candidates_screened[index_generated] = []
        сandidates[index_generated] = []
        candidates_approved_offer[index_generated] = []

        tool_context.state["pipelines"] = pipelines
        tool_context.state["candidates_truncated"] = candidates_truncated
        tool_context.state["candidates_screened"] = candidates_screened
        tool_context.state["сandidates"] = сandidates
        tool_context.state["candidates_approved_offer"] = candidates_approved_offer


        try:
          with httpx.Client(timeout=1.0) as client:
            client.post(
                "http://localhost:8765/broadcast",
                json={
                    "index": index_generated,
                    "pipeline": pipelines[index_generated]
                }
            )
        except Exception as e:
         print(f"WebSocket broadcast failed: {e}")

        return {"Status": f"OK"}


def change_list_of_people(tool_context: ToolContext, indx_of_pipeline: str, index_of_component: int, indxs: Optional[List[int]] = None,
    names: Optional[List[str]] = None):
      """Function for changing list of people which are going to be called by our voice bot. 
      This fucntion must be called when user is not willing to call each candidate from list and wants to remove someone before calling. 
      You must put here indx_of_pipeline:str, indxs : list[int],names: list[str]. 
      Here indxs - is a list of indexes of people we are going to remove from state, names is the list of their names respectively
      indx_of_pipeline - list of pipeleine you are working with
      index_of_component - is a index of component in our pipeline array so here you have to put index of Voice bot component to change its flag to True"""
      
      сandidates = tool_context.state["сandidates"]
      pipeline = tool_context.state["pipelines"]
      candidates_truncated =  tool_context.state["candidates_truncated"]

      if indxs is not None and names is not None:
        candidates_filtered = []
        candidates_truncated_filtered = []
        
        for candidate in сandidates[indx_of_pipeline]:
              if candidate["id"] not in indxs and candidate["person_name"] not in names:
                candidates_filtered.append(candidate)
                candidates_truncated_filtered.append(" ".join([str(candidate["id"]), candidate["person_name"]]))
                

        сandidates[indx_of_pipeline] = candidates_filtered 
        candidates_truncated[indx_of_pipeline] = candidates_truncated_filtered

      pipeline[indx_of_pipeline]["chain"][index_of_component]["ready_to_send_people"] = True
      tool_context.state["сandidates"] = сandidates
      tool_context.state["pipelines"] = pipeline
      tool_context.state["candidates_truncated"] = candidates_truncated