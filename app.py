import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
import plotly.express as px
from PIL import Image
from datetime import datetime
import sqlite3
import json
from streamlit_extras.colored_header import colored_header
from streamlit_extras.stylable_container import stylable_container

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
    """Clean and parse Gemini response"""
    try:
        cleaned = response_text.replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned)
    except Exception as e:
        st.error(f"Parsing error: {str(e)}")
        return None

def analyze_food(image):
    """Analyze food image using Gemini"""
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
    """Get detailed nutrition from Nutritionix"""
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
def nutrient_card(label, value, unit="", dv=0, color="#FF4B4B"):
    """Styled nutrient display card"""
    with stylable_container(
        key=f"nutrient_{label}",
        css_styles=f"""
            {{
                background: {color}22;
                border-radius: 10px;
                padding: 1rem;
                margin: 0.5rem;
                border-left: 4px solid {color};
            }}
        """
    ):
        st.markdown(f"""
        <div style="padding: 0.5rem;">
            <div style="font-size: 0.8rem; color: {color};">
                {label.upper()}
            </div>
            <div style="font-size: 1.5rem; font-weight: bold;">
                {value}{unit}
            </div>
            {f'<div style="font-size: 0.75rem; color: #666;">{dv}% DV</div>' if dv else ""}
        </div>
        """, unsafe_allow_html=True)

def create_macronutrient_chart(data):
    """Interactive macronutrient chart"""
    df = pd.DataFrame({
        'Macro': ['Protein', 'Carbs', 'Fat'],
        'Value': [
            data.get('nf_protein', 0),
            data.get('nf_total_carbohydrate', 0),
            data.get('nf_total_fat', 0)
        ]
    })
    fig = px.bar(df, x='Macro', y='Value', color='Macro',
                 color_discrete_sequence=['#00CC96', '#FFA15A', '#EF553B'])
    fig.update_layout(showlegend=False)
    return fig

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

.food-header {
    font-size: 2.5rem !important;
    color: #2c3e50 !important;
    margin-bottom: 1rem !important;
}

.nutrition-grid {
    background: white;
    border-radius: 15px;
    padding: 2rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
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
        st.image(uploaded_file, use_container_width=True, caption="Uploaded Image")

    with col2:
        with st.spinner("🔍 Analyzing your meal..."):
            analysis = analyze_food(uploaded_file)
            if analysis and 'analysis' in analysis:
                main_food = analysis['analysis'].get('main_food', 'Unknown Food')
                colored_header(
                    label=f"Detected Food: {main_food}",
                    description="",
                    color_name="blue-70"
                )
                
                # Save analysis to database
                c.execute('''INSERT INTO meals 
                          (id, timestamp, image, analysis)
                          VALUES (?, ?, ?, ?)''',
                        (str(datetime.now()), datetime.now(),
                         uploaded_file.getvalue(), json.dumps(analysis)))
                conn.commit()

                # Get nutrition data
                nutrition_data = [get_nutrition_data(item) 
                                for item in analysis['analysis'].get('items', [])]

                # Main Nutrition Dashboard
                with st.container():
                    st.subheader("📊 Nutritional Breakdown")
                    
                    # Macronutrient Row
                    cols = st.columns(3)
                    cols[0].metric("Calories", 
                                  f"{sum(item.get('nf_calories', 0) for item in nutrition_data)} kcal")
                    cols[1].metric("Protein", 
                                  f"{sum(item.get('nf_protein', 0) for item in nutrition_data)}g")
                    cols[2].metric("Carbs", 
                                  f"{sum(item.get('nf_total_carbohydrate', 0) for item in nutrition_data)}g")

                    # Detailed Nutrition Tabs
                    tab1, tab2, tab3 = st.tabs(["Macronutrients", "Micronutrients", "Health Insights"])
                    
                    with tab1:
                        st.plotly_chart(create_macronutrient_chart(nutrition_data[0]), 
                                      use_container_width=True)
                        
                    with tab2:
                        st.subheader("Vitamins & Minerals")
                        grid = st.columns(4)
                        micronutrients = [
                            ('Calcium', 'nf_calcium_dv', '%', '#00CC96'),
                            ('Iron', 'nf_iron_dv', '%', '#EF553B'),
                            ('Potassium', 'nf_potassium', 'mg', '#AB63FA'),
                            ('Vitamin C', 'nf_vitamin_c_dv', '%', '#19D3F3')
                        ]
                        for idx, (name, key, unit, color) in enumerate(micronutrients):
                            with grid[idx % 4]:
                                nutrient_card(name, 
                                            nutrition_data[0].get(key, 0), 
                                            unit, color=color)
                    
                    with tab3:
                        st.subheader("🥦 Health Recommendations")
                        st.write(f"**Health Rating:** {analysis['analysis'].get('health_rating', 0)}/5")
                        
                        st.subheader("🌟 Healthier Alternatives")
                        for suggestion in analysis['analysis'].get('alternative_suggestions', []):
                            st.markdown(f"- {suggestion}")



