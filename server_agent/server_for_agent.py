
import os
import uvicorn
from google.adk.sessions import InMemorySessionService
import time
from google.adk.events import Event, EventActions
from typing import Any, Dict
from fastapi import FastAPI
from google.genai import types
from google.adk.runners import Runner
from chat_bot_agent.agent import root_agent
from .process_responces import process_agent_response
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


session_service = InMemorySessionService()

APP_NAME = "agents"


app = FastAPI()


runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

@app.post("/users/{user_id}/sessions/{session_id}/create_session")
async def create_session(user_id:str, session_id:str):

    initial_state = {"pipelines" : {},

      "сandidates": {},
      "candidates_truncated": {},
      "candidates_screened": {},
      "candidates_approved_offer": {}
       }

    await session_service.create_session(
        app_name= APP_NAME,
        user_id=user_id,
        session_id = session_id,
        state=initial_state,
    )
    return {"status": "session has been created"}

      
@app.post("/users/{user_id}/sessions/{session_id}/delete_session")
async def delete_session(user_id, session_id):
    await session_service.delete_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    return {"status": "session has been deleted"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/users/{user_id}/sessions/{session_id}/get_session")
async def get_session(user_id: str, session_id: str):
    final_session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    return {"status":final_session}


@app.post("/run")
async def run_agent(user_id: str, session_id: str, message: str):
    try:
        сontent = types.Content(role="user", parts=[types.Part(text=message)])
        final_answer = None
        
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=сontent
        ):
            if event.author:
                agent_name = event.author

            response = await process_agent_response(event)
            if response:
                final_answer = response
        
        if final_answer:
            return {"answer": final_answer}
        else:
            return {"answer": "Agent did not return the answer"}
            
    except Exception as e:
        return {"answer": f"Error: {str(e)}"} 


@app.websocket("/ws/update_session_state")
async def update_session_state_ws(websocket: WebSocket):
    await websocket.accept()
    print("Client has just connected")

    try:
        while True:
            data: Dict[str, Any] = await websocket.receive_json()

            user_id = data.get("user_id")
            session_id = data.get("session_id")
            state_changes = data.get("state_changes", {})
            index_of_pipeline = data.get("index_of_pipeline")
            index_of_component = data.get("index_of_component")
            type_of_component = data.get("type_of_component")
            text= ""

            print("Data:", data)

            session = await session_service.get_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
            
            new_interaction_history = session.state.copy()
            print(f"Retrieved session: {session.id if session else 'None'}")
         
            if (type_of_component == "ai_matching"):
                people = data.get("candidates")
                for batch in people:
                    candidates = batch["result"]
                    if (candidates != None):
                        for candidate in candidates:
                            print("Candidate:",  candidate )
                            new_interaction_history["сandidates"][index_of_pipeline].append(candidate) 
                            new_interaction_history["candidates_truncated"][index_of_pipeline].append(
                                " ".join([str(candidate["id"]), candidate["person_name"]]) )


                if (len(new_interaction_history["сandidates"][index_of_pipeline]) == 0):
                        
                        new_interaction_history["сandidates"][index_of_pipeline] = None  
                        text += f"Candidates for pipeline {index_of_pipeline} have not been found for the resume!" 
                else:
                        text += f"We have found at least one candidate for pipeline {index_of_pipeline} for the resume" 


            if (type_of_component == "voice_bot_component"):
                print(data)
                if  data.get("finish_task") != None:
                    print(data.get("finish_task"))

                    finish_task = data.get("finish_task")
                    status_about_each_candidate = data.get("status_about_each_candidate")
                    for status in status_about_each_candidate:
                        print(f"status about the person: {status}")
                        if status["accept_call"] == True and status["candidate_name"] not in new_interaction_history["candidates_screened"][index_of_pipeline]:
                            new_interaction_history["candidates_screened"][index_of_pipeline].append(status["candidate_name"])

                        if status["approved"] == True and status["candidate_name"] not in new_interaction_history["candidates_approved_offer"][index_of_pipeline]:
                            new_interaction_history["candidates_approved_offer"][index_of_pipeline].append(status["candidate_name"])
                            name = status["candidate_name"]
                            print(f"Candidate {name} has just approved our offer")
                            text += f"Candidate {name} has just approved our offer \n"

                    if finish_task and state_changes["COMPLETED"] == True:
                        text += f"Calling of candidates for pipeline number {index_of_pipeline} was completed successfully! \n" 

                    if finish_task and state_changes["COMPLETED"] == False:
                        text += f"Calling of candidates for pipeline number {index_of_pipeline} was interrupted! \n" 



            for key,value in state_changes.items():
                new_interaction_history["pipelines"][index_of_pipeline]["chain"][index_of_component]["status"][key] = value
            

            print(f"Updating session state for app='{APP_NAME}', user='{user_id}', session='{session_id}'")
            print(f"State changes to apply: {state_changes}")

            actions_with_update = EventActions(state_delta=new_interaction_history)
            text += f"Session state updated successfully. \n"

            system_event = Event(
                invocation_id="inv_login_update",
                author="system",
                timestamp=time.time(),
                actions=actions_with_update,
                content=types.Content(
            role="system", 
            parts=[types.Part(text=text)]
        ), )
                
            
            await session_service.append_event(session, system_event)

            await websocket.send_json({"message": "Session state updated successfully."})

    except WebSocketDisconnect:
        print("Cleint has been disconected")


if __name__ == "__main__":
    print("Starting FastAPI server...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=9999, 
        reload=False
    )