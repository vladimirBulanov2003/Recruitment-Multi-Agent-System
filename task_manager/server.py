from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
import asyncio
import websockets
import json
import httpx
import url
from apscheduler.schedulers.asyncio import AsyncIOScheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    app.state.loop = loop
    app.state.client_ats =  httpx.AsyncClient(base_url= url.url_ats, 
                                              timeout=None)
    app.state.client_ai_matching = httpx.AsyncClient(base_url= url.url_ai_matching, 
                                                     timeout=None)
    app.state.client_voice_bot = httpx.AsyncClient(base_url= url.url_voice_bot, 
                                                     timeout=None)
    app.state.scheduler = AsyncIOScheduler()

    app.state.scheduler.start()

    yield 

app = FastAPI(lifespan=lifespan)

async def task_for_adding_people_to_ai_matching(parameters: dict):

    ws = await websockets.connect(url.url_agent_websocket)

    try: 
        response = await app.state.client_ats.get("/get_candidates", 
        params = {"number_of_resumes" : parameters["number_of_resumes"]})

        candidates =  response.json()["chosen_candidates"]
        await  app.state.client_ai_matching.post("/add_candidates", json= candidates)
                
        payload = {"user_id": "0", "session_id":"0",
                        "index_of_pipeline": parameters["index_of_pipeline"], 
                        "index_of_component": parameters["index_of_component"],
                        "type_of_component": "ats_component",
                        "state_changes": {"COMPLETED" : True, "NOT_STARTED": False}}
                
        await ws.send(json.dumps(payload))
        response = await ws.recv()

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://localhost:8765/update_pipeline_status",
                    json={
                        "index_of_pipeline": parameters["index_of_pipeline"],
                        "index_of_component": parameters["index_of_component"],
                        "state_changes": {"COMPLETED": True, "NOT_STARTED": False}
                    }
                )
        except Exception as e:
            print(f"Failed to update Streamlit: {e}")


        print(f"Ответ: {response}")
    finally:
        await ws.close()


async def task_for_ai_matching(parameters: dict):
    ws = await websockets.connect(url.url_agent_websocket)
    try:
        result = await app.state.client_ai_matching.get("/start_search_candidates", 
                                                            params = {"jobpost" : parameters["resume"], 
                                                                    "number_of_candidates": parameters["number_of_candidates"]})
        print("результат:", result.json()["result"])
        payload = {"user_id": "0", "session_id":"0",
                        "index_of_pipeline": parameters["index_of_pipeline"],
                        "index_of_component": parameters["index_of_component"],
                        "type_of_component": "ai_matching",
                        "candidates": result.json()["result"],
                        "state_changes": {"COMPLETED" : True, "NOT_STARTED": False}}
                
        await ws.send(json.dumps(payload))
        response = await ws.recv()
        print(f"Ответ: {response}")

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://localhost:8765/update_pipeline_status",
                    json={
                        "index_of_pipeline": parameters["index_of_pipeline"],
                        "index_of_component": parameters["index_of_component"],
                        "state_changes": {"COMPLETED": True, "NOT_STARTED": False}
                    }
                )
        except Exception as e:
            print(f"Failed to update Streamlit: {e}")

       
        candidates_data = result.json()["result"]
        print(f"🔍 AI Matching result structure: {type(candidates_data)}, length: {len(candidates_data) if isinstance(candidates_data, list) else 'N/A'}")
        print(f"🔍 First batch: {candidates_data[0] if candidates_data else 'empty'}")
        
        candidates_found = []
        
        for i, batch in enumerate(candidates_data):
            print(f"🔍 Processing batch {i}: {type(batch)}, has 'result': {batch.get('result') if isinstance(batch, dict) else 'not a dict'}")
            if batch and batch.get("result"):
                candidates_found.extend(batch["result"])
                print(f"✅ Added {len(batch['result'])} candidates from batch {i}")
        
        print(f"🔍 Total candidates found: {len(candidates_found)}")
        
        if candidates_found:
            print(f"📤 Attempting to send {len(candidates_found)} candidates to Streamlit...")
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8765/broadcast_candidates",
                        json={
                            "index_of_pipeline": parameters["index_of_pipeline"],
                            "candidates": candidates_found,
                            "count": len(candidates_found)
                        }
                    )
                    print(f"✅ Sent {len(candidates_found)} candidates to Streamlit. Response: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Failed to send candidates to Streamlit: {e}")
        else:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "http://localhost:8765/broadcast_candidates",
                        json={
                            "index_of_pipeline": parameters["index_of_pipeline"],
                            "candidates": [],
                            "count": 0
                        }
                    )
                    print(f"⚠️ No candidates found, notification sent to Streamlit")
            except Exception as e:
                print(f"⚠️ Failed to send no-candidates notification: {e}")
    
        
    finally:
        await ws.close()



