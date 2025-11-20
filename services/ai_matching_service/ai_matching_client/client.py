import httpx
import numpy as np
import asyncio
from models.candidate_resume import Resume

class AIMatching_service_client:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=None )

    async def add_candidates(self, candidates: list[dict]): 
    
        r = await self.client.post(f"{self.base_url}/add_candidates", json=candidates)
        r.raise_for_status()
        return {"status" : "OK"}
    
    async def start_search_top_candidates(self, jobpost : str, number_of_candidates: int):
        await self.client.get(f"{self.base_url}/start_search_candidates", params={"jobpost": jobpost, "number_of_candidates" : number_of_candidates})
        return {"status" : "OK"}

    
