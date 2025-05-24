from pydantic import BaseModel
from typing import List, Optional

class CartItem(BaseModel):
    name: str
    price: float
    image: str
    quantity: int

class Order(BaseModel):
    table: int
    items: List[CartItem]
    payment_method: str = 'ONLINE'   # default हो सकता है 'ONLINE' या 'COD'
    user: Optional[str] = None       # ✅ user field added for filtering orders

class WeatherInfo(BaseModel):
    city: str
    temperature_celsius: float
    description: str
    humidity: Optional[int]
    wind_speed_kmph: Optional[float]
