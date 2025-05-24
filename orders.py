from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth, db
from typing import List

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://th3-restaurant.firebaseio.com/"
})

app = FastAPI()

# -------------------------
# 👨‍🍳 Connection Manager
# -------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


# -------------------------
# 🔐 Chef User Model
# -------------------------
class ChefUser(BaseModel):
    email: str
    name: str
    password: str
    enabled: bool = True


# -------------------------
# ✅ Add or Update Chef
# -------------------------
@app.post("/add-chef")
async def add_chef(chef: ChefUser):
    try:
        # 1. Firebase Auth user creation or update
        try:
            user = auth.get_user_by_email(chef.email)
            auth.update_user(user.uid, password=chef.password)
        except auth.UserNotFoundError:
            user = auth.create_user(email=chef.email, password=chef.password)

        # 2. Firebase DB (chef_users) entry
        chef_data = {
            "email": chef.email,
            "name": chef.name,
            "enabled": chef.enabled
        }
        ref = db.reference("chef_users")
        snapshot = ref.order_by_child("email").equal_to(chef.email).get()
        if snapshot:
            key = list(snapshot.keys())[0]
            ref.child(key).update(chef_data)
        else:
            ref.push(chef_data)

        return {"success": True, "message": f"Chef {chef.email} saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# ❌ Delete Chef
# -------------------------
@app.delete("/delete-chef/{email}")
def delete_chef(email: str):
    try:
        try:
            user = auth.get_user_by_email(email)
            auth.delete_user(user.uid)
        except auth.UserNotFoundError:
            pass

        ref = db.reference("chef_users")
        snapshot = ref.order_by_child("email").equal_to(email).get()
        if snapshot:
            key = list(snapshot.keys())[0]
            ref.child(key).delete()
            return {"success": True, "message": f"Deleted {email} from database and auth."}
        else:
            return {"success": False, "message": "No such chef found in database."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# 🔁 Get All Chefs
# -------------------------
@app.get("/chef-users")
def get_chef_users():
    try:
        ref = db.reference("chef_users")
        users = ref.get()
        return users or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# 📡 WebSocket: Kitchen Orders
# -------------------------
@app.websocket("/ws/kitchen")
async def kitchen_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data)  # or handle it
    except WebSocketDisconnect:
        manager.disconnect(websocket)
