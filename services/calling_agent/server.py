
import asyncio
import random
from fastapi import FastAPI
from contextlib import asynccontextmanager
from pathlib import Path
import sys
import uvicorn

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from models.candidate_resume import Resume


call_sem = asyncio.Semaphore(8)
state_dict = {}
tasks_dict = {}

from typing import List


async def make_call(candidate: dict, state: dict):
    try:
        async with call_sem:
            await asyncio.sleep(random.uniform(1, 100))
            state["accept_call"] = True
            await asyncio.sleep(random.uniform(1, 10))
            state["finished_call"] = True
            if random.random() < 0.7:
                print(f"Кандидат {candidate} ответил на звонок")
                state["approved"] = True
                return {"result": candidate}
            else:
                state["approved"] = False
                return {"result": None}
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print("уведомление сломалось:", e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    app.state.loop = loop
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/call_webhook")
async def call_webhook(candidates: List[Resume], index: int):
    state_dict[index] = [
        {"candidate_name": candidate.person_name, "accept_call": False, "approved": False, "finished_call": False}
        for candidate in candidates
    ]

    tasks_dict.setdefault(index, [])
    for candidate, state in zip(candidates, state_dict[index]):
        tasks_dict[index].append(app.state.loop.create_task(make_call(candidate, state)))

    return {"status": "started"}

@app.post("/check_status")
async def check_status(index: int):
    return state_dict.get(index, [])

@app.post("/kill_task")
async def kill_process(index: int):
    for task in tasks_dict.get(index, []):
        task.cancel()
    return {"status": "cancelled"}




if __name__ == "__main__":
    print("Starting FastAPI server...")
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8002, 
        reload=False
    )