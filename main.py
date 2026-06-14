
#Drug Storage Conditions Survey — Sunyani Technical University


import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import os
import io
from datetime import datetime

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
# CUSTOM CSS
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
    footer { visibility: hidden; }
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
# SUPABASE / POSTGRESQL DATABASE LAYER
# ─────────────────────────────────────────────
# ┌─────────────────────────────────────────────────────────────┐
# │  SETUP INSTRUCTIONS — SUPABASE                              │
# │                                                             │
# │  1. Go to https://supabase.com and create a project.        │
# │  2. In your project, open SQL Editor and run the SQL in     │
# │     the file  supabase_schema.sql  (shipped alongside       │
# │     this app).                                              │
# │  3. In Streamlit Cloud, go to App Settings → Secrets and   │
# │     add:                                                    │
# │         SUPABASE_URL = "https://xxxx.supabase.co"           │
# │         SUPABASE_KEY = "your-anon-or-service-role-key"      │
# │     OR add a direct PostgreSQL connection string:           │
# │         DATABASE_URL = "postgresql://user:pass@host/db"     │
# │  4. For local development create a file .streamlit/secrets  │
# │     .toml with the same keys.                               │
# └─────────────────────────────────────────────────────────────┘

def get_db_connection():
    """Return a psycopg2 connection using Streamlit secrets."""
    import psycopg2
    try:
        db_url = st.secrets["DATABASE_URL"]
        conn = psycopg2.connect(db_url, sslmode="require")
        return conn
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}\n\nPlease check your DATABASE_URL in Streamlit secrets.")
        st.stop()

@st.cache_resource(ttl=30)
def _get_cached_conn():
    return get_db_connection()

def run_query(sql: str, params=None, fetch=True):
    """Run a SQL query and optionally return rows."""
    import psycopg2
    conn = _get_cached_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        if fetch:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
        else:
            conn.commit()
    except psycopg2.OperationalError:
        # Try to reconnect once
        _get_cached_conn.clear()
        conn = _get_cached_conn()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        if fetch:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
        else:
            conn.commit()

def insert_response(data: dict):
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    sql = f"INSERT INTO responses ({cols}) VALUES ({placeholders})"
    run_query(sql, list(data.values()), fetch=False)

def fetch_all() -> pd.DataFrame:
    return run_query("SELECT * FROM responses ORDER BY submitted_at DESC")

def delete_response(rid: int):
    run_query("DELETE FROM responses WHERE id=%s", (rid,), fetch=False)

def response_count() -> int:
    df = run_query("SELECT COUNT(*) AS n FROM responses")
    return int(df["n"].iloc[0]) if not df.empty else 0