async def check_status(index_of_task: int, index_of_pipeline: str, index_of_component: int, scheduler: AsyncIOScheduler):
    
    response = await app.state.client_voice_bot.post(
    f"/check_status?index={index_of_task}"
)
    statuses_json = response.json()
    finish_task = all(candidate["finished_call"] for candidate in statuses_json)

    async with websockets.connect(url.url_agent_websocket) as ws:
        print("Отправялем по вебсокету")
        payload = {
            "user_id": "0",
            "session_id": "0",
            "index_of_pipeline": index_of_pipeline,
            "index_of_component": index_of_component,
            "type_of_component": "voice_bot_component",
            "finish_task": finish_task,
            "status_about_each_candidate": statuses_json,
            "state_changes": {"RUNNING": not finish_task, "COMPLETED": finish_task}
        }
        await ws.send(json.dumps(payload))

    answered = sum(1 for c in statuses_json if c["accept_call"])
    approved = sum(1 for c in statuses_json if c["approved"])
    declined = sum(1 for c in statuses_json if c["accept_call"] and not c["approved"])


    accepted_candidates = [
        {"name": c.get("candidate_name", "Unknown"), "phone": ""}
        for c in statuses_json if c["approved"]
    ]
    
    declined_candidates = [
        {"name": c.get("candidate_name", "Unknown"), "phone": ""}
        for c in statuses_json if c["accept_call"] and not c["approved"]
    ]

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "http://localhost:8765/update_pipeline_status",
                json={
                    "index_of_pipeline": index_of_pipeline,
                    "index_of_component": index_of_component,
                    "state_changes": {"RUNNING": not finish_task, "COMPLETED": finish_task},
                    "clients_stats": {
                        "total": len(statuses_json),
                        "answered": answered,
                        "accepted_offer": approved,
                        "declined_offer": declined,
                        "accepted_candidates": accepted_candidates,  # НОВОЕ: Список принявших
                        "declined_candidates": declined_candidates   # НОВОЕ: Список отклонивших
                    }
                }
            )
    except Exception as e:
        print(f"⚠️ Failed to update Streamlit: {e}")

    if finish_task:
        scheduler.remove_job(job_id = index_of_pipeline)
        print(f"Задача {index_of_pipeline} завершена и удалена из scheduler")
    


