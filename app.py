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
c.execute('''CREATE TABLE IF NOT EXISTS users 
            (id TEXT PRIMARY KEY, created TIMESTAMP, goals TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS meals 
            (id TEXT PRIMARY KEY, user_id TEXT, timestamp TIMESTAMP, 
             image BLOB, analysis TEXT)''')

# --------------------------
# AI Core Functions
# --------------------------
def clean_and_parse(response_text):
    """Clean and parse Gemini response with error handling"""
    try:
        # Remove markdown code blocks
        cleaned = response_text.replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse AI response: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None

def analyze_food(image):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([
        """Analyze this food image and return JSON with:
        - items: list of {name, quantity, unit, estimated_calories}
        - health_rating: 1-5 scale
        - alternative_suggestions: [healthier alternatives]
        Format: {analysis: {items: [...], ...}}""",
        Image.open(image)
    ])
    return clean_and_parse(response.text)

# --------------------------
# Nutrition Engine
# --------------------------
def get_deep_nutrition(item):
    try:
        response = requests.post(
            "https://trackapi.nutritionix.com/v2/natural/nutrients",
            headers=NUTRITIONIX_HEADERS,
            json={"query": f"{item['quantity']}{item['unit']} {item['name']}"}
        )
        return response.json().get('foods', [{}])[0] if response.ok else {}
    except Exception as e:
        st.error(f"Nutrition API Error: {str(e)}")
        return {}

# --------------------------
# Enhanced UI Components
# --------------------------
def neo_metric(label, value, delta=None):
    st.markdown(f"""
    <div class="neo-card">
        <div class="neo-label">{label}</div>
        <div class="neo-value">{value}</div>
        {f'<div class="neo-delta">{delta}</div>' if delta else ""}
    </div>
    """, unsafe_allow_html=True)

def radar_chart(nutrition):
    df = pd.DataFrame(dict(
        Nutrient=["Calories", "Protein", "Carbs", "Fat", "Fiber"],
        Value=[
            nutrition.get('nf_calories', 0),
            nutrition.get('nf_protein', 0),
            nutrition.get('nf_total_carbohydrate', 0),
            nutrition.get('nf_total_fat', 0),
            nutrition.get('nf_dietary_fiber', 0)
        ]
    ))
    fig = px.line_polar(df, r='Value', theta='Nutrient', line_close=True)
    st.plotly_chart(fig, use_container_width=True)

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
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: #ffffff;
}

.neo-card {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 15px;
    padding: 1.5rem;
    margin: 1rem;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    transition: transform 0.3s ease;
}

.stPlotlyChart {
    border-radius: 15px;
    background: rgba(0,0,0,0.2) !important;
}
</style>
""", unsafe_allow_html=True)

# --------------------------
# User Flow
# --------------------------
with st.sidebar:
    st.title("⚙️ Profile Settings")
    user_id = st.text_input("Unique ID", "user_123")
    goals = st.multiselect("Diet Goals", [
        "Weight Loss", "Muscle Gain", "Ketogenic", 
        "Plant-Based", "Low Sodium"
    ])
    st.session_state.goals = goals

col1, col2 = st.columns([1, 2])

with col1:
    st.title("🥗 Foodie Die Pro")
    uploaded_file = st.file_uploader("", type=["jpg", "png", "jpeg"], 
                                   help="Snap or upload your meal")

with col2:
    if uploaded_file:
        st.image(uploaded_file, use_container_width=True, 
                caption="Your Meal Analysis Preview")
        
        with st.spinner("🧠 Analyzing with Quantum Nutrition AI..."):
            analysis = analyze_food(uploaded_file)
            
            if analysis and 'analysis' in analysis:
                nutrition_data = [get_deep_nutrition(item) 
                                 for item in analysis['analysis'].get('items', [])]
                
                # Save to database
                c.execute('''INSERT INTO meals 
                            (id, user_id, timestamp, image, analysis)
                            VALUES (?, ?, ?, ?, ?)''',
                         (str(datetime.now()), user_id, 
                         datetime.now(), uploaded_file.getvalue(), 
                         json.dumps(analysis)))
                conn.commit()

                # Display Results
                st.success("Analysis Complete!")
                
                # Nutrition Dashboard
                with st.expander("🔍 Detailed Nutrition Breakdown", expanded=True):
                    cols = st.columns(3)
                    cols[0].metric("Health Score", 
                                  f"{analysis['analysis'].get('health_rating', 0)}/5")
                    cols[1].metric("Total Calories", 
                                  sum(item['estimated_calories'] 
                                  for item in analysis['analysis'].get('items', [])))
                    cols[2].metric("Food Groups", 
                                  len(analysis['analysis'].get('items', [])))
                    
                    if nutrition_data:
                        radar_chart(nutrition_data[0])
                
                # Alternative Suggestions
                st.subheader("🌟 Healthier Alternatives")
                for suggestion in analysis['analysis'].get('alternative_suggestions', []):
                    st.markdown(f"- {suggestion}")

