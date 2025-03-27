"""
NUTRISCALE PRO - AI-Powered Nutrition Analysis Platform
"""

import streamlit as st
import google.generativeai as genai
import requests
import sqlite3
import json
import uuid
from datetime import datetime
from PIL import Image
import pandas as pd
import plotly.express as px
import hashlib
import os

# ======================
# Configuration Layer
# ======================
class AppConfig:
    def __init__(self):
        self.gemini_key = st.secrets["GEMINI_API_KEY"]
        self.nutritionix_id = st.secrets["NUTRITIONIX_APP_ID"]
        self.nutritionix_key = st.secrets["NUTRITIONIX_API_KEY"]
        self.db_path = "nutriverse.db"
        self.analytics_enabled = True

config = AppConfig()

# ======================
# Database Layer
# ======================
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(config.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self._init_db()
    
    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    session_token TEXT,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    plan_level INTEGER DEFAULT 0
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    timestamp TIMESTAMP,
                    image_hash TEXT,
                    analysis_json TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
    
    def create_user_session(self):
        user_id = str(uuid.uuid4())
        with self.conn:
            self.conn.execute(
                "INSERT INTO users (id) VALUES (?)",
                (user_id,)
            )
        return user_id
    
    def save_analysis(self, user_id, image, analysis):
        image_hash = hashlib.sha256(image.getvalue()).hexdigest()
        analysis_id = str(uuid.uuid4())
        with self.conn:
            self.conn.execute(
                """INSERT INTO analyses 
                (id, user_id, timestamp, image_hash, analysis_json)
                VALUES (?, ?, ?, ?, ?)""",
                (analysis_id, user_id, datetime.now(), image_hash, json.dumps(analysis))
            )
        return analysis_id

# ======================
# AI Service Layer
# ======================
class NutritionAI:
    def __init__(self):
        genai.configure(api_key=config.gemini_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def analyze_image(self, image):
        try:
            response = self.model.generate_content([
                self._build_prompt(),
                Image.open(image)
            ])
            return self._parse_response(response.text)
        except Exception as e:
            st.error(f"AI Analysis Error: {str(e)}")
            return None
    
    def _build_prompt(self):
        return """Analyze this food image and output JSON with:
        - main_dish: {name, cultural_origin}
        - ingredients: [{name, quantity, unit}]
        - nutrition: {calories, protein, carbs, fat, vitamins}
        - health_metrics: {score (0-100), allergens}
        - sustainability: {carbon_footprint, alternatives}
        """
    
    def _parse_response(self, text):
        cleaned = text.replace('```json', '').replace('```', '').strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            st.error("Failed to parse AI response")
            return None

# ======================
# Nutrition API Layer
# ======================
class NutritionAPI:
    def __init__(self):
        self.headers = {
            "x-app-id": config.nutritionix_id,
            "x-app-key": config.nutritionix_key,
            "Content-Type": "application/json"
        }
    
    def get_detailed_nutrition(self, item):
        try:
            response = requests.post(
                "https://trackapi.nutritionix.com/v2/natural/nutrients",
                headers=self.headers,
                json={"query": f"{item['quantity']}{item['unit']} {item['name']}"}
            )
            return response.json().get('foods', [{}])[0] if response.ok else {}
        except Exception as e:
            st.error(f"Nutrition API Error: {str(e)}")
            return {}

# ======================
# Presentation Layer
# ======================
class NutritionDashboard:
    def __init__(self):
        self._load_assets()
    
    def _load_assets(self):
        st.markdown("""
        <style>
        .main {
            background: #f8fafc;
        }
        .food-card {
            border-radius: 15px;
            padding: 2rem;
            background: white;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            margin: 1rem 0;
        }
        .metric-badge {
            padding: 1rem;
            border-radius: 8px;
            background: #f1f5f9;
            text-align: center;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def show_analysis(self, analysis, nutrition_data):
        with st.container():
            # Header Section
            st.subheader(f"🍴 {analysis.get('main_dish', {}).get('name', 'Unknown Dish')}")
            st.caption(f"Cuisine: {analysis.get('main_dish', {}).get('cultural_origin', '')}")
            
            # Health Metrics
            cols = st.columns(3)
            health_score = analysis.get('health_metrics', {}).get('score', 0)
            cols[0].metric("Health Score", f"{health_score}/100")
            cols[1].metric("Calories", sum(item.get('nf_calories', 0) for item in nutrition_data))
            cols[2].metric("Allergens", ", ".join(analysis.get('health_metrics', {}).get('allergens', [])) or "None")
            
            # Nutrition Visualization
            with st.expander("📊 Detailed Nutrition Analysis", expanded=True):
                tab1, tab2 = st.tabs(["Macronutrients", "Micronutrients"])
                
                with tab1:
                    self._show_macros(nutrition_data)
                
                with tab2:
                    self._show_micros(nutrition_data)
            
            # Sustainability
            with st.container():
                st.subheader("🌱 Sustainability Impact")
                sustainability = analysis.get('sustainability', {})
                cols = st.columns(2)
                cols[0].metric("Carbon Footprint", f"{sustainability.get('carbon_footprint', 0)}g CO2")
                cols[1].metric("Eco Alternatives", len(sustainability.get('alternatives', [])))
                
                if sustainability.get('alternatives'):
                    st.write("**Sustainable Swaps:**")
                    for alt in sustainability['alternatives']:
                        st.write(f"- {alt}")
    
    def _show_macros(self, data):
        df = pd.DataFrame({
            'Macro': ['Protein', 'Carbs', 'Fat'],
            'Grams': [
                sum(item.get('nf_protein', 0) for item in data),
                sum(item.get('nf_total_carbohydrate', 0) for item in data),
                sum(item.get('nf_total_fat', 0) for item in data)
            ]
        })
        fig = px.pie(df, values='Grams', names='Macro', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    
    def _show_micros(self, data):
        micros = {
            'Calcium': sum(item.get('nf_calcium_dv', 0) for item in data),
            'Iron': sum(item.get('nf_iron_dv', 0) for item in data),
            'Potassium': sum(item.get('nf_potassium', 0) for item in data),
            'Vitamin C': sum(item.get('nf_vitamin_c_dv', 0) for item in data)
        }
        st.bar_chart(micros)

# ======================
# Application Core
# ======================
def main():
    # Initialize services
    db = DatabaseManager()
    ai = NutritionAI()
    nutrition_api = NutritionAPI()
    ui = NutritionDashboard()
    
    # User Session Management
    if 'user_id' not in st.session_state:
        st.session_state.user_id = db.create_user_session()
    
    # App Interface
    st.set_page_config(
        page_title="Nutriverse Pro",
        page_icon="🥗",
        layout="wide"
    )
    
    st.title("🍎 Nutriverse - AI Nutrition Analyst")
    uploaded_file = st.file_uploader("Upload Food Image", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.image(uploaded_file, use_container_width=True)
        
        with col2:
            with st.spinner("🔍 Analyzing nutritional composition..."):
                # AI Analysis
                analysis = ai.analyze_image(uploaded_file)
                
                if analysis:
                    # Nutrition API Data
                    nutrition_data = [
                        nutrition_api.get_detailed_nutrition(item)
                        for item in analysis.get('ingredients', [])
                    ]
                    
                    # Save to Database
                    db.save_analysis(
                        st.session_state.user_id,
                        uploaded_file,
                        analysis
                    )
                    
                    # Display Results
                    ui.show_analysis(analysis, nutrition_data)

if __name__ == "__main__":
    main()
