import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ✅ Use Gemini 1.5 Flash model
model = genai.GenerativeModel("models/gemini-1.5-flash")

def get_ai_special(recent_dishes, sales_stats):
    prompt = f"""
    Analyze the following data and recommend a creative and appealing 'Today's Special' for our restaurant.

    Recent Popular Dishes: {recent_dishes}
    Current Sales Stats: {sales_stats}

    Suggest 1–2 dish names and a short description in a friendly, catchy tone.
    """
    response = model.generate_content(prompt)
    return response.text

def get_weather_based_recommendation(weather: str, temp: float):
    try:
        menu_ref = db.reference('menu')
        menu_data = menu_ref.get()

        if not menu_data:
            return "Today's chef specials look delicious!"

        all_items = []
        for category in menu_data.values():
            for item in category.values():
                name = item.get('name')
                if name:
                    all_items.append(name)

        if not all_items:
            return "Try our signature dishes today!"

        prompt = f"""
        The weather today is '{weather}' with temperature around {temp}°C.
        Here is the full menu: {all_items}

        Suggest 2 food or drink items from this menu that would be ideal for this weather.
        Give the response in a short, casual restaurant tone.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"AI recommendation error: {e}")
        return "Our chef's specials are perfect for any weather!"
