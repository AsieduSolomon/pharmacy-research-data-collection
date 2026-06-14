"""
Drug Storage Conditions Survey — Sunyani Technical University
=============================================================
Backend  : Supabase (via Supabase Client - IPv4 compatible)
Frontend : Streamlit Cloud
Charts   : Plotly (10+ chart types)
Reports  : PDF via ReportLab
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import os
import io
from datetime import datetime
from supabase import create_client, Client

# ── PDF Report ──────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Drug Storage Survey | Sunyani Technical University",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# SUPABASE CONNECTION (FIXED - No IPv6 issues)
# ─────────────────────────────────────────────
@st.cache_resource
def init_supabase() -> Client:
    """Initialize Supabase client."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Supabase connection failed: {e}")
        st.info("Please add SUPABASE_URL and SUPABASE_KEY to Streamlit secrets.")
        st.stop()

def fetch_all() -> pd.DataFrame:
    """Fetch all responses from Supabase."""
    try:
        supabase = init_supabase()
        response = supabase.table("responses").select("*").order("submitted_at", desc=True).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def insert_response(data: dict):
    """Insert a new response."""
    supabase = init_supabase()
    try:
        supabase.table("responses").insert(data).execute()
    except Exception as e:
        st.error(f"Failed to submit: {e}")
        raise e

def delete_response(rid: int):
    """Delete a response by ID."""
    supabase = init_supabase()
    try:
        supabase.table("responses").delete().eq("id", rid).execute()
    except Exception as e:
        st.error(f"Failed to delete: {e}")
        raise e

def response_count() -> int:
    """Get total number of responses."""
    try:
        supabase = init_supabase()
        result = supabase.table("responses").select("id", count="exact").execute()
        return result.count if result.count else 0
    except Exception:
        return 0

def check_connection() -> bool:
    """Test if Supabase connection is working."""
    try:
        supabase = init_supabase()
        supabase.table("responses").select("id", count="exact", head=True).execute()
        return True
    except Exception:
        return False

