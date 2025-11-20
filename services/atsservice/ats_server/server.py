from fastapi import FastAPI, HTTPException
import json
import numpy as np
import asyncio
import random
import uvicorn
from pathlib import Path

app = FastAPI()

server_dir = Path(__file__).parent
json_file = server_dir / "new_can.json"

with open(json_file, "r", encoding="utf-8") as f:
    data = json.load(f)

statisitc = {}

@app.get("/get_candidates")
async def get_candidates(number_of_resumes: int):

    if number_of_resumes > len(data["list_of_resumes"]):
         raise HTTPException(status_code=400, detail="Too many resumes requested") 
    
    time = random.uniform(1, 4)
    
    await asyncio.sleep(time)
    list_of_candidates = np.array(data["list_of_resumes"])


    return {"chosen_candidates": 
            np.random.choice(list_of_candidates, number_of_resumes, replace = False).tolist()
            }


    

if __name__ == "__main__":
    print("Starting FastAPI server...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080, 
        reload=False
    )