async def task_for_voice_bot(parameters: dict, scheduler: AsyncIOScheduler):
    async with websockets.connect(url.url_agent_websocket) as ws:

        
        result = await app.state.client_voice_bot.post("/call_webhook", params={"index":parameters["index_of_pipeline"] }, json= parameters["candidates"]["candidates"])

        if result.json()["status"] == "started":

            payload = {
                "user_id": "0",
                "session_id": "0",
                "index_of_pipeline": parameters["index_of_pipeline"],
                "index_of_component": parameters["index_of_component"],
                "type_of_component": "voice_bot_component",
                "finish_task": None,
                "status_about_each_candidate": None,
                "state_changes": {"NOT_STARTED": False, "RUNNING": True}
            }

            await ws.send(json.dumps(payload))
            response = await ws.recv()
            print(f"Ответ: {response}")

            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "http://localhost:8765/update_pipeline_status",
                        json={
                            "index_of_pipeline": parameters["index_of_pipeline"],
                            "index_of_component": parameters["index_of_component"],
                            "state_changes": {"NOT_STARTED": False, "RUNNING": True}
                        }
                    )
            except Exception as e:
                print(f"Failed to update Streamlit: {e}")

            scheduler.add_job(
                check_status,
                'interval',
                seconds=3,
                args=[
                    int(parameters["index_of_pipeline"]),  
                    parameters["index_of_pipeline"],  
                    parameters["index_of_component"],
                    scheduler,
                
                ],
                id=parameters["index_of_pipeline"]
            )
            print(f"Задача для проверки статуса {parameters['index_of_pipeline']} добавлена в scheduler")

@app.post("/kill_voice_bot_task") 
async def kill_voice_bot_task(index_of_pipeline : str, index_of_component: int):
    
    result = await app.state.client_voice_bot.post("/kill_task", params={"index": int(index_of_pipeline)})
    print(f"🛑 Voice Bot task killed: {result.json()['status']}")

    try:
        app.state.scheduler.remove_job(index_of_pipeline)
        print(f"✅ Removed job {index_of_pipeline} from scheduler")
    except Exception as e:
        print(f"⚠️ Job {index_of_pipeline} not found in scheduler: {e}")

    ws = await websockets.connect(url.url_agent_websocket)

    payload = {
                "user_id": "0",
                "session_id": "0",
                "index_of_pipeline": index_of_pipeline,
                "index_of_component": index_of_component,
                "type_of_component": "voice_bot_component",
                "finish_task": True,
                "status_about_each_candidate": [],
                "state_changes": {"INTERRUPTED": True, "RUNNING": False, "COMPLETED" : False}
            }
    
    await ws.send(json.dumps(payload))
    response = await ws.recv()
    print(f"📥 Agent response: {response}")
    await ws.close()

    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "http://localhost:8765/update_pipeline_status",
                json={
                    "index_of_pipeline": index_of_pipeline,
                    "index_of_component": index_of_component,
                    "state_changes": {"INTERRUPTED": True, "RUNNING": False, "COMPLETED": False}
                }
            )
            print(f"✅ Sent INTERRUPTED status to Streamlit for pipeline #{index_of_pipeline}")
    except Exception as e:
        print(f"⚠️ Failed to update Streamlit: {e}")
    
    
    return {"status": "cancelled", "pipeline": index_of_pipeline} 




@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/create_tasks")
async def create_tasks(type_of_component: str, index_of_pipeline : str, index_of_component: int, data: dict):


    print("ПРИШЛО-")
    print(type_of_component)
    print(index_of_pipeline)
    print(index_of_component)
    print("---------")
    print(data)
    dictionary_for_arguments = {}
    dictionary_for_arguments["index_of_pipeline"] = index_of_pipeline
    dictionary_for_arguments["index_of_component"] = index_of_component
    data = data["data"]

    if type_of_component == "ATS":
        number_of_resumes = data["number_of_resumes"]
        print("Число резюме")
        print(number_of_resumes)
        if number_of_resumes is None:
            return {"error": "number_of_resumes is required for ATS component"}
    
        dictionary_for_arguments["number_of_resumes"] = number_of_resumes
        app.state.loop.create_task(task_for_adding_people_to_ai_matching(dictionary_for_arguments))

    if type_of_component == "AI_Matching":
        dictionary_for_arguments["resume"] = data["resume"]
        dictionary_for_arguments["number_of_candidates"] = data["number_of_candidates"]
        app.state.loop.create_task(task_for_ai_matching(dictionary_for_arguments))

    if type_of_component == "Voice_bot":
        dictionary_for_arguments["candidates"] = data["candidates"]
        app.state.loop.create_task(task_for_voice_bot(dictionary_for_arguments, scheduler= app.state.scheduler))
        return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7999)
