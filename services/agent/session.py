
from dotenv import load_dotenv
import json 
import asyncio, httpx
from math import ceil

load_dotenv()

client_ai_matching_agent = httpx.AsyncClient(timeout=None)
client_create_session_in_adk = httpx.AsyncClient(timeout=None)
client_delete_session_in_adk = httpx.AsyncClient(timeout=None)
client_calling_agent = httpx.AsyncClient(timeout=None)


            
async def create_session(i):
        url = f"http://localhost:8000/apps/resume_search_llm/users/u_123/sessions/{i}"
        r = await client_create_session_in_adk.post(url)   
        r.raise_for_status()
        return r.json()

async def delete_session(i):
        url = f"http://localhost:8000/apps/resume_search_llm/users/u_123/sessions/{i}"
        r = await client_delete_session_in_adk.delete(url)   
        r.raise_for_status()
        return r.json()

async def search(candidates, description_of_resume, index_of_session, conditions, sem):
        async with sem:
            
            async with conditions["lock"]:
                if conditions["number_of_candidates"] <= 0:
                    return {"result" : None}

            try: 
                url = f"http://localhost:8000/run"
                await create_session(index_of_session)

                dictionary = {"desired_resume":  description_of_resume, "list_of_candidates": candidates}
                payload = {
                    "app_name": "resume_search_llm",
                    "user_id": "u_123",
                    "session_id": f"{index_of_session}", 
                    "new_message": {
                        "role": "user",
                        "parts": [
                            {"text" : json.dumps(dictionary)}
                        ]      
                    }
                }
            
                answer = await client_ai_matching_agent.post(url, json=payload)  
                clean_text = answer.json()[0]["content"]["parts"][0]["text"]
                parsed = json.loads(clean_text)
                answer.raise_for_status()
                
                if parsed is None or not isinstance(parsed, dict):
                    return {"result": None}
                
                candidates_list = parsed.get("list_of_candidates")
                if candidates_list is None or len(candidates_list) == 0:
                    return {"result": None}
                
                async with conditions["lock"]:
                    if conditions["number_of_candidates"] <= 0:
                        return {"result" : None}
                    else: 
                         number_found_candidates = len(parsed["list_of_candidates"])
                         how_many_can_be_added = min(conditions["number_of_candidates"], number_found_candidates)

                         #await client_calling_agent.post("http://0.0.0.0:8002/call_webhook", json = parsed["list_of_candidates"])  

                         conditions["number_of_candidates"] -= how_many_can_be_added
                
                return {"result" : parsed["list_of_candidates"][:how_many_can_be_added]}
            
            finally:
                 await delete_session(index_of_session)



async def searching_of_candidates(jobpost, number_of_candidates, data, start_index):
    batch_size = 5
    sem = asyncio.Semaphore(number_of_candidates + 2)  
    lock = asyncio.Lock()
    conditions = {"number_of_candidates" : number_of_candidates, "lock": lock}
    res = await asyncio.gather(*[search(data[index: index+batch_size], jobpost, index + start_index, conditions, sem) 
                                 for index in range(0, len(data), batch_size)])
    print("результаты в ai matching: ", res)
    return res
    


