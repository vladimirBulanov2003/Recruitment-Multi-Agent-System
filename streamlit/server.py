from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from typing import List
import uvicorn

app = FastAPI(title="Pipeline WebSocket Server")

# CORS для Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Список подключенных WebSocket клиентов
connected_clients: List[WebSocket] = []

class PipelineBroadcast(BaseModel):
    index: str
    pipeline: dict

@app.post("/broadcast")
async def broadcast_pipeline(data: PipelineBroadcast):
    """Принимает pipeline от агента и отправляет всем подключенным клиентам"""
    print(f"📡 Broadcasting pipeline #{data.index} to {len(connected_clients)} clients")
    
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_json({
                "index": data.index,
                "pipeline": data.pipeline
            })
        except Exception as e:
            print(f"❌ Failed to send to client: {e}")
            disconnected.append(client)
    
    # Удаляем отключенных клиентов
    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)
    
    return {"status": "ok", "clients_notified": len(connected_clients)}

@app.websocket("/ws/pipelines")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для Streamlit"""
    await websocket.accept()
    connected_clients.append(websocket)
    print(f"✅ New client connected. Total: {len(connected_clients)}")
    
    try:
        # Держим соединение открытым
        while True:
            # Ждем ping от клиента (keep-alive)
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"❌ Client disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"📊 Remaining clients: {len(connected_clients)}")

@app.get("/")
async def root():
    return {
        "status": "running",
        "connected_clients": len(connected_clients)
    }


# ДОБАВИТЬ новый endpoint:

from pydantic import BaseModel

class PipelineStatusUpdate(BaseModel):
    index_of_pipeline: str
    index_of_component: int
    state_changes: dict
    clients_stats: dict = None  # Опционально для voice_bot

class CandidatesBroadcast(BaseModel):
    index_of_pipeline: str
    candidates: list
    count: int

@app.post("/update_pipeline_status")
async def update_pipeline_status(data: PipelineStatusUpdate):
    """Принимает обновление статуса от Task Manager и обновляет pipeline"""
    print(f"📝 Updating pipeline #{data.index_of_pipeline}, component #{data.index_of_component}")
    
    import json
    from pathlib import Path
    
    PIPELINES_FILE = Path("/tmp/maya_pipelines.json")
    
    try:
        if PIPELINES_FILE.exists():
            # Читаем с проверкой на пустой файл
            with open(PIPELINES_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    pipelines = []
                else:
                    pipelines = json.loads(content)
            
            # Находим нужный pipeline
            for pipeline in pipelines:
                if pipeline["id"] == data.index_of_pipeline:
                    # Обновляем статус компонента
                    component = pipeline["components"][data.index_of_component]
                    for key, value in data.state_changes.items():
                        component["status"][key] = value
                    
                    # Обновляем clients_stats если есть (для voice_bot)
                    if data.clients_stats:
                        component["clients_stats"] = data.clients_stats
                    
                    # Сохраняем обратно
                    with open(PIPELINES_FILE, "w") as f:
                        json.dump(pipelines, f, indent=2)
                    
                    print(f"✅ Updated pipeline file")
                    
                    # Отправляем broadcast всем клиентам
                    broadcast_data = {
                        "type": "status_update",
                        "index_of_pipeline": data.index_of_pipeline,
                        "index_of_component": data.index_of_component,
                        "state_changes": data.state_changes
                    }
                    
                    if data.clients_stats:
                        broadcast_data["clients_stats"] = data.clients_stats
                    
                    disconnected = []
                    for client in connected_clients:
                        try:
                            await client.send_json(broadcast_data)
                        except Exception as e:
                            print(f"❌ Failed to send to client: {e}")
                            disconnected.append(client)
                    
                    for client in disconnected:
                        if client in connected_clients:
                            connected_clients.remove(client)
                    
                    return {"status": "ok", "clients_notified": len(connected_clients)}
        
        return {"status": "pipeline_not_found"}
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return {"status": "error", "message": "Invalid JSON in file"}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/broadcast_candidates")
async def broadcast_candidates(data: CandidatesBroadcast):
    """Отправляет информацию о найденных кандидатах в Streamlit чат"""
    print(f"📋 Broadcasting {data.count} candidates for pipeline #{data.index_of_pipeline}")
    
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_json({
                "type": "candidates_found",
                "index_of_pipeline": data.index_of_pipeline,
                "candidates": data.candidates,
                "count": data.count
            })
        except Exception as e:
            print(f"❌ Failed to send to client: {e}")
            disconnected.append(client)
    
    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)
    
    return {"status": "ok", "clients_notified": len(connected_clients)}

if __name__ == "__main__":
    print("🚀 Starting WebSocket server on http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765)