import os
import time
import requests
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import razorpay

from models import Order, WeatherInfo
from fastapi import Body
from orders import ConnectionManager
from ai import get_ai_special, get_weather_based_recommendation

import firebase_admin
from firebase_admin import credentials, db

# ✅ Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        "databaseURL": os.getenv("FIREBASE_DB_URL") or "https://th3-restaurant-default-rtdb.asia-southeast1.firebasedatabase.app"
    })

app = FastAPI()

# CORS: allow frontend at port 5500
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
manager = ConnectionManager()

# Razorpay client setup
razorpay_client = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
)

# Pydantic models for payment flow
class PaymentRequest(BaseModel):
    amount: float
    currency: str = "INR"
    receipt: str | None = None

class PaymentVerification(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

@app.get("/")
def home():
    return {"message": "FastAPI backend is live and working!"}

# ✅ Razorpay Online Order - Create Order
@app.post("/create-order")
async def create_order(payment_request: PaymentRequest):
    try:
        data = {
            "amount": int(payment_request.amount * 100),
            "currency": payment_request.currency,
            "payment_capture": 1
        }
        if payment_request.receipt:
            data["receipt"] = payment_request.receipt

        order = razorpay_client.order.create(data=data)
        return {
            "id": order.get("id"),
            "amount": order.get("amount"),
            "currency": order.get("currency"),
            "key": os.getenv("RAZORPAY_KEY_ID")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ✅ Razorpay Online Order - Verify Signature
@app.post("/verify-payment")
async def verify_payment(verification: PaymentVerification):
    try:
        params_dict = {
            "razorpay_order_id": verification.razorpay_order_id,
            "razorpay_payment_id": verification.razorpay_payment_id,
            "razorpay_signature": verification.razorpay_signature
        }
        await manager.send_order_to_all({"type": "payment_success", **params_dict})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ✅ COD (Cash-on-Delivery) Endpoint
@app.post("/place-cod-order")
async def place_cod_order(order: Order):
    try:
        order_ref = db.reference("orders").push()
        order_ref.set({
            "table": order.table,
            "items": [item.dict() for item in order.items],
            "payment_method": "cash",
            "status": "pending_payment",
            "total_amount": sum(item.price * item.quantity for item in order.items),
            "timestamp": int(time.time() * 1000)
        })

        # ✅ Do NOT send to chef now — wait for admin approval
        return {"status": "success", "order_id": order_ref.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ For existing online flow 
@app.post("/place-order")
async def place_order(order: Order):
    try:
        order_ref = db.reference("orders").push()
        order_ref.set({
            "table": order.table,
            "items": [item.dict() for item in order.items],
            "payment_method": "online",
            "status": "order placed",
            "total_amount": sum(item.price * item.quantity for item in order.items),
            "timestamp": int(time.time() * 1000)
        })

        await manager.send_order_to_all({
            "type": "new_order",
            "orderId": order_ref.key,
            "table": order.table
        })

        return {"status": "success", "order_id": order_ref.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Gemini AI specials
@app.post("/ai/todays-special")
def todays_special(data: dict = Body(...)):
    weather = data.get("weather", "clear")
    temp = data.get("temp", 30)
    try:
        response = get_weather_based_recommendation(weather, temp)
        return { "recommendation": response }
    except Exception as e:
        return { "error": f"AI recommendation error: {str(e)}" }

# ✅ Weather-based suggestions
@app.get("/get-weather")
def get_weather():
    city = "Varanasi"
    weather = "clear"
    temp = 30.0
    try:
        _ = get_weather_based_recommendation(weather, temp)  # Not used by frontend, only triggers AI
        return WeatherInfo(
            city=city,
            temperature_celsius=temp,
            description=weather,
            humidity=60,
            wind_speed_kmph=12.5
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "weather generation failed", "detail": str(e)})

# ✅ WebSocket for Chef
@app.websocket("/ws/chef")
async def websocket_chef(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast({"type": "chef_msg", "message": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ✅ WebSocket for Menu Sync
@app.websocket("/ws/menu")
async def websocket_menu(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
            await manager.broadcast({"type": "menu_update"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/popular-choices-updates")
async def websocket_popular_choices(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
            await manager.broadcast({"type": "popular_update"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

