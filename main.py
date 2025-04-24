from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import time
from collections import defaultdict
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
import pytz
import json

app = FastAPI()


class message(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    timestamp:  datetime = Field(default_factory=lambda: datetime.now(tz=pytz.utc))


connected_clients = []
user_message_times = defaultdict(list)

MAX_CALLS = 5
TIME_FRAME = 1  

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    client_id = websocket.client.host
    try:
        while True:
            #message validation
            raw_data = await websocket.receive_text()
            try:
                msg=message.model_validate_json(raw_data)
            except ValidationError as e:
                await websocket.send_text(f"Validation error: {e}")
                continue


            now = time.time()
            
            times = user_message_times[client_id]
            #Rate limiting to 5 messages per 1 second with sliding window
            times = [t for t in times if now - t < TIME_FRAME]
            if len(times) >= MAX_CALLS:
                await websocket.send_text(" Rate limit exceeded. Please slow down.")
                continue
            times.append(now)
            user_message_times[client_id] = times

            
            #Sends message to all Clients
            for client in connected_clients: 
                await client.send_text(json.dumps({
                    "text": msg.text,
                    "timestamp": msg.timestamp.isoformat()
                }))
    except WebSocketDisconnect:
        pass
    #Cleaning up disconnected clients for memory
    finally:
        connected_clients.remove(websocket)
        user_message_times.pop(client_id, None)