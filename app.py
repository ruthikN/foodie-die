import streamlit as st
import google.generativeai as genai
from PIL import Image
import requests
import json  # Add this import

# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def analyze_food(image):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([
        """Identify food items and estimate quantities in this image. 
        Return valid JSON format only: 
        {"items": [{"name": "item1", "quantity": number, "unit": "unit1"}, ...]}""",
        Image.open(image)
    ])
    
    # Clean response text
    response_text = response.text.replace('```json', '').replace('```', '').strip()
    
    try:
        return json.loads(response_text)  # Use json instead of eval
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse response: {e}\nResponse was: {response_text}")
        return None

def get_nutrition(items):
    if not items:
        return []
    
    nutrition = []
    for item in items:
        try:
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
        except Exception as e:
            st.error(f"Error getting nutrition for {item['name']}: {str(e)}")
    
    return nutrition

# Streamlit UI
st.title("🍎 Foodie Die - AI Nutrition Analyzer")
upload = st.file_uploader("Upload Food Photo", type=["jpg", "png", "jpeg"])

if upload:
    st.image(upload, width=300)
    with st.spinner("Analyzing..."):
        food_data = analyze_food(upload)
        
        if food_data and "items" in food_data:
            nutrition = get_nutrition(food_data["items"])
            
            st.subheader("Nutrition Facts")
            if nutrition:
                for item in nutrition:
                    st.write(f"### {item['food_name']}")
                    st.metric("Calories", f"{item['nf_calories']} kcal")
                    st.write(f"Protein: {item['nf_protein']}g | Carbs: {item['nf_total_carbohydrate']}g | Fat: {item['nf_total_fat']}g")
            else:
                st.warning("No nutrition data found")
        else:
            st.error("Failed to analyze food items")