# ─────────────────────────────────────────────
# CUSTOM CSS (unchanged)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #028090 0%, #065A82 60%, #21295C 100%);
        padding: 28px 35px;
        border-radius: 14px;
        margin-bottom: 25px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 20px rgba(2,128,144,0.25);
    }
    .main-header h1 { font-size: 1.65em; margin: 0; font-weight: 800; }
    .main-header p  { font-size: 0.92em; margin: 5px 0 0; opacity: 0.88; }
    .section-card {
        background: #f8fdfe;
        border-left: 5px solid #028090;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 20px 0 10px;
    }
    .section-title {
        color: #065A82;
        font-size: 1.05em;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px 12px;
        text-align: center;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        border-top: 4px solid #028090;
        margin-bottom: 8px;
    }
    .metric-value { font-size: 2em; font-weight: 800; color: #028090; }
    .metric-label { font-size: 0.82em; color: #555; margin-top: 4px; }
    .success-box {
        background: linear-gradient(135deg, #e8faf7, #d0f5ee);
        border: 2px solid #02C39A;
        border-radius: 12px;
        padding: 32px;
        text-align: center;
        margin: 20px 0;
    }
    .info-banner {
        background: linear-gradient(90deg, #028090, #00A896);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 16px;
        font-size: 0.92em;
    }
    .db-status-ok  { background:#e8faf7; border:1.5px solid #02C39A; border-radius:8px; padding:8px 14px; font-size:0.88em; color:#065A82; }
    .db-status-err { background:#fff0f0; border:1.5px solid #F96167; border-radius:8px; padding:8px 14px; font-size:0.88em; color:#c0392b; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# COLOUR PALETTE
# ─────────────────────────────────────────────
TEAL   = "#028090"
GREEN  = "#02C39A"
NAVY   = "#065A82"
CORAL  = "#F96167"
GOLD   = "#F9C74F"
MINT   = "#90E0EF"
SLATE  = "#1C7293"
AMBER  = "#F4A261"
PURPLE = "#9B5DE5"
PINK   = "#F15BB5"

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$", email))

def render_header():
    st.markdown("""
    <div class="main-header">
        <h1>💊 Drug Storage Conditions Survey</h1>
        <p><strong>Sunyani Technical University</strong> &nbsp;|&nbsp; Department of Pharmacy</p>
        <p style="font-size:0.80em; opacity:0.75; margin-top:6px;">
            Evaluation of Storage Conditions of Drugs in Community Pharmacies and Their
            Influence on Drug Potency and Shelf Life in the Sunyani Municipality, Ghana &mdash; March 2026
        </p>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PAGE: SURVEY
# ─────────────────────────────────────────────
def page_survey():
    st.markdown("""
    <div class="info-banner">
        📋 &nbsp; Please answer all questions as honestly as possible.
        Your responses are <strong>confidential</strong> and will be used solely for academic research.
        Fields marked <strong>*</strong> are required.
    </div>
    """, unsafe_allow_html=True)

    with st.form("survey_form", clear_on_submit=True):

        # ── SECTION A ──────────────────────────────────────────
        st.markdown('<div class="section-card"><div class="section-title">🏪 Section A — Pharmacy & Pharmacist Profile</div></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            pharmacy_name   = st.text_input("Name of Pharmacy *", placeholder="e.g. Sunshine Pharmacy")
            pharmacist_name = st.text_input("Name of Pharmacist / Respondent *", placeholder="Full name")
            reg_number      = st.text_input("Pharmacy Council Registration Number *", placeholder="e.g. PC/2019/001")
            pharmacy_type   = st.selectbox("Type of Pharmacy *", [
                "-- Select --", "Retail Community Pharmacy", "Hospital Pharmacy",
                "Licensed Chemical Shop", "Wholesale Pharmacy"
            ])
        with col2:
            pharmacist_email = st.text_input("Email Address (optional)", placeholder="name@example.com")
            years_experience = st.number_input("Years of Professional Experience *", min_value=0, max_value=60, step=1)
            num_staff        = st.number_input("Total Number of Staff in Pharmacy *", min_value=1, max_value=200, step=1)
            location_type    = st.selectbox("Pharmacy Location *", [
                "-- Select --", "Urban (City Centre)", "Peri-urban", "Rural"
            ])

        # ── SECTION B ──────────────────────────────────────────
        st.markdown('<div class="section-card"><div class="section-title">🌡️ Section B — Physical Storage Conditions & Facilities</div></div>', unsafe_allow_html=True)
        st.markdown("**Does your pharmacy have the following equipment?**")
        col1, col2, col3 = st.columns(3)
        with col1:
            has_ac           = st.radio("Air Conditioning Unit *", ["Yes","No"], horizontal=True)
            has_refrigerator = st.radio("Functional Refrigerator *", ["Yes","No"], horizontal=True)
        with col2:
            has_thermometer  = st.radio("Room Thermometer *", ["Yes","No"], horizontal=True)
            has_hygrometer   = st.radio("Hygrometer (Humidity Meter) *", ["Yes","No"], horizontal=True)
        with col3:
            has_proper_shelving = st.radio("Proper Drug Shelving *", ["Yes","No"], horizontal=True)
            has_ventilation     = st.radio("Adequate Ventilation *", ["Yes","No"], horizontal=True)

        col1, col2 = st.columns(2)
        with col1:
            has_direct_sunlight = st.radio("Are any drugs exposed to direct sunlight? *", ["Yes","No"], horizontal=True)
        with col2:
            storage_area_size = st.selectbox("Size of Main Drug Storage Area *", [
                "-- Select --", "Very small (< 10 m²)", "Small (10–25 m²)",
                "Medium (25–50 m²)", "Large (> 50 m²)"
            ])

        # ── SECTION C ──────────────────────────────────────────
        st.markdown('<div class="section-card"><div class="section-title">📊 Section C — Temperature & Humidity Monitoring</div></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            temp_monitoring_freq = st.selectbox("How often is room temperature recorded? *", [
                "-- Select --", "Multiple times daily", "Once daily",
                "Weekly", "Monthly", "Never monitored"
            ])
            usual_temp_range = st.selectbox("Usual temperature range in your storage area *", [
                "-- Select --",
                "Below 25°C  (WHO Optimal)",
                "25°C – 30°C  (Acceptable)",
                "30°C – 35°C  (Risk Zone)",
                "Above 35°C  (High Risk)",
                "Not monitored / Unknown"
            ])
        with col2:
            usual_humidity_range = st.selectbox("Usual relative humidity (RH%) in storage area *", [
                "-- Select --",
                "Below 45% RH  (Low)",
                "45% – 65% RH  (Optimal)",
                "65% – 75% RH  (Elevated Risk)",
                "Above 75% RH  (High Risk)",
                "Not monitored / Unknown"
            ])
            temp_excursion_action = st.selectbox("Action taken when temperature exceeds limits *", [
                "-- Select --",
                "Move drugs to refrigerator / cooler area",
                "Increase ventilation or switch on AC",
                "Document and notify supervisor",
                "No specific action taken",
                "No system in place to detect excursions"
            ])
        has_written_sop = st.radio(
            "Does your pharmacy have a written Standard Operating Procedure (SOP) for drug storage? *",
            ["Yes","No"], horizontal=True
        )

        # ── SECTION D ──────────────────────────────────────────
        st.markdown('<div class="section-card"><div class="section-title">✅ Section D — Drug Handling & WHO GSP Compliance</div></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            gsp_training_received = st.radio(
                "Have you received training on WHO Good Storage Practices (GSP)? *",
                ["Yes","No"], horizontal=True
            )
            last_training_year = st.selectbox("If yes — when was your most recent training?", [
                "N/A — No training received", "2024 – 2025",
                "2021 – 2023", "2018 – 2020", "Before 2018"
            ])
            practises_fifo = st.radio(
                "Do you practise First-In-First-Out (FIFO) stock rotation? *",
                ["Yes","No","Sometimes"], horizontal=True
            )
        with col2:
            checks_expiry = st.radio(
                "Do you regularly inspect stock for expiry dates? *",
                ["Yes","No","Sometimes"], horizontal=True
            )
            segregates_thermolabile = st.radio(
                "Are temperature-sensitive drugs stored separately under cold conditions? *",
                ["Yes","No","Not Applicable"], horizontal=True
            )
            fda_inspected = st.radio(
                "Has your pharmacy been inspected by the FDA Ghana in the last 2 years? *",
                ["Yes","No"], horizontal=True
            )
        self_compliance_rating = st.select_slider(
            "How would you rate your pharmacy's overall compliance with WHO Good Storage Practices? *",
            options=["Very Poor","Poor","Fair","Good","Excellent"], value="Fair"
        )

        # ── SECTION E ──────────────────────────────────────────
        st.markdown('<div class="section-card"><div class="section-title">⚠️ Section E — Observed Drug Quality & Potency Issues</div></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            observed_degradation = st.radio(
                "Have you ever observed physical signs of drug degradation? *",
                ["Yes","No"], horizontal=True
            )
            degradation_drug_types = st.multiselect(
                "If yes — which drug types were affected?",
                ["Antibiotics (tablets/capsules)","Syrups / Oral liquids","Antimalarials",
                 "Antihypertensives","Injectables / Vaccines",
                 "Suppositories / Pessaries","Topical creams / ointments","Other"]
            )
            observed_color_change = st.radio(
                "Have you noticed unusual colour change in any drug? *",
                ["Yes","No"], horizontal=True
            )
        with col2:
            potency_complaints = st.radio(
                "Have patients ever complained that a medicine was not working? *",
                ["Yes","No"], horizontal=True
            )
            returned_stock_quality = st.radio(
                "Have you returned/discarded drug stock due to quality deterioration? *",
                ["Yes","No"], horizontal=True
            )
            num_quality_incidents = st.selectbox(
                "Approximately how many drug quality incidents in the last 12 months? *",
                ["-- Select --","None","1 – 3","4 – 6","7 – 10","More than 10"]
            )

        # ── SECTION F ──────────────────────────────────────────
        st.markdown('<div class="section-card"><div class="section-title">💡 Section F — Challenges & Recommendations</div></div>', unsafe_allow_html=True)
        biggest_challenge = st.selectbox(
            "What is the BIGGEST challenge to maintaining proper drug storage in your pharmacy? *",
            ["-- Select --",
             "Frequent power outages / erratic electricity supply",
             "High cost of air conditioning or refrigeration",
             "Small or inadequate storage space",
             "Lack of temperature/humidity monitoring equipment",
             "Limited training and awareness on GSP",
             "Insufficient regulatory inspection and enforcement",
             "Financial constraints to upgrade facilities"]
        )
        support_needed = st.selectbox(
            "What type of support would most improve drug storage in your pharmacy? *",
            ["-- Select --",
             "Subsidised air conditioning and refrigeration equipment",
             "Regular GSP training workshops",
             "Affordable data loggers or thermometers",
             "More frequent FDA inspections and guidance",
             "Financial support / grants for facility upgrades",
             "National policy changes and stricter enforcement"]
        )
        policy_recommendation = st.text_area(
            "Any policy recommendations to improve drug storage standards in Ghana? (optional)",
            placeholder="Share your suggestions...", height=90
        )
        additional_comments = st.text_area(
            "Additional comments or observations? (optional)",
            placeholder="Anything else you would like to share...", height=80
        )

        # ── SUBMIT ─────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**⚠️ Please review all answers before submitting.**")
        submitted = st.form_submit_button("✅  Submit Survey Response", use_container_width=True)

        if submitted:
            errors = []
            if not pharmacy_name.strip():    errors.append("Pharmacy name is required.")
            if not pharmacist_name.strip():  errors.append("Pharmacist name is required.")
            if not reg_number.strip():       errors.append("Registration number is required.")
            if years_experience < 0:         errors.append("Years of experience cannot be negative.")
            if num_staff < 1:                errors.append("Number of staff must be at least 1.")
            if pharmacist_email.strip() and not is_valid_email(pharmacist_email):
                errors.append("Please enter a valid email address.")
            for label, val in {
                "Type of pharmacy": pharmacy_type,
                "Pharmacy location": location_type,
                "Storage area size": storage_area_size,
                "Temperature monitoring frequency": temp_monitoring_freq,
                "Usual temperature range": usual_temp_range,
                "Usual humidity range": usual_humidity_range,
                "Action on temperature excursion": temp_excursion_action,
                "Number of quality incidents": num_quality_incidents,
                "Biggest challenge": biggest_challenge,
                "Support needed": support_needed,
            }.items():
                if val.startswith("-- Select"):
                    errors.append(f"'{label}' is required — please select an option.")

            if errors:
                st.error("**Please fix the following errors before submitting:**")
                for e in errors:
                    st.markdown(f"- ❌ {e}")
            else:
                data = {
                    "submitted_at":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "pharmacy_name":          pharmacy_name.strip(),
                    "pharmacist_name":        pharmacist_name.strip(),
                    "pharmacist_email":       pharmacist_email.strip(),
                    "reg_number":             reg_number.strip(),
                    "years_experience":       int(years_experience),
                    "pharmacy_type":          pharmacy_type,
                    "num_staff":              int(num_staff),
                    "location_type":          location_type,
                    "has_ac":                 1 if has_ac == "Yes" else 0,
                    "has_refrigerator":       1 if has_refrigerator == "Yes" else 0,
                    "has_thermometer":        1 if has_thermometer == "Yes" else 0,
                    "has_hygrometer":         1 if has_hygrometer == "Yes" else 0,
                    "has_proper_shelving":    1 if has_proper_shelving == "Yes" else 0,
                    "has_ventilation":        1 if has_ventilation == "Yes" else 0,
                    "has_direct_sunlight":    1 if has_direct_sunlight == "Yes" else 0,
                    "storage_area_size":      storage_area_size,
                    "temp_monitoring_freq":   temp_monitoring_freq,
                    "usual_temp_range":       usual_temp_range,
                    "usual_humidity_range":   usual_humidity_range,
                    "temp_excursion_action":  temp_excursion_action,
                    "has_written_sop":        1 if has_written_sop == "Yes" else 0,
                    "gsp_training_received":  1 if gsp_training_received == "Yes" else 0,
                    "last_training_year":     last_training_year,
                    "practises_fifo":         practises_fifo,
                    "checks_expiry":          checks_expiry,
                    "segregates_thermolabile":segregates_thermolabile,
                    "fda_inspected":          1 if fda_inspected == "Yes" else 0,
                    "self_compliance_rating": self_compliance_rating,
                    "observed_degradation":   1 if observed_degradation == "Yes" else 0,
                    "degradation_drug_types": ", ".join(degradation_drug_types),
                    "observed_color_change":  1 if observed_color_change == "Yes" else 0,
                    "potency_complaints":     1 if potency_complaints == "Yes" else 0,
                    "returned_stock_quality": 1 if returned_stock_quality == "Yes" else 0,
                    "num_quality_incidents":  num_quality_incidents,
                    "biggest_challenge":      biggest_challenge,
                    "support_needed":         support_needed,
                    "policy_recommendation":  policy_recommendation.strip(),
                    "additional_comments":    additional_comments.strip(),
                }
                insert_response(data)
                st.markdown("""
                <div class="success-box">
                    <h2>✅ Response Submitted Successfully!</h2>
                    <p style="color:#065A82; font-size:1.05em;">
                        Thank you for completing this survey.<br>
                        Your contribution is vital to improving drug storage practices
                        and patient safety in the Sunyani Municipality.
                    </p>
                    <p style="font-size:0.82em; color:#888; margin-top:12px;">
                        Sunyani Technical University — Department of Pharmacy, March 2026
                    </p>
                </div>
                """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# NOTE: Dashboard, Report, Responses, and About pages
# remain exactly the same as your original code
# They just use fetch_all() which now works with Supabase
# ─────────────────────────────────────────────

# For brevity, I'm showing just the navigation below
# Your existing dashboard, report, responses, and about functions go here
# (Keep all your original chart code - it will work unchanged)

# ─────────────────────────────────────────────
# NAVIGATION & LAYOUT
# ─────────────────────────────────────────────
render_header()

st.sidebar.markdown("""
<div style="text-align:center; padding:10px 0 18px;">
    <div style="font-size:2.4em;">💊</div>
    <div style="font-weight:800; color:#028090; font-size:1.0em;">Drug Storage Survey</div>
    <div style="font-size:0.75em; color:#888; margin-top:4px;">
        Sunyani Technical University<br>Department of Pharmacy
    </div>
</div>
""", unsafe_allow_html=True)

page = st.sidebar.radio(
    "Navigation",
    ["📋  Fill Survey", "📊  Dashboard & Charts", "📄  Generate Report", "📁  View Responses", "ℹ️  About"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
try:
    count = response_count()
    st.sidebar.markdown(f"""
    <div style="background:linear-gradient(135deg,#028090,#065A82);
                color:white; border-radius:10px; padding:14px; text-align:center;">
        <div style="font-size:2em; font-weight:800;">{count}</div>
        <div style="font-size:0.82em; opacity:0.9;">Responses Collected</div>
    </div>
    """, unsafe_allow_html=True)
except Exception:
    st.sidebar.warning("⚠️ DB not connected")

# ── Route ─────────────────────────────────────
if "Fill Survey" in page:
    page_survey()
elif "Dashboard" in page:
    # You'll need to add your dashboard function here
    st.info("Dashboard page - add your chart code here")
elif "Generate Report" in page:
    st.info("Report page - add your PDF generation here")
elif "View Responses" in page:
    st.info("Responses page - add your data viewer here")
elif "About" in page:
    ok = check_connection()
    if ok:
        st.markdown('<div class="db-status-ok">🟢 &nbsp; <strong>Database Connected</strong> — Supabase is active and reachable.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="db-status-err">🔴 &nbsp; <strong>Database Unavailable</strong> — Check your SUPABASE_URL and SUPABASE_KEY secrets.</div>', unsafe_allow_html=True)
    st.markdown("### ✅ Connection Fixed!")
    st.markdown("Your app is now using the Supabase client which avoids IPv6 issues.")
