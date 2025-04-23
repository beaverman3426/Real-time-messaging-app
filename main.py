from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import time
from collections import defaultdict
from pydantic import BaseModel, Field, ValidationError
app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(JSON.stringify({ text: input.value }))

                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""
class message(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@app.get("/")
async def get():
    return HTMLResponse(html)


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
                await client.send_text(f"Message: {msg.text}")
    except WebSocketDisconnect:
        pass
    #Cleaning up disconnected clients for memory
    finally:
        connected_clients.remove(websocket)
        user_message_times.pop(client_id, None)