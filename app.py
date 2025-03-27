import streamlit as st
import google.generativeai as genai
from PIL import Image
import requests

# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def analyze_food(image):
    model = genai.GenerativeModel('gemini-pro-vision')
    response = model.generate_content([
        "Identify food items and estimate quantities in this image. Return as: {items: [{name, quantity, unit}]}",
        Image.open(image)
    ])
    return response.text

def get_nutrition(items):
    nutrition = []
    for item in items:
        response = requests.post(
            "https://api.edamam.com/api/nutrition-data",
            params={
                "app_id": st.secrets["EDAMAM_APP_ID"],
                "app_key": st.secrets["EDAMAM_APP_KEY"],
                "ingr": f"{item['quantity']} {item['unit']} {item['name']}"
            }
        )
        nutrition.append(response.json())
    return nutrition

# Streamlit UI
st.title("🍎 Foodie Die - AI Nutrition Analyzer")
upload = st.file_uploader("Upload Food Photo", type=["jpg", "png", "jpeg"])

if upload:
    st.image(upload, width=300)
    with st.spinner("Analyzing..."):
        food_data = analyze_food(upload)
        nutrition = get_nutrition(eval(food_data)["items"])
    
    st.subheader("Nutrition Facts")
    st.json(nutrition)