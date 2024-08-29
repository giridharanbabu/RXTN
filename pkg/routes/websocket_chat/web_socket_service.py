from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from typing import List
from pydantic import BaseModel
import json

from starlette import status

from pkg.database.database import database
import uuid
from datetime import datetime
import logging

websocket_router = APIRouter()
chat_collection = database.get_collection("socket_chat")


# Store connected clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


# Helper function to create a unique chat ID
def create_unique_chat_id():
    return str(uuid.uuid4())


connected_users = {}


@websocket_router.websocket("/ws/{user_id}/{chat_id}")
async def websocket_endpoint(user_id: str, chat_id: str, websocket: WebSocket):
    try:
        logging.info(f"Attempting WebSocket connection: User {user_id}, Chat {chat_id}")
        await websocket.accept()
        # Rest of the WebSocket code...
    except Exception as e:
        logging.error(f"WebSocket connection rejected: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)

# @websocket_router.websocket("/ws/chat/{user_id}/{chat_id}")
# @websocket_router.websocket("/ws/{user_id}")
# async def websocket_endpoint(user_id: str, websocket: WebSocket):
#     await websocket.accept()
#
#     # Store the WebSocket connection in the dictionary
#     connected_users[user_id] = websocket
#
#     try:
#         while True:
#             data = await websocket.receive_text()
#             # Send the received data to the other user
#             for user, user_ws in connected_users.items():
#                 if user != user_id:
#                     await user_ws.send_text(data)
#     except:
#         # If a user disconnects, remove them from the dictionary
#         del connected_users[user_id]
#         await websocket.close()

# async def websocket_endpoint(user_id, chat_id, websocket: WebSocket):
#     await manager.connect(websocket)
#     connected_users[user_id] = websocket
#     try:
#         while True:
#             data = await websocket.receive_text()
#             await manager.broadcast(f"Client says: {data}")
#             # Create or update the conversation in MongoDB
#             chat_message = {
#                 "user_id": user_id,
#                 "message": data,
#                 "timestamp": datetime.utcnow()
#             }
#             try:
#                 # Append message to the existing chat document, or create it if it doesn't exist
#                 chat_collection.update_one(
#                     {"chat_id": chat_id},
#                     {
#                         "$push": {"messages": chat_message},
#                         "$setOnInsert": {
#                             "chat_id": chat_id,
#                             "created_at": datetime.utcnow()
#                         }
#                     },
#                     upsert=True
#                 )
#                 logging.info(f"Message appended to chat {chat_id}.")
#             except Exception as e:
#                 logging.error(f"Error updating chat {chat_id} in MongoDB: {e}")
#
#             # Send the received data to other users in the same chat
#             for user, user_ws in connected_users.items():
#                 if user != user_id:
#                     await user_ws.send_text(data)
#     except WebSocketDisconnect:
#         manager.disconnect(websocket)
#         await manager.broadcast("Client left the chat")
