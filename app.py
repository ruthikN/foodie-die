import streamlit as st
import google.generativeai as genai
from PIL import Image
import requests

# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def analyze_food(image):
    model = genai.GenerativeModel('gemini-1.0-pro-vision-latest')
    response = model.generate_content([
        "Identify food items and estimate quantities in this image. Return as: {items: [{name, quantity, unit}]}",
        Image.open(image)
    ])
    return response.text

def get_nutrition(items):
    nutrition = []
    for item in items:
        response = requests.post(
            "https://trackapi.nutritionix.com/v2/natural/nutrients",
            headers={
                "x-app-id": st.secrets["NUTRITIONIX_APP_ID"],
                "x-app-key": st.secrets["NUTRITIONIX_API_KEY"],
                "Content-Type": "application/json"
            },
            json={
                "query": f"{item['quantity']}{item['unit']} {item['name']}"
            }
        )
        if response.status_code == 200:
            nutrition.append(response.json()['foods'][0])
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
    for item in nutrition:
        st.write(f"### {item['food_name']}")
        st.metric("Calories", f"{item['nf_calories']} kcal")
        st.write(f"Protein: {item['nf_protein']}g | Carbs: {item['nf_total_carbohydrate']}g | Fat: {item['nf_total_fat']}g")
