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
conn = sqlite3.connect('foodie_die.db', detect_types=sqlite3.PARSE_DECLTYPES)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS meals 
            (id TEXT PRIMARY KEY, 
             timestamp TIMESTAMP,
             image BLOB, 
             analysis TEXT)''')

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
# UI Components
# --------------------------
def clinical_card(title, content=None):
    return st.markdown(f"""
    <div class="clinical-card">
        <div class="clinical-card-header">{title}</div>
        <div class="clinical-card-content">{content or ""}</div>
    </div>
    """, unsafe_allow_html=True)

def metric_badge(label, value, unit=""):
    return st.markdown(f"""
    <div class="metric-badge">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}{unit}</div>
    </div>
    """, unsafe_allow_html=True)

# --------------------------
# Main Interface
# --------------------------
st.set_page_config(
    page_title="NutriScan Pro",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clinical CSS
st.markdown("""
<style>
:root {
    --primary: #2A5C82;
    --secondary: #5BA4E6;
    --accent: #FF6B6B;
    --background: #F8FAFC;
}

[data-testid="stAppViewContainer"] {
    background: var(--background);
    font-family: 'Inter', sans-serif;
}

.clinical-card {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    margin: 1rem 0;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    border: 1px solid #E5E7EB;
}

.clinical-card-header {
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--primary);
    margin-bottom: 1.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--secondary);
}

.metric-badge {
    background: white;
    border-radius: 8px;
    padding: 1.2rem;
    margin: 0.5rem;
    border: 1px solid #E5E7EB;
    text-align: center;
}

.metric-label {
    font-size: 0.9rem;
    color: #6B7280;
    margin-bottom: 0.5rem;
}

.metric-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--primary);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 1rem;
}

.stTabs [data-baseweb="tab"] {
    padding: 0.5rem 1.5rem;
    border-radius: 8px;
    background: white !important;
    border: 1px solid #E5E7EB !important;
}

.stTabs [aria-selected="true"] {
    background: var(--secondary) !important;
    color: white !important;
    border-color: var(--secondary) !important;
}

.analysis-progress {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 2rem;
    background: white;
    border-radius: 12px;
    margin: 2rem 0;
}

.progress-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #E5E7EB;
    border-top-color: var(--secondary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
</style>
""", unsafe_allow_html=True)

# --------------------------
# App Flow
# --------------------------
st.title("🩺 NutriScan Pro")
st.caption("Clinical-Grade Nutrition Analysis")

uploaded_file = st.file_uploader("Upload Food Image", type=["jpg", "png", "jpeg"])

if uploaded_file:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        clinical_card("Food Image Preview", st.image(uploaded_file, use_container_width=True))

    with col2:
        with st.container():
            st.markdown("""
            <div class="analysis-progress">
                <div class="progress-spinner"></div>
                <div style="font-weight: 500; color: var(--primary);">Analyzing nutritional composition...</div>
            </div>
            """, unsafe_allow_html=True)
            
            analysis = analyze_food(uploaded_file)
            
            if analysis and 'analysis' in analysis:
                # Save analysis
                timestamp = datetime.now().isoformat()
                c.execute('''INSERT INTO meals 
                          (id, timestamp, image, analysis)
                          VALUES (?, ?, ?, ?)''',
                        (str(timestamp), timestamp,
                         uploaded_file.getvalue(), json.dumps(analysis)))
                conn.commit()

                # Get nutrition data
                nutrition_data = [get_nutrition_data(item) 
                                for item in analysis['analysis'].get('items', [])]

                # Main Results
                with clinical_card("Meal Analysis"):
                    cols = st.columns(3)
                    with cols[0]:
                        metric_badge("Main Food", analysis['analysis'].get('main_food', 'Unknown'))
                    with cols[1]:
                        metric_badge("Health Score", f"{analysis['analysis'].get('health_rating', 0)}/5")
                    with cols[2]:
                        metric_badge("Components", len(analysis['analysis'].get('items', [])))

                # Nutrition Tabs
                tab1, tab2 = st.tabs(["Macronutrients", "Micronutrients"])
                
                with tab1:
                    with clinical_card("Macronutrient Breakdown"):
                        cols = st.columns(3)
                        cols[0].metric("Protein", f"{sum(item.get('nf_protein', 0) for item in nutrition_data)}g")
                        cols[1].metric("Carbohydrates", f"{sum(item.get('nf_total_carbohydrate', 0) for item in nutrition_data)}g")
                        cols[2].metric("Fats", f"{sum(item.get('nf_total_fat', 0) for item in nutrition_data)}g")
                        
                        fig = px.pie(
                            values=[
                                sum(item.get('nf_protein', 0) for item in nutrition_data),
                                sum(item.get('nf_total_carbohydrate', 0) for item in nutrition_data),
                                sum(item.get('nf_total_fat', 0) for item in nutrition_data)
                            ],
                            names=['Protein', 'Carbs', 'Fats'],
                            color_discrete_sequence=['#2A5C82', '#5BA4E6', '#FF6B6B']
                        )
                        st.plotly_chart(fig, use_container_width=True)

                with tab2:
                    with clinical_card("Micronutrient Analysis"):
                        grid = st.columns(4)
                        nutrients = [
                            ('Calcium', 'nf_calcium_dv', '%'),
                            ('Iron', 'nf_iron_dv', '%'),
                            ('Potassium', 'nf_potassium', 'mg'),
                            ('Vitamin C', 'nf_vitamin_c_dv', '%')
                        ]
                        for idx, (name, key, unit) in enumerate(nutrients):
                            with grid[idx % 4]:
                                metric_badge(name, 
                                           sum(item.get(key, 0) for item in nutrition_data),
                                           unit)

                # Recommendations
                with clinical_card("Clinical Recommendations"):
                    st.subheader("Healthier Alternatives")
                    cols = st.columns(2)
                    for idx, suggestion in enumerate(analysis['analysis'].get('alternative_suggestions', [])):
                        with cols[idx % 2]:
                            st.markdown(f"""
                            <div class="clinical-suggestion">
                                <div style="color: var(--primary); margin-bottom: 0.5rem;">✓ {suggestion}</div>
                            </div>
                            """, unsafe_allow_html=True)

# Close database connection
conn.close()
