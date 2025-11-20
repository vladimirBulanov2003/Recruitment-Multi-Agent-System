import httpx
import asyncio

class ATSClient():
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    async def get_candidates(self, number_of_resumes = 5):

        r = await self.client.get("/get_candidates", params={"number_of_resumes": number_of_resumes})
        return r.json()

async def main():
    ats = ATSClient("http://0.0.0.0:80")

asyncio.run(main())


    
