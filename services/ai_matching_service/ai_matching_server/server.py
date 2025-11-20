from fastapi import FastAPI
from ...agent.session import searching_of_candidates
import asyncio
from math import ceil
import uvicorn

 
app = FastAPI()
memory = {"list_of_candidates": []}
status = {}
index = 0
lock = asyncio.Lock()


@app.post("/add_candidates")
async def add_candidates(candidates: list[dict]):
    for candidate in candidates:
        memory["list_of_candidates"].append(candidate)


@app.get("/start_search_candidates")
async def search_candidates(jobpost: str, number_of_candidates: int):

    print(f"Запустили поиск кандидатов для резюме {jobpost}")
    global index
    num_of_indexes = ceil(len(memory["list_of_candidates"]) / 5) 
    async with lock:
        index += (num_of_indexes + 1)

    start_index = index 

    result = await searching_of_candidates(jobpost, number_of_candidates, memory["list_of_candidates"], start_index)
    print("Все ок")
    return {"result": result}
    
@app.get("/get_memory")
async def search_candidates():
         return memory


if __name__ == "__main__":
    print("Starting FastAPI server...")
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8001, 
        reload=False
    )