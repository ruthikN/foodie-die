import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
import plotly.express as px
from PIL import Image
from datetime import datetime
import sqlite3
import json

# --------------------------
# Configuration
# --------------------------
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
NUTRITIONIX_HEADERS = {
    "x-app-id": st.secrets["NUTRITIONIX_APP_ID"],
    "x-app-key": st.secrets["NUTRITIONIX_API_KEY"],
    "Content-Type": "application/json"
}

# --------------------------
# Database Setup
# --------------------------
conn = sqlite3.connect('foodie_die.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS meals 
            (id TEXT PRIMARY KEY, timestamp TIMESTAMP, 
             image BLOB, analysis TEXT)''')

# --------------------------
# Core Functions
# --------------------------
def clean_and_parse(response_text):
    try:
        cleaned = response_text.replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned)
    except Exception as e:
        st.error(f"Parsing error: {str(e)}")
        return None

def analyze_food(image):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """Analyze this food image and return JSON with:
    - main_food: primary food name
    - items: list of {name, quantity, unit}
    - health_rating: 1-5 scale
    - alternative_suggestions: [healthier options]
    Format: {analysis: {...}}"""
    
    try:
        response = model.generate_content([prompt, Image.open(image)])
        return clean_and_parse(response.text)
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        return None

def get_nutrition_data(item):
    try:
        response = requests.post(
            "https://trackapi.nutritionix.com/v2/natural/nutrients",
            headers=NUTRITIONIX_HEADERS,
            json={"query": f"{item['quantity']}{item['unit']} {item['name']}"}
        )
        return response.json().get('foods', [{}])[0] if response.ok else {}
    except Exception as e:
        st.error(f"Nutrition API error: {str(e)}")
        return {}

# --------------------------
# Custom Styled Components
# --------------------------
def styled_container():
    return st.container(
        border=True,
        border_color="#e0e0e0",
        padding=20,
        margin=10
    )

def nutrient_card(label, value, unit=""):
    with st.container():
        st.markdown(f"""
        <div style="
            padding: 1rem;
            border-radius: 10px;
            background: #ffffff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 0.5rem 0;
        ">
            <div style="font-size: 0.9rem; color: #666;">
                {label}
            </div>
            <div style="font-size: 1.5rem; font-weight: bold; color: #2c3e50;">
                {value}{unit}
            </div>
        </div>
        """, unsafe_allow_html=True)

# --------------------------
# Main Interface
# --------------------------
st.set_page_config(
    page_title="Foodie Die Pro",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: #f8f9fa;
}

.st-emotion-cache-1kyxreq {
    justify-content: center;
}

.st-emotion-cache-1v0mbdj {
    border-radius: 15px;
}
</style>
""", unsafe_allow_html=True)

# --------------------------
# App Flow
# --------------------------
st.title("🍎 Foodie Die Pro - AI Nutrition Analyzer")
uploaded_file = st.file_uploader("Upload Food Image", type=["jpg", "png", "jpeg"])

if uploaded_file:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.image(uploaded_file, use_container_width=True)

    with col2:
        with st.spinner("🔍 Analyzing your meal..."):
            analysis = analyze_food(uploaded_file)
            if analysis and 'analysis' in analysis:
                # Save analysis
                c.execute('''INSERT INTO meals 
                          (id, timestamp, image, analysis)
                          VALUES (?, ?, ?, ?)''',
                        (str(datetime.now()), datetime.now(),
                         uploaded_file.getvalue(), json.dumps(analysis)))
                conn.commit()

                # Get nutrition data
                nutrition_data = [get_nutrition_data(item) 
                                for item in analysis['analysis'].get('items', [])]

                # Display Results
                with styled_container():
                    st.subheader(f"🍴 {analysis['analysis'].get('main_food', 'Unknown Food')}")
                    
                    cols = st.columns(3)
                    cols[0].metric("Health Score", 
                                  f"{analysis['analysis'].get('health_rating', 0)}/5")
                    cols[1].metric("Total Calories", 
                                  sum(item.get('nf_calories', 0) for item in nutrition_data))
                    cols[2].metric("Food Components", 
                                  len(analysis['analysis'].get('items', [])))

                # Nutrition Breakdown
                with styled_container():
                    st.subheader("📊 Nutritional Breakdown")
                    tab1, tab2 = st.tabs(["Macronutrients", "Micronutrients"])
                    
                    with tab1:
                        cols = st.columns(3)
                        cols[0].metric("Protein", f"{sum(item.get('nf_protein', 0) for item in nutrition_data)}g")
                        cols[1].metric("Carbs", f"{sum(item.get('nf_total_carbohydrate', 0) for item in nutrition_data)}g")
                        cols[2].metric("Fat", f"{sum(item.get('nf_total_fat', 0) for item in nutrition_data)}g")
                    
                    with tab2:
                        grid = st.columns(4)
                        nutrients = [
                            ('Calcium', 'nf_calcium_dv', '%'),
                            ('Iron', 'nf_iron_dv', '%'),
                            ('Potassium', 'nf_potassium', 'mg'),
                            ('Vitamin C', 'nf_vitamin_c_dv', '%')
                        ]
                        for idx, (name, key, unit) in enumerate(nutrients):
                            with grid[idx % 4]:
                                nutrient_card(name, 
                                             sum(item.get(key, 0) for item in nutrition_data),
                                             unit)

                # Recommendations
                with styled_container():
                    st.subheader("🌟 Healthier Alternatives")
                    for suggestion in analysis['analysis'].get('alternative_suggestions', []):
                        st.markdown(f"- {suggestion}")