def check_connection() -> bool:
    try:
        run_query("SELECT 1 AS ok")
        return True
    except Exception:
        return False

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
# PAGE: DASHBOARD  (10 + enhanced charts)
# ─────────────────────────────────────────────
def page_dashboard():
    df = fetch_all()
    if df.empty:
        st.warning("📭 No survey responses yet. Share the survey link with pharmacists to collect data.")
        return

    n = len(df)

    # ── Filters ────────────────────────────────────────────────
    with st.expander("🔽 Filter Data", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            loc_opts = ["All"] + sorted(df["location_type"].dropna().unique().tolist())
            sel_loc  = st.selectbox("Location Type", loc_opts)
        with fc2:
            typ_opts = ["All"] + sorted(df["pharmacy_type"].dropna().unique().tolist())
            sel_typ  = st.selectbox("Pharmacy Type", typ_opts)
        with fc3:
            rat_opts = ["All", "Very Poor","Poor","Fair","Good","Excellent"]
            sel_rat  = st.selectbox("Compliance Rating", rat_opts)

    if sel_loc != "All": df = df[df["location_type"] == sel_loc]
    if sel_typ != "All": df = df[df["pharmacy_type"] == sel_typ]
    if sel_rat != "All": df = df[df["self_compliance_rating"] == sel_rat]
    n = len(df)
    if n == 0:
        st.info("No responses match the selected filters.")
        return

    # ── KPI Tiles ──────────────────────────────────────────────
    st.markdown("### 📈 Research Summary — Key Metrics")
    kpi_data = [
        ("Total Responses",        str(n),                                       "📋"),
        ("Have Air Conditioning",  f"{df['has_ac'].mean()*100:.0f}%",            "❄️"),
        ("Have Thermometer",       f"{df['has_thermometer'].mean()*100:.0f}%",   "🌡️"),
        ("GSP Trained",            f"{df['gsp_training_received'].mean()*100:.0f}%","🎓"),
        ("Observed Degradation",   f"{df['observed_degradation'].mean()*100:.0f}%","⚠️"),
        ("Have Written SOP",       f"{df['has_written_sop'].mean()*100:.0f}%",   "📄"),
        ("FDA Inspected",          f"{df['fda_inspected'].mean()*100:.0f}%",     "🔍"),
        ("Have Refrigerator",      f"{df['has_refrigerator'].mean()*100:.0f}%",  "🧊"),
    ]
    cols = st.columns(8)
    for col, (label, val, ico) in zip(cols, kpi_data):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size:1.5em">{ico}</div>
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # CHART ROW 1 — Equipment & Temperature
    # ══════════════════════════════════════════
    st.markdown("### 🏗️ Physical Storage Infrastructure")
    col1, col2 = st.columns(2)

    with col1:
        # ── CHART 1: Equipment Availability — Horizontal Bar ──
        labels = ["Air Conditioning","Refrigerator","Thermometer",
                  "Hygrometer","Proper Shelving","Ventilation"]
        keys   = ["has_ac","has_refrigerator","has_thermometer",
                  "has_hygrometer","has_proper_shelving","has_ventilation"]
        vals   = [round(df[k].mean()*100, 1) for k in keys]
        colors = [GREEN if v >= 70 else CORAL for v in vals]

        fig = go.Figure(go.Bar(
            x=vals, y=labels, orientation='h',
            marker_color=colors,
            text=[f"{v}%" for v in vals], textposition='outside',
            hovertemplate='%{y}: %{x:.1f}%<extra></extra>'
        ))
        fig.add_vline(x=70, line_dash="dash", line_color=NAVY, line_width=2,
                      annotation_text="70% Benchmark",
                      annotation_position="top right", annotation_font_size=11)
        fig.update_layout(
            title=dict(text="📦 Storage Equipment Availability<br><sup>Green ≥ 70% adequate | Red = below benchmark</sup>", font_size=14),
            xaxis=dict(title="% of Pharmacies", range=[0, 118]),
            yaxis_title="", height=390,
            margin=dict(l=10, r=20, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("🔑 Red bars indicate equipment present in fewer than 70% of pharmacies — a critical compliance gap that directly risks drug quality.")

    with col2:
        # ── CHART 2: Storage Area Size — Donut ──
        sz = df["storage_area_size"].value_counts().reset_index()
        sz.columns = ["Size","Count"]
        fig2 = px.pie(sz, values="Count", names="Size", hole=0.44,
                      color_discrete_sequence=[GREEN, TEAL, GOLD, CORAL])
        fig2.update_traces(textinfo='percent+label',
                           hovertemplate='%{label}: %{value} pharmacies (%{percent})<extra></extra>')
        fig2.update_layout(
            title=dict(text="📐 Drug Storage Area Size Distribution<br><sup>Small/cramped spaces limit safe drug organisation</sup>", font_size=14),
            showlegend=False, height=390,
            margin=dict(l=10, r=10, t=85, b=10), paper_bgcolor="white"
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("🔑 Very small storage areas make FIFO rotation and proper drug segregation extremely difficult, elevating contamination risk.")

    # ══════════════════════════════════════════
    # CHART ROW 2 — Temperature & Humidity
    # ══════════════════════════════════════════
    st.markdown("### 🌡️ Temperature & Humidity Conditions")
    col1, col2 = st.columns(2)

    with col1:
        # ── CHART 3: Temperature Donut ──
        temp_short = {
            "Below 25°C  (WHO Optimal)":      "< 25°C ✅ Optimal",
            "25°C – 30°C  (Acceptable)":       "25–30°C ⚠️ Acceptable",
            "30°C – 35°C  (Risk Zone)":        "30–35°C 🔶 Risk Zone",
            "Above 35°C  (High Risk)":         "> 35°C 🔴 High Risk",
            "Not monitored / Unknown":          "Unknown"
        }
        df["temp_label"] = df["usual_temp_range"].map(temp_short).fillna(df["usual_temp_range"])
        tc = df["temp_label"].value_counts().reset_index()
        tc.columns = ["Range","Count"]
        fig3 = px.pie(tc, values="Count", names="Range", hole=0.44,
                      color_discrete_sequence=[GREEN, TEAL, GOLD, CORAL, SLATE])
        fig3.update_traces(textinfo='percent+label',
                           hovertemplate='%{label}: %{value} pharmacies (%{percent})<extra></extra>')
        fig3.update_layout(
            title=dict(text="🌡️ Usual Temperature in Storage Areas<br><sup>WHO recommends ≤25–30°C for most medicines</sup>", font_size=14),
            showlegend=False, height=390,
            margin=dict(l=10, r=10, t=85, b=10), paper_bgcolor="white"
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("🔑 Pharmacies in the orange/red segments store drugs above recommended limits, accelerating hydrolysis and oxidation.")

    with col2:
        # ── CHART 4: Humidity — Horizontal Bar ──
        hum_short = {
            "Below 45% RH  (Low)":            "< 45% RH",
            "45% – 65% RH  (Optimal)":        "45–65% ✅ Optimal",
            "65% – 75% RH  (Elevated Risk)":  "65–75% ⚠️ Elevated",
            "Above 75% RH  (High Risk)":       "> 75% 🔴 High Risk",
            "Not monitored / Unknown":          "Unknown"
        }
        df["hum_label"] = df["usual_humidity_range"].map(hum_short).fillna(df["usual_humidity_range"])
        hc = df["hum_label"].value_counts().reset_index()
        hc.columns = ["Humidity","Count"]
        hum_colors = [GREEN if "Optimal" in r else CORAL if "High" in r else GOLD if "Elevated" in r else SLATE for r in hc["Humidity"]]
        fig4 = go.Figure(go.Bar(
            x=hc["Count"], y=hc["Humidity"], orientation='h',
            marker_color=hum_colors,
            text=hc["Count"], textposition='outside',
            hovertemplate='%{y}: %{x} pharmacies<extra></extra>'
        ))
        fig4.update_layout(
            title=dict(text="💧 Relative Humidity in Storage Areas<br><sup>Optimal range: 45–65% RH for most medicines</sup>", font_size=14),
            xaxis_title="Number of Pharmacies", yaxis_title="",
            height=390, margin=dict(l=10, r=30, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig4, use_container_width=True)
        st.caption("🔑 High humidity (>65% RH) accelerates moisture-induced degradation in antibiotics, antimalarials and oral solids.")

    # ── CHART 5: Temp vs Humidity Scatter ──
    st.markdown("#### 🔗 Temperature Risk vs. Humidity Risk — Cross-Analysis")
    temp_risk = {
        "Below 25°C  (WHO Optimal)": 1,
        "25°C – 30°C  (Acceptable)": 2,
        "30°C – 35°C  (Risk Zone)": 3,
        "Above 35°C  (High Risk)": 4,
        "Not monitored / Unknown": 0
    }
    hum_risk = {
        "Below 45% RH  (Low)": 2,
        "45% – 65% RH  (Optimal)": 1,
        "65% – 75% RH  (Elevated Risk)": 3,
        "Above 75% RH  (High Risk)": 4,
        "Not monitored / Unknown": 0
    }
    scatter_df = df.copy()
    scatter_df["temp_score"] = scatter_df["usual_temp_range"].map(temp_risk).fillna(0)
    scatter_df["hum_score"]  = scatter_df["usual_humidity_range"].map(hum_risk).fillna(0)
    scatter_df["risk_total"] = scatter_df["temp_score"] + scatter_df["hum_score"]
    fig_sc = px.scatter(
        scatter_df, x="temp_score", y="hum_score",
        color="pharmacy_type", size="risk_total",
        size_max=28,
        hover_data=["pharmacy_name","location_type","self_compliance_rating"],
        color_discrete_sequence=[TEAL, CORAL, GOLD, PURPLE],
        labels={"temp_score":"Temperature Risk Level (1=Low → 4=High)",
                "hum_score":"Humidity Risk Level (1=Low → 4=High)",
                "pharmacy_type":"Pharmacy Type"},
        title="🔗 Temperature vs. Humidity Risk by Pharmacy Type<br><sup>Bubble size = combined risk score | Upper-right = highest risk</sup>"
    )
    fig_sc.update_layout(height=420, paper_bgcolor="white", plot_bgcolor="white")
    st.plotly_chart(fig_sc, use_container_width=True)
    st.caption("🔑 Pharmacies in the upper-right quadrant face compounded risk from both high temperature and high humidity simultaneously.")

    # ══════════════════════════════════════════
    # CHART ROW 3 — GSP Compliance
    # ══════════════════════════════════════════
    st.markdown("### ✅ WHO Good Storage Practice (GSP) Compliance")
    col1, col2 = st.columns(2)

    with col1:
        # ── CHART 6: Stacked Bar — GSP ──
        clabels = ["GSP Training","Written SOP","FIFO Rotation",
                   "Expiry Checks","Thermolabile Segregation","FDA Inspected"]
        yes_pcts = [
            df["gsp_training_received"].mean()*100,
            df["has_written_sop"].mean()*100,
            (df["practises_fifo"]=="Yes").mean()*100,
            (df["checks_expiry"]=="Yes").mean()*100,
            (df["segregates_thermolabile"]=="Yes").mean()*100,
            df["fda_inspected"].mean()*100,
        ]
        no_pcts = [100-v for v in yes_pcts]
        fig6 = go.Figure()
        fig6.add_trace(go.Bar(name="Compliant ✅", x=clabels, y=yes_pcts,
                              marker_color=GREEN, text=[f"{v:.0f}%" for v in yes_pcts],
                              textposition='inside',
                              hovertemplate='%{x}<br>Compliant: %{y:.1f}%<extra></extra>'))
        fig6.add_trace(go.Bar(name="Non-compliant ❌", x=clabels, y=no_pcts,
                              marker_color=CORAL, text=[f"{v:.0f}%" for v in no_pcts],
                              textposition='inside',
                              hovertemplate='%{x}<br>Non-compliant: %{y:.1f}%<extra></extra>'))
        fig6.update_layout(
            barmode='stack',
            title=dict(text="✅ WHO GSP Compliance by Practice<br><sup>Green = Compliant | Red = Non-compliant</sup>", font_size=14),
            yaxis_title="% of Pharmacies", xaxis_tickangle=-20, height=400,
            margin=dict(l=20, r=20, t=85, b=90),
            legend=dict(orientation='h', yanchor='bottom', y=-0.38),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig6, use_container_width=True)
        st.caption("🔑 Large red segments reveal which GSP practices are most neglected.")

    with col2:
        # ── CHART 7: Spider — Drug Quality Risk ──
        cats = ["Degradation Observed","Colour Changes","Potency Complaints",
                "Returned Stock","No SOP","No Thermometer"]
        rvals = [
            df["observed_degradation"].mean()*100,
            df["observed_color_change"].mean()*100,
            df["potency_complaints"].mean()*100,
            df["returned_stock_quality"].mean()*100,
            (1-df["has_written_sop"].mean())*100,
            (1-df["has_thermometer"].mean())*100,
        ]
        fig7 = go.Figure(go.Scatterpolar(
            r=rvals + [rvals[0]], theta=cats + [cats[0]], fill='toself',
            fillcolor="rgba(249,97,103,0.20)",
            line=dict(color=CORAL, width=2.5),
            hovertemplate='%{theta}: %{r:.1f}%<extra></extra>'
        ))
        fig7.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0,100],
                                       ticksuffix="%", tickfont_size=10),
                       angularaxis=dict(tickfont_size=11)),
            title=dict(text="🕸️ Drug Quality Risk Radar<br><sup>Larger shaded area = broader systemic risk</sup>", font_size=14),
            height=400, showlegend=False,
            margin=dict(l=60, r=60, t=85, b=60), paper_bgcolor="white"
        )
        st.plotly_chart(fig7, use_container_width=True)
        st.caption("🔑 Points near the outer edge signal critical problems across multiple quality dimensions.")

    # ── CHART 8: Self-rated Compliance + Location breakdown ──
    st.markdown("#### 🌟 Compliance Rating by Pharmacy Location")
    order = ["Very Poor","Poor","Fair","Good","Excellent"]
    heat_df = df.groupby(["location_type","self_compliance_rating"]).size().reset_index(name="Count")
    fig8 = px.bar(heat_df, x="self_compliance_rating", y="Count",
                  color="location_type",
                  barmode="group",
                  category_orders={"self_compliance_rating": order},
                  color_discrete_sequence=[TEAL, CORAL, GOLD],
                  labels={"self_compliance_rating":"Self-rated Compliance",
                          "Count":"Number of Pharmacies",
                          "location_type":"Location Type"},
                  title="🌟 Pharmacists' Self-Rated GSP Compliance by Location<br><sup>Grouped bar: Urban vs Peri-urban vs Rural</sup>")
    fig8.update_layout(height=380, plot_bgcolor="white", paper_bgcolor="white",
                       margin=dict(t=85))
    st.plotly_chart(fig8, use_container_width=True)
    st.caption("🔑 Compare compliance self-perception across urban, peri-urban and rural pharmacies to identify location-specific patterns.")

    # ══════════════════════════════════════════
    # CHART ROW 4 — Quality Incidents
    # ══════════════════════════════════════════
    st.markdown("### ⚠️ Drug Quality & Incident Analysis")
    col1, col2 = st.columns(2)

    with col1:
        # ── CHART 9: Monitoring Frequency — Funnel/Bar ──
        freq_map = {
            "Multiple times daily":"Multiple/Day ✅",
            "Once daily":"Once Daily ✅",
            "Weekly":"Weekly ⚠️",
            "Monthly":"Monthly ⚠️",
            "Never monitored":"Never 🔴"
        }
        freq_order = ["Multiple/Day ✅","Once Daily ✅","Weekly ⚠️","Monthly ⚠️","Never 🔴"]
        df["freq_short"] = df["temp_monitoring_freq"].map(freq_map).fillna(df["temp_monitoring_freq"])
        fc = df["freq_short"].value_counts().reindex(freq_order, fill_value=0).reset_index()
        fc.columns = ["Frequency","Count"]
        f_colors = [GREEN, GREEN, GOLD, AMBER, CORAL]
        fig9 = go.Figure(go.Bar(
            x=fc["Frequency"], y=fc["Count"], marker_color=f_colors,
            text=fc["Count"], textposition='outside',
            hovertemplate='%{x}: %{y} pharmacies<extra></extra>'
        ))
        fig9.update_layout(
            title=dict(text="🕐 Temperature Monitoring Frequency<br><sup>WHO GSP requires minimum once-daily recording</sup>", font_size=14),
            xaxis_title="Monitoring Frequency", yaxis_title="Number of Pharmacies",
            height=380, margin=dict(l=20, r=20, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig9, use_container_width=True)
        st.caption("🔑 Infrequent or absent monitoring means temperature excursions go undetected, silently degrading drug potency.")

    with col2:
        # ── CHART 10: Quality Incidents — Colour-coded Bar ──
        inc_order = ["None","1 – 3","4 – 6","7 – 10","More than 10"]
        ic = df["num_quality_incidents"].value_counts().reindex(inc_order, fill_value=0).reset_index()
        ic.columns = ["Incidents","Count"]
        ip = (ic["Count"]/n*100).round(1)
        fig10 = go.Figure(go.Bar(
            x=ic["Incidents"], y=ic["Count"],
            marker_color=[GREEN, TEAL, GOLD, AMBER, CORAL],
            text=[f"{c} ({p}%)" for c,p in zip(ic["Count"],ip)],
            textposition='outside',
            hovertemplate='%{x}: %{y} pharmacies<extra></extra>'
        ))
        fig10.update_layout(
            title=dict(text="📦 Drug Quality Incidents in Last 12 Months<br><sup>Per pharmacy, self-reported</sup>", font_size=14),
            xaxis_title="Number of Incidents", yaxis_title="Number of Pharmacies",
            height=380, margin=dict(l=20, r=20, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig10, use_container_width=True)
        st.caption("🔑 Higher counts in 4+ categories signal systemic storage failures requiring urgent regulatory attention.")

    # ── CHART 11: Degradation Drug Types — Treemap ──
    st.markdown("#### 🧪 Which Drug Types Show Degradation?")
    if df["degradation_drug_types"].notna().any():
        all_drugs = []
        for val in df["degradation_drug_types"].dropna():
            if val.strip():
                all_drugs.extend([d.strip() for d in val.split(",")])
        if all_drugs:
            drug_counts = pd.Series(all_drugs).value_counts().reset_index()
            drug_counts.columns = ["Drug Type","Count"]
            fig11 = px.treemap(drug_counts, path=["Drug Type"], values="Count",
                               color="Count",
                               color_continuous_scale=[[0,MINT],[0.5,TEAL],[1,NAVY]],
                               title="🧪 Drug Types Affected by Degradation<br><sup>Larger box = more frequently reported</sup>")
            fig11.update_layout(height=380, margin=dict(t=85, l=10, r=10, b=10))
            st.plotly_chart(fig11, use_container_width=True)
            st.caption("🔑 Focus regulatory and training attention on the most frequently degraded drug categories.")

    # ══════════════════════════════════════════
    # CHART ROW 5 — Experience & Staff
    # ══════════════════════════════════════════
    st.markdown("### 👥 Staff & Experience Profile")
    col1, col2 = st.columns(2)

    with col1:
        # ── CHART 12: Experience Histogram ──
        fig12 = px.histogram(df, x="years_experience", nbins=12,
                             color_discrete_sequence=[TEAL],
                             labels={"years_experience":"Years of Experience","count":"Number of Pharmacists"},
                             title="📅 Distribution of Pharmacist Experience<br><sup>Experience in years across all respondents</sup>")
        fig12.update_layout(height=360, plot_bgcolor="white", paper_bgcolor="white",
                            margin=dict(t=85), bargap=0.05)
        st.plotly_chart(fig12, use_container_width=True)
        st.caption("🔑 Less experienced pharmacists may have lower awareness of WHO GSP standards — a key training target group.")

    with col2:
        # ── CHART 13: Pharmacy Type Pie ──
        pt = df["pharmacy_type"].value_counts().reset_index()
        pt.columns = ["Type","Count"]
        fig13 = px.pie(pt, values="Count", names="Type", hole=0.35,
                       color_discrete_sequence=[TEAL, CORAL, GOLD, PURPLE],
                       title="🏪 Pharmacy Type Distribution<br><sup>Mix of respondents across pharmacy categories</sup>")
        fig13.update_traces(textinfo='percent+label',
                            hovertemplate='%{label}: %{value} (%{percent})<extra></extra>')
        fig13.update_layout(height=360, showlegend=False,
                            margin=dict(l=10, r=10, t=85, b=10), paper_bgcolor="white")
        st.plotly_chart(fig13, use_container_width=True)
        st.caption("🔑 Ensure equal representation across pharmacy types for valid research conclusions.")

    # ── CHART 14: Correlation Heatmap ──
    st.markdown("#### 🔥 Binary Indicators Correlation Heatmap")
    bool_cols = ["has_ac","has_refrigerator","has_thermometer","has_hygrometer",
                 "has_proper_shelving","has_ventilation","has_written_sop",
                 "gsp_training_received","fda_inspected",
                 "observed_degradation","observed_color_change","potency_complaints"]
    corr_df = df[bool_cols].corr().round(2)
    short_names = ["AC","Fridge","Thermom.","Hygrom.","Shelving","Ventil.",
                   "SOP","GSP Train.","FDA Insp.","Degradat.","Color Chg","Potency Cmpl."]
    fig14 = go.Figure(go.Heatmap(
        z=corr_df.values,
        x=short_names, y=short_names,
        colorscale=[[0,CORAL],[0.5,"white"],[1,GREEN]],
        zmid=0, zmin=-1, zmax=1,
        text=corr_df.values.round(2),
        texttemplate="%{text}",
        hovertemplate='%{y} vs %{x}: %{z:.2f}<extra></extra>'
    ))
    fig14.update_layout(
        title=dict(text="🔥 Correlation Between Storage Infrastructure & Quality Indicators<br><sup>Green = positive correlation | Red = inverse correlation</sup>", font_size=14),
        height=480, margin=dict(t=100, l=10, r=10, b=10),
        paper_bgcolor="white"
    )
    st.plotly_chart(fig14, use_container_width=True)
    st.caption("🔑 Strong green cells reveal which infrastructure investments most reliably reduce drug quality problems.")

    # ══════════════════════════════════════════
    # CHART ROW 6 — Challenges & Support
    # ══════════════════════════════════════════
    st.markdown("### 🚧 Identified Barriers & Support Needs")
    col1, col2 = st.columns(2)

    with col1:
        # ── CHART 15: Biggest Challenges — Horizontal Bar ──
        ch_short = {
            "Frequent power outages / erratic electricity supply": "Power Outages",
            "High cost of air conditioning or refrigeration": "High Equipment Cost",
            "Small or inadequate storage space": "Inadequate Storage Space",
            "Lack of temperature/humidity monitoring equipment": "No Monitoring Equipment",
            "Limited training and awareness on GSP": "Limited GSP Training",
            "Insufficient regulatory inspection and enforcement": "Weak Regulation/Enforcement",
            "Financial constraints to upgrade facilities": "Financial Constraints"
        }
        df["chall_short"] = df["biggest_challenge"].map(ch_short).fillna(df["biggest_challenge"])
        ch = df["chall_short"].value_counts().sort_values().reset_index()
        ch.columns = ["Challenge","Count"]
        fig15 = px.bar(ch, x="Count", y="Challenge", orientation='h',
                       color="Count",
                       color_continuous_scale=[[0,MINT],[0.5,TEAL],[1,NAVY]],
                       text="Count")
        fig15.update_traces(textposition='outside',
                            hovertemplate='%{y}: %{x} pharmacies<extra></extra>')
        fig15.update_layout(
            title=dict(text="🚧 Biggest Challenges to Proper Drug Storage<br><sup>As reported by pharmacists</sup>", font_size=14),
            showlegend=False, coloraxis_showscale=False,
            xaxis_title="Number of Pharmacies", yaxis_title="",
            height=400, margin=dict(l=10, r=30, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig15, use_container_width=True)
        st.caption("🔑 The longest bars identify the most common barriers — essential for designing targeted policy interventions.")

    with col2:
        # ── CHART 16: Support Needed — Donut ──
        sup_short = {
            "Subsidised air conditioning and refrigeration equipment": "Subsidised Equipment",
            "Regular GSP training workshops": "GSP Training Workshops",
            "Affordable data loggers or thermometers": "Affordable Monitoring Tools",
            "More frequent FDA inspections and guidance": "More FDA Inspections",
            "Financial support / grants for facility upgrades": "Financial Grants",
            "National policy changes and stricter enforcement": "Policy & Enforcement Reform"
        }
        df["sup_short"] = df["support_needed"].map(sup_short).fillna(df["support_needed"])
        sp = df["sup_short"].value_counts().reset_index()
        sp.columns = ["Support","Count"]
        fig16 = px.pie(sp, values="Count", names="Support", hole=0.40,
                       color_discrete_sequence=[TEAL, GREEN, NAVY, CORAL, GOLD, SLATE])
        fig16.update_traces(textinfo='percent+label',
                            hovertemplate='%{label}: %{value} pharmacies (%{percent})<extra></extra>')
        fig16.update_layout(
            title=dict(text="🤝 Type of Support Most Needed<br><sup>Pharmacists' top requested interventions</sup>", font_size=14),
            showlegend=False, height=400,
            margin=dict(l=10, r=10, t=85, b=10), paper_bgcolor="white"
        )
        st.plotly_chart(fig16, use_container_width=True)
        st.caption("🔑 Dominant segments reveal what pharmacists believe would most improve drug storage quality.")

    # ── CHART 17: Line — Submissions over time ──
    if "submitted_at" in df.columns and df["submitted_at"].notna().any():
        st.markdown("#### 📅 Survey Response Collection Timeline")
        df["submitted_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
        daily = df.groupby(df["submitted_dt"].dt.date).size().reset_index(name="Count")
        daily.columns = ["Date","Count"]
        daily["Cumulative"] = daily["Count"].cumsum()
        fig17 = make_subplots(specs=[[{"secondary_y": True}]])
        fig17.add_trace(go.Bar(x=daily["Date"], y=daily["Count"],
                               name="Daily Responses", marker_color=TEAL,
                               opacity=0.7), secondary_y=False)
        fig17.add_trace(go.Scatter(x=daily["Date"], y=daily["Cumulative"],
                                   name="Cumulative Total", mode="lines+markers",
                                   line=dict(color=CORAL, width=2.5)),
                        secondary_y=True)
        fig17.update_layout(
            title=dict(text="📅 Response Collection Timeline<br><sup>Daily new responses (bars) and cumulative total (line)</sup>", font_size=14),
            height=360, plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(t=85), legend=dict(orientation='h', y=-0.2)
        )
        fig17.update_yaxes(title_text="Daily Responses", secondary_y=False)
        fig17.update_yaxes(title_text="Cumulative Responses", secondary_y=True)
        st.plotly_chart(fig17, use_container_width=True)
        st.caption("🔑 Track data collection progress to ensure sample size targets are met before analysis cutoff.")

# ─────────────────────────────────────────────
# PAGE: REPORT GENERATION
# ─────────────────────────────────────────────
def build_pdf_report(df: pd.DataFrame) -> bytes:
    """Generate a comprehensive PDF research report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2.5*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"],
                                 fontSize=16, textColor=colors.HexColor("#065A82"),
                                 spaceAfter=6, alignment=TA_CENTER)
    h1_style = ParagraphStyle("H1", parent=styles["Heading1"],
                              fontSize=13, textColor=colors.HexColor("#028090"),
                              spaceBefore=14, spaceAfter=4,
                              borderPad=4)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"],
                              fontSize=11, textColor=colors.HexColor("#065A82"),
                              spaceBefore=10, spaceAfter=2)
    body_style = ParagraphStyle("Body2", parent=styles["Normal"],
                                fontSize=9.5, leading=14, spaceAfter=4)
    caption_style = ParagraphStyle("Caption", parent=styles["Normal"],
                                   fontSize=8.5, textColor=colors.grey,
                                   leading=12, spaceAfter=6, leftIndent=6)
    right_style = ParagraphStyle("Right", parent=styles["Normal"],
                                 fontSize=8, textColor=colors.grey, alignment=TA_RIGHT)

    n = len(df)
    now = datetime.now().strftime("%d %B %Y, %H:%M")

    def tbl(data, col_widths=None, header_bg=colors.HexColor("#028090")):
        t = Table(data, colWidths=col_widths)
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), header_bg),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f9fb")]),
            ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor("#c0dde6")),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ])
        t.setStyle(style)
        return t

    story = []

    # ── Cover ──
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("RESEARCH REPORT", ParagraphStyle("Cover1", parent=styles["Normal"],
                            fontSize=10, textColor=colors.HexColor("#028090"),
                            alignment=TA_CENTER, spaceAfter=2)))
    story.append(Paragraph(
        "Evaluation of Storage Conditions of Drugs in Community Pharmacies<br/>"
        "and Their Influence on Drug Potency and Shelf Life<br/>"
        "in the Sunyani Municipality, Ghana",
        title_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#028090")))
    story.append(Spacer(1, 0.3*cm))

    meta = [
        ["Institution:", "Sunyani Technical University"],
        ["Department:", "Department of Pharmacy"],
        ["Supervisor:", "Mrs. Lydia Sarfo Mainoo"],
        ["Researchers:", "Obeng Theophilus · Yussif Asmau · Egawu Naomi"],
        ["Report Generated:", now],
        ["Total Responses:", str(n)],
    ]
    story.append(tbl(meta, col_widths=[4.5*cm, 12*cm]))
    story.append(Spacer(1, 0.5*cm))

    # ── Executive Summary ──
    story.append(Paragraph("1. Executive Summary", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))

    pct_ac    = df["has_ac"].mean()*100
    pct_therm = df["has_thermometer"].mean()*100
    pct_gsp   = df["gsp_training_received"].mean()*100
    pct_sop   = df["has_written_sop"].mean()*100
    pct_deg   = df["observed_degradation"].mean()*100
    pct_fda   = df["fda_inspected"].mean()*100

    story.append(Paragraph(
        f"This report summarises findings from <b>{n} community pharmacies</b> surveyed in the Sunyani Municipality, "
        f"Ghana. Key findings reveal significant infrastructure gaps: only <b>{pct_ac:.0f}%</b> of pharmacies have air "
        f"conditioning and only <b>{pct_therm:.0f}%</b> possess functional thermometers. WHO Good Storage Practice "
        f"(GSP) training has been received by <b>{pct_gsp:.0f}%</b> of pharmacists, while only <b>{pct_sop:.0f}%</b> "
        f"operate with a written SOP. Alarmingly, <b>{pct_deg:.0f}%</b> of pharmacies have observed physical signs of "
        f"drug degradation. FDA inspections reached only <b>{pct_fda:.0f}%</b> of facilities in the last two years, "
        f"indicating a regulatory gap. These findings collectively suggest systemic vulnerabilities in drug storage "
        f"conditions that may compromise drug potency and patient safety.", body_style))

    # ── Section A Summary ──
    story.append(Paragraph("2. Pharmacy & Pharmacist Profile (Section A)", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))

    avg_exp   = df["years_experience"].mean()
    avg_staff = df["num_staff"].mean()
    pt_counts = df["pharmacy_type"].value_counts()
    loc_counts= df["location_type"].value_counts()

    story.append(Paragraph(f"<b>Average pharmacist experience:</b> {avg_exp:.1f} years | "
                           f"<b>Average staff per pharmacy:</b> {avg_staff:.1f}", body_style))

    pt_data = [["Pharmacy Type","Count","% of Total"]] + \
              [[t, str(c), f"{c/n*100:.1f}%"] for t,c in pt_counts.items()]
    story.append(tbl(pt_data, col_widths=[8*cm, 4*cm, 4*cm]))
    story.append(Spacer(1, 0.3*cm))
    loc_data = [["Location Type","Count","% of Total"]] + \
               [[t, str(c), f"{c/n*100:.1f}%"] for t,c in loc_counts.items()]
    story.append(tbl(loc_data, col_widths=[8*cm, 4*cm, 4*cm]))

    # ── Section B ──
    story.append(Paragraph("3. Physical Storage Conditions (Section B)", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))
    equip = [
        ("Air Conditioning Unit",    df["has_ac"].mean()*100),
        ("Functional Refrigerator",  df["has_refrigerator"].mean()*100),
        ("Room Thermometer",         df["has_thermometer"].mean()*100),
        ("Hygrometer",               df["has_hygrometer"].mean()*100),
        ("Proper Shelving",          df["has_proper_shelving"].mean()*100),
        ("Adequate Ventilation",     df["has_ventilation"].mean()*100),
        ("Direct Sunlight Exposure", df["has_direct_sunlight"].mean()*100),
    ]
    eq_data = [["Equipment","% Have It","Status"]] + \
              [[e, f"{v:.1f}%", "✅ Adequate" if v >= 70 else "❌ Below Benchmark"] for e,v in equip]
    story.append(tbl(eq_data, col_widths=[8*cm, 4*cm, 4*cm]))
    story.append(Paragraph(
        "A 70% benchmark is applied to each equipment category. Items falling below this threshold "
        "represent critical infrastructure gaps requiring immediate policy intervention.", caption_style))

    # ── Section C ──
    story.append(Paragraph("4. Temperature & Humidity Monitoring (Section C)", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))
    temp_counts = df["usual_temp_range"].value_counts()
    hum_counts  = df["usual_humidity_range"].value_counts()
    freq_counts  = df["temp_monitoring_freq"].value_counts()

    story.append(Paragraph("<b>Temperature Range Distribution:</b>", h2_style))
    temp_data = [["Temperature Range","Count","% of Total"]] + \
                [[t, str(c), f"{c/n*100:.1f}%"] for t,c in temp_counts.items()]
    story.append(tbl(temp_data, col_widths=[9*cm, 3*cm, 4*cm]))

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<b>Humidity Range Distribution:</b>", h2_style))
    hum_data = [["Humidity Range","Count","% of Total"]] + \
               [[t, str(c), f"{c/n*100:.1f}%"] for t,c in hum_counts.items()]
    story.append(tbl(hum_data, col_widths=[9*cm, 3*cm, 4*cm]))

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<b>Monitoring Frequency:</b>", h2_style))
    freq_data = [["Monitoring Frequency","Count","% of Total"]] + \
                [[t, str(c), f"{c/n*100:.1f}%"] for t,c in freq_counts.items()]
    story.append(tbl(freq_data, col_widths=[9*cm, 3*cm, 4*cm]))

    # ── Section D ──
    story.append(Paragraph("5. GSP Compliance (Section D)", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))
    gsp_items = [
        ("GSP Training Received",              df["gsp_training_received"].mean()*100),
        ("Written SOP in Place",               df["has_written_sop"].mean()*100),
        ("Practises FIFO (Yes)",               (df["practises_fifo"]=="Yes").mean()*100),
        ("Regular Expiry Checks (Yes)",        (df["checks_expiry"]=="Yes").mean()*100),
        ("Thermolabile Drugs Segregated (Yes)",(df["segregates_thermolabile"]=="Yes").mean()*100),
        ("FDA Inspected in Last 2 Years",      df["fda_inspected"].mean()*100),
    ]
    gsp_data = [["GSP Indicator","% Compliant","Assessment"]] + \
               [[g, f"{v:.1f}%", "✅ Good" if v >= 70 else "⚠️ Needs Improvement"] for g,v in gsp_items]
    story.append(tbl(gsp_data, col_widths=[9*cm, 4*cm, 3*cm]))

    cr_counts = df["self_compliance_rating"].value_counts()
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<b>Self-Rated GSP Compliance:</b>", h2_style))
    cr_data = [["Rating","Count","% of Total"]] + \
              [[r, str(c), f"{c/n*100:.1f}%"] for r,c in cr_counts.items()]
    story.append(tbl(cr_data, col_widths=[6*cm, 4*cm, 6*cm]))

    # ── Section E ──
    story.append(Paragraph("6. Drug Quality & Potency Issues (Section E)", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))
    quality_items = [
        ("Observed Physical Degradation",     df["observed_degradation"].mean()*100),
        ("Observed Colour Changes",           df["observed_color_change"].mean()*100),
        ("Received Potency Complaints",       df["potency_complaints"].mean()*100),
        ("Returned/Discarded Stock for Quality", df["returned_stock_quality"].mean()*100),
    ]
    q_data = [["Quality Indicator","% Yes","Risk Level"]] + \
             [[q, f"{v:.1f}%", "🔴 High" if v >= 50 else "🟡 Moderate" if v >= 25 else "🟢 Low"] for q,v in quality_items]
    story.append(tbl(q_data, col_widths=[9*cm, 4*cm, 3*cm]))

    incident_counts = df["num_quality_incidents"].value_counts()
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<b>Drug Quality Incidents (Last 12 Months):</b>", h2_style))
    inc_data = [["Incident Count","Pharmacies","% of Total"]] + \
               [[i, str(c), f"{c/n*100:.1f}%"] for i,c in incident_counts.items()]
    story.append(tbl(inc_data, col_widths=[6*cm, 4*cm, 6*cm]))

    # ── Section F ──
    story.append(Paragraph("7. Challenges & Recommendations (Section F)", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))
    ch_counts  = df["biggest_challenge"].value_counts()
    sup_counts = df["support_needed"].value_counts()

    story.append(Paragraph("<b>Biggest Challenges Reported:</b>", h2_style))
    ch_data = [["Challenge","Count","% of Total"]] + \
              [[c[:60]+"…" if len(c)>60 else c, str(v), f"{v/n*100:.1f}%"] for c,v in ch_counts.items()]
    story.append(tbl(ch_data, col_widths=[10*cm, 2*cm, 4*cm]))

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<b>Types of Support Requested:</b>", h2_style))
    sp_data = [["Support Type","Count","% of Total"]] + \
              [[s[:60]+"…" if len(s)>60 else s, str(v), f"{v/n*100:.1f}%"] for s,v in sup_counts.items()]
    story.append(tbl(sp_data, col_widths=[10*cm, 2*cm, 4*cm]))

    # ── Policy Recommendations ──
    recs = df["policy_recommendation"].dropna()
    recs = recs[recs.str.strip() != ""]
    if not recs.empty:
        story.append(Paragraph("8. Selected Policy Recommendations from Pharmacists", h1_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))
        for i, rec in enumerate(recs.head(10), 1):
            story.append(Paragraph(f"<b>{i}.</b> {rec}", body_style))

    # ── Conclusions ──
    story.append(Paragraph("9. Conclusions & Research Implications", h1_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#028090")))
    story.append(Paragraph(
        f"Based on {n} responses collected from community pharmacies in the Sunyani Municipality, "
        "the following conclusions are drawn:", body_style))
    conclusions = [
        f"Infrastructure gaps are prevalent — AC availability at {pct_ac:.0f}% and thermometer availability "
        f"at {pct_therm:.0f}% fall below the 70% benchmark, indicating systemic under-investment in storage infrastructure.",
        f"WHO GSP compliance is incomplete — with only {pct_gsp:.0f}% of pharmacists GSP-trained and {pct_sop:.0f}% "
        f"operating written SOPs, knowledge and procedural gaps are widespread.",
        f"Drug quality events are common — {pct_deg:.0f}% of pharmacies report observable drug degradation, "
        "suggesting that current storage conditions are inadequate to preserve drug potency.",
        f"Regulatory oversight needs strengthening — only {pct_fda:.0f}% of pharmacies were inspected by the FDA Ghana "
        "in the last two years, representing a significant enforcement gap.",
        "Power supply instability is identified as the top systemic barrier to maintaining proper cold-chain and "
        "temperature-controlled storage conditions.",
        "Targeted interventions — including subsidised AC/refrigeration equipment, GSP training workshops, "
        "and affordable monitoring tools — are the most requested forms of support from pharmacists."
    ]
    for i, c in enumerate(conclusions, 1):
        story.append(Paragraph(f"<b>{i}.</b> {c}", body_style))

    # ── Footer ──
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#c0dde6")))
    story.append(Paragraph(
        f"Generated: {now} | Sunyani Technical University — Department of Pharmacy | "
        "Confidential — For Academic Research Only",
        right_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def page_report():
    st.markdown("## 📄 Research Report Generation")
    st.markdown("""
    <div class="info-banner">
        📊 &nbsp; Generate a comprehensive PDF research report from all collected survey responses.
        The report includes summary statistics, compliance analysis, quality incident data,
        and pharmacist-reported recommendations — formatted for academic submission.
    </div>
    """, unsafe_allow_html=True)

    df = fetch_all()
    if df.empty:
        st.warning("📭 No survey responses available yet. Please collect data first.")
        return

    n = len(df)
    st.info(f"📋 **{n} responses** are available for the report.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Report will include:**")
        st.markdown("""
        - ✅ Executive Summary with key statistics
        - 🏪 Pharmacy & Pharmacist Profile
        - 🌡️ Temperature & Humidity Analysis
        - ✅ WHO GSP Compliance Assessment
        - ⚠️ Drug Quality Incident Summary
        - 🚧 Challenges & Support Needs
        - 💡 Policy Recommendations from Pharmacists
        - 📊 Conclusions & Research Implications
        """)
    with col2:
        st.markdown("**Quick Stats Preview:**")
        st.metric("Total Responses", n)
        st.metric("% With AC", f"{df['has_ac'].mean()*100:.0f}%")
        st.metric("% GSP Trained", f"{df['gsp_training_received'].mean()*100:.0f}%")
        st.metric("% Observed Degradation", f"{df['observed_degradation'].mean()*100:.0f}%")

    st.markdown("---")
    if st.button("📥 Generate & Download PDF Report", use_container_width=True, type="primary"):
        with st.spinner("Building comprehensive research report..."):
            pdf_bytes = build_pdf_report(df)
        filename = f"Drug_Storage_Survey_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        st.download_button(
            label="⬇️ Click Here to Download PDF Report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True
        )
        st.success("✅ Report generated successfully! Click the button above to download.")

    st.markdown("---")
    st.markdown("### 📊 Export Raw Data")
    col1, col2 = st.columns(2)
    with col1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download All Responses (CSV)",
            data=csv,
            file_name=f"pharmacy_survey_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col2:
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Survey Data")
        excel_buf.seek(0)
        st.download_button(
            "⬇️ Download All Responses (Excel)",
            data=excel_buf.getvalue(),
            file_name=f"pharmacy_survey_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )


# ─────────────────────────────────────────────
# PAGE: RESPONSES
# ─────────────────────────────────────────────
def page_responses():
    df = fetch_all()
    if df.empty:
        st.info("📭 No responses submitted yet.")
        return

    st.markdown(f"### 📋 All Submitted Responses &nbsp; — &nbsp; {len(df)} total")

    # Search
    search = st.text_input("🔍 Search by pharmacy or pharmacist name", "")
    if search:
        mask = (df["pharmacy_name"].str.contains(search, case=False, na=False) |
                df["pharmacist_name"].str.contains(search, case=False, na=False))
        df = df[mask]

    show = df[["id","submitted_at","pharmacy_name","pharmacist_name",
               "pharmacy_type","location_type","self_compliance_rating","observed_degradation"]].copy()
    show["observed_degradation"] = show["observed_degradation"].map({1:"✅ Yes", 0:"❌ No"})
    show.columns = ["ID","Submitted At","Pharmacy","Pharmacist",
                    "Type","Location","Compliance Rating","Degradation?"]
    st.dataframe(show, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### 🔍 View or Delete a Response")
    rid = st.number_input("Enter Response ID", min_value=1, step=1, key="rid_input")
    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if st.button("👁️ View"):
            full_df = fetch_all()
            row = full_df[full_df["id"] == rid]
            if row.empty:
                st.error(f"No response found with ID {rid}.")
            else:
                r = row.iloc[0]
                st.success(f"Showing details for **{r['pharmacy_name']}** — submitted {r['submitted_at']}")
                st.json({k: str(v) for k, v in r.items() if k != "id"})
    with c2:
        if st.button("🗑️ Delete", type="secondary"):
            full_df = fetch_all()
            row = full_df[full_df["id"] == rid]
            if row.empty:
                st.error(f"No response found with ID {rid}.")
            else:
                delete_response(int(rid))
                st.success(f"Response ID {rid} deleted successfully.")
                st.rerun()

# ─────────────────────────────────────────────
# PAGE: ABOUT
# ─────────────────────────────────────────────
def page_about():
    # Live DB status check
    ok = check_connection()
    if ok:
        st.markdown('<div class="db-status-ok">🟢 &nbsp; <strong>Database Connected</strong> — Supabase (PostgreSQL) is active and reachable.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="db-status-err">🔴 &nbsp; <strong>Database Unavailable</strong> — Check your DATABASE_URL secret in Streamlit Cloud settings.</div>', unsafe_allow_html=True)

    st.markdown("""
    ## 📖 About This Survey System

    > **"Evaluation of Storage Conditions of Drugs in Community Pharmacies and
    > Their Influence on Drug Potency and Shelf Life in the Sunyani Municipality, Ghana"**

    ---
    ### 🎓 Academic Details

    | | |
    |---|---|
    | **Institution** | Sunyani Technical University |
    | **Department** | Department of Pharmacy |
    | **Supervisor** | Mrs. Lydia Sarfo Mainoo |
    | **Researchers** | Obeng Theophilus (STUBTECH220600) · Yussif Asmau (STUBTECH220592) · Egawu Naomi (STUBTECH220598) |
    | **Period** | March 2026 |

    ---
    ### ⚙️ Technical Stack

    | Component | Technology |
    |-----------|------------|
    | User Interface | Streamlit Cloud |
    | Database | Supabase (PostgreSQL) |
    | Charts | Plotly (interactive, 17 chart types) |
    | Reports | ReportLab PDF |
    | Language | Python 3.x |

    ---
    ### 🔧 Supabase Setup (Step-by-Step)

    **Step 1 — Create a Supabase Project**
    1. Go to [supabase.com](https://supabase.com) and sign up / log in.
    2. Click **New Project**, choose a name and region (pick one closest to Ghana).
    3. Note your project **URL** and **API keys** from *Settings → API*.

    **Step 2 — Create the Database Table**
    1. In your Supabase dashboard, go to **SQL Editor**.
    2. Paste and run the contents of `supabase_schema.sql` (provided alongside this file).
    3. Verify the `responses` table appears in *Table Editor*.

    **Step 3 — Get your Connection String**
    1. Go to *Settings → Database → Connection String → URI*.
    2. Copy the URI — it looks like:
       `postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres`

    **Step 4 — Configure Streamlit Cloud Secrets**
    1. In Streamlit Cloud, open your app → **Settings → Secrets**.
    2. Add:
    ```toml
    DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres"
    ```
    3. For local development, create `.streamlit/secrets.toml` with the same content.

    ---
    ### 🚀 Deploying on Streamlit Cloud

    1. Push this project to a **GitHub repository**.
    2. Go to [share.streamlit.io](https://share.streamlit.io) → **New App**.
    3. Connect your GitHub repo and set `app.py` as the entry file.
    4. Add your Supabase `DATABASE_URL` in the Secrets section.
    5. Click **Deploy** — your survey will be live and publicly accessible!

    ---
    ### 📋 Survey Sections

    | Section | Coverage |
    |---------|----------|
    | A | Pharmacy & Pharmacist Profile |
    | B | Physical Storage Conditions & Facilities |
    | C | Temperature & Humidity Monitoring |
    | D | Drug Handling & WHO GSP Compliance |
    | E | Observed Drug Quality & Potency Issues |
    | F | Challenges & Recommendations |

    ---
    ### 🔒 Data Privacy
    All responses are stored securely in Supabase (PostgreSQL with row-level encryption).
    Data is used exclusively for academic research.
    Respondent identities are handled with strict confidentiality.
    """)

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

st.sidebar.markdown("""
<div style="margin-top:18px; font-size:0.76em; color:#999; text-align:center; line-height:1.6;">
    <b>Backend:</b> Supabase (PostgreSQL)<br>
    <b>Frontend:</b> Streamlit Cloud<br><br>
    <b>Run locally:</b><br>
    <code>streamlit run app.py</code>
</div>
""", unsafe_allow_html=True)

# ── Route ─────────────────────────────────────
if   "Fill Survey"    in page: page_survey()
elif "Dashboard"      in page: page_dashboard()
elif "Generate Report" in page: page_report()
elif "View Responses" in page: page_responses()
elif "About"          in page: page_about()
