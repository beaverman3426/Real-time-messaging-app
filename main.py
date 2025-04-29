from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import time
from collections import defaultdict
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
import pytz
import json
import asyncio
from db import get_db_session

app = FastAPI()


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    timestamp:  datetime = Field(default_factory=lambda: datetime.now(tz=pytz.utc))
    user: str = Field(min_length=1, max_length=30)


connected_clients = set()
user_message_times = defaultdict(list)

MAX_CALLS = 5
TIME_FRAME = 1  


CONVO_ID = "global_chat"
session = get_db_session()

def save_message_to_db(msg: Message):
    bucket_month = msg.timestamp.strftime("%Y-%m")
    session.execute(
        """
        INSERT INTO messages_by_conversation (convo_id, bucket_month, timestamp, user, text)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (CONVO_ID, bucket_month, msg.timestamp, msg.user, msg.text)
    )

def get_recent_messages(limit=20):
    now = datetime.now(tz=pytz.utc)
    bucket_month = now.strftime("%Y-%m")
    rows = session.execute(
        """
        SELECT text, timestamp, user FROM messages_by_conversation
        WHERE convo_id = %s AND bucket_month = %s
        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (CONVO_ID, bucket_month, limit)
    )
    
    return list(reversed(list(rows)))



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    client_id = websocket.client.host
    #sending last 20 messages

    recent_messages = get_recent_messages(limit=20)
    for row in recent_messages:
        await websocket.send_text(json.dumps({
            "text": row.text,
            "timestamp": row.timestamp.isoformat(),
            "user": row.user
        }))


    try:
        while True:
            #message validation
            raw_data = await websocket.receive_text()
            try:
                msg=Message.parse_raw(raw_data)
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
            save_message_to_db(msg)


            
            #Sends message to all Clients
            send_tasks = [
            client.send_text(json.dumps({
                "text": msg.text,
                "timestamp": msg.timestamp.isoformat(),
                "user": msg.user
            }))
            for client in connected_clients
        ]
            await asyncio.gather(*send_tasks, return_exceptions=True)
    except WebSocketDisconnect:
        pass
    #Cleaning up disconnected clients for memory
    finally:
        connected_clients.remove(websocket)
        user_message_times.pop(client_id, None)