"""
Drug Storage Conditions Survey
Sunyani Technical University — Department of Pharmacy
Upgraded: Supabase backend · Admin panel · Rich analytics · Thesis report export
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import os
from datetime import datetime
from io import BytesIO

# ── Supabase client ─────────────────────────────────────────────
from supabase import create_client, Client

# Pull credentials from Streamlit secrets (set in .streamlit/secrets.toml or Streamlit Cloud)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = get_supabase()

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Drug Storage Survey | STU",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
PURPLE = "#7B2D8B"
ROSE   = "#E63946"

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
    .admin-banner {
        background: linear-gradient(135deg, #21295C, #065A82);
        color: white;
        padding: 18px 24px;
        border-radius: 10px;
        margin-bottom: 20px;
        font-size: 0.95em;
        border-left: 6px solid #F9C74F;
    }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SUPABASE HELPERS
# ─────────────────────────────────────────────
def insert_response(data: dict) -> bool:
    """Insert a survey response and trigger the Supabase Edge Function for thank-you email."""
    try:
        supabase.table("responses").insert(data).execute()
        # Trigger thank-you email via Supabase Edge Function (if email provided)
        email = data.get("pharmacist_email", "").strip()
        name  = data.get("pharmacist_name", "Pharmacist").strip()
        if email:
            try:
                supabase.functions.invoke(
                    "send-thankyou-email",
                    invoke_options={"body": {"to": email, "name": name}}
                )
            except Exception:
                pass  # Email failure should not block submission
        return True
    except Exception as e:
        st.error(f"Database error: {e}")
        return False


def fetch_all() -> pd.DataFrame:
    try:
        res = supabase.table("responses").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return pd.DataFrame()


def delete_response(rid: int):
    supabase.table("responses").delete().eq("id", rid).execute()


def response_count() -> int:
    try:
        res = supabase.table("responses").select("id", count="exact").execute()
        return res.count or 0
    except Exception:
        return 0


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$", email))


# ─────────────────────────────────────────────
# ADMIN AUTH
# ─────────────────────────────────────────────
ADMIN_PASSWORD = "kwame"

def require_admin() -> bool:
    """Returns True if admin is authenticated for this session."""
    if st.session_state.get("admin_authenticated"):
        return True
    st.markdown('<div class="admin-banner">🔐 <b>Admin Panel</b> — Restricted Access</div>', unsafe_allow_html=True)
    pwd = st.text_input("Enter admin password", type="password", key="admin_pwd_input")
    if st.button("🔓 Unlock Admin Panel"):
        if pwd == ADMIN_PASSWORD:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect password. Access denied.")
    return False


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
def render_header():
    st.markdown("""
    <div class="main-header">
        <h1>💊 Drug Storage Conditions Survey</h1>
        <p><strong>Sunyani Technical University</strong> &nbsp;|&nbsp; Department of Pharmacy</p>
        <p style="font-size:0.80em; opacity:0.75; margin-top:6px;">
            Evaluation of Storage Conditions of Drugs in Community Pharmacies and Their
            Influence on Drug Potency and Shelf Life in the Sunyani Municipality, Ghana &mdash; 2026
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
            pharmacist_email = st.text_input("Email Address (optional — for thank-you message)", placeholder="name@example.com")
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
            has_ac           = st.radio("Air Conditioning Unit *", ["Yes", "No"], horizontal=True)
            has_refrigerator = st.radio("Functional Refrigerator *", ["Yes", "No"], horizontal=True)
        with col2:
            has_thermometer  = st.radio("Room Thermometer *", ["Yes", "No"], horizontal=True)
            has_hygrometer   = st.radio("Hygrometer (Humidity Meter) *", ["Yes", "No"], horizontal=True)
        with col3:
            has_proper_shelving = st.radio("Proper Drug Shelving *", ["Yes", "No"], horizontal=True)
            has_ventilation     = st.radio("Adequate Ventilation *", ["Yes", "No"], horizontal=True)

        col1, col2 = st.columns(2)
        with col1:
            has_direct_sunlight = st.radio("Are any drugs exposed to direct sunlight? *", ["Yes", "No"], horizontal=True)
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
            ["Yes", "No"], horizontal=True
        )

        # ── SECTION D ──────────────────────────────────────────
        st.markdown('<div class="section-card"><div class="section-title">✅ Section D — Drug Handling & WHO Good Storage Practice (GSP) Compliance</div></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            gsp_training_received = st.radio(
                "Have you received training on WHO Good Storage Practices (GSP)? *",
                ["Yes", "No"], horizontal=True
            )
            last_training_year = st.selectbox("If yes — when was your most recent training?", [
                "N/A — No training received", "2024 – 2025",
                "2021 – 2023", "2018 – 2020", "Before 2018"
            ])
            practises_fifo = st.radio(
                "Do you practise First-In-First-Out (FIFO) stock rotation? *",
                ["Yes", "No", "Sometimes"], horizontal=True
            )
        with col2:
            checks_expiry = st.radio(
                "Do you regularly inspect stock for expiry dates? *",
                ["Yes", "No", "Sometimes"], horizontal=True
            )
            segregates_thermolabile = st.radio(
                "Are temperature-sensitive drugs (e.g. insulin, vaccines, suppositories) stored separately under cold conditions? *",
                ["Yes", "No", "Not Applicable"], horizontal=True
            )
            fda_inspected = st.radio(
                "Has your pharmacy been inspected by the FDA Ghana in the last 2 years? *",
                ["Yes", "No"], horizontal=True
            )
        self_compliance_rating = st.select_slider(
            "How would you rate your pharmacy's overall compliance with WHO Good Storage Practices? *",
            options=["Very Poor", "Poor", "Fair", "Good", "Excellent"], value="Fair"
        )

        # ── SECTION E ──────────────────────────────────────────
        st.markdown('<div class="section-card"><div class="section-title">⚠️ Section E — Observed Drug Quality & Potency Issues</div></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            observed_degradation = st.radio(
                "Have you ever observed physical signs of drug degradation (melting, crystallisation, caking, unusual smell)? *",
                ["Yes", "No"], horizontal=True
            )
            degradation_drug_types = st.multiselect(
                "If yes — which drug types were affected? (select all that apply)",
                ["Antibiotics (tablets/capsules)", "Syrups / Oral liquids", "Antimalarials",
                 "Antihypertensives", "Injectables / Vaccines",
                 "Suppositories / Pessaries", "Topical creams / ointments", "Other"]
            )
            observed_color_change = st.radio(
                "Have you noticed unusual colour change or discolouration in any drug? *",
                ["Yes", "No"], horizontal=True
            )
        with col2:
            potency_complaints = st.radio(
                "Have patients ever complained that a medicine 'was not working' or appeared ineffective? *",
                ["Yes", "No"], horizontal=True
            )
            returned_stock_quality = st.radio(
                "Have you returned or discarded drug stock due to suspected quality deterioration? *",
                ["Yes", "No"], horizontal=True
            )
            num_quality_incidents = st.selectbox(
                "Approximately how many drug quality incidents in the last 12 months? *",
                ["-- Select --", "None", "1 – 3", "4 – 6", "7 – 10", "More than 10"]
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
            if not pharmacy_name.strip():        errors.append("Pharmacy name is required.")
            if not pharmacist_name.strip():      errors.append("Pharmacist name is required.")
            if not reg_number.strip():           errors.append("Registration number is required.")
            if pharmacist_email.strip() and not is_valid_email(pharmacist_email):
                errors.append("Please enter a valid email address (e.g. name@gmail.com).")
            dropdowns = {
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
            }
            for label, val in dropdowns.items():
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
                    "segregates_thermolabile": segregates_thermolabile,
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
                ok = insert_response(data)
                if ok:
                    email_note = " A thank-you message has been sent to your email." if pharmacist_email.strip() else ""
                    st.markdown(f"""
                    <div class="success-box">
                        <h2>✅ Response Submitted Successfully!</h2>
                        <p style="color:#065A82; font-size:1.05em;">
                            Thank you for completing this survey.{email_note}<br>
                            Your contribution is vital to improving drug storage practices
                            and patient safety in the Sunyani Municipality.
                        </p>
                        <p style="font-size:0.82em; color:#888; margin-top:12px;">
                            Sunyani Technical University — Department of Pharmacy, 2026
                        </p>
                    </div>
                    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────
def page_dashboard():
    df = fetch_all()

    if df.empty:
        st.warning("📭 No survey responses yet. Share the survey link with pharmacists to collect data.")
        return

    # Ensure numeric types
    bool_cols = ["has_ac","has_refrigerator","has_thermometer","has_hygrometer",
                 "has_proper_shelving","has_ventilation","has_direct_sunlight",
                 "has_written_sop","gsp_training_received","fda_inspected",
                 "observed_degradation","observed_color_change","potency_complaints",
                 "returned_stock_quality"]
    for c in bool_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    n = len(df)

    # ── KPI TILES ──────────────────────────────────────────────
    st.markdown("### 📈 Research Summary — Key Metrics")
    cols = st.columns(6)
    kpis = [
        ("Total Responses",        str(n)),
        ("Have Air Conditioning",  f"{df['has_ac'].mean()*100:.0f}%"),
        ("Have Thermometer",       f"{df['has_thermometer'].mean()*100:.0f}%"),
        ("GSP Trained",            f"{df['gsp_training_received'].mean()*100:.0f}%"),
        ("Observed Degradation",   f"{df['observed_degradation'].mean()*100:.0f}%"),
        ("Have Written SOP",       f"{df['has_written_sop'].mean()*100:.0f}%"),
    ]
    for col, (label, val) in zip(cols, kpis):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # CHART 1: Horizontal Bar — Equipment Availability
    # ══════════════════════════════════════════
    col1, col2 = st.columns(2)
    with col1:
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
                      annotation_text="70% Benchmark", annotation_position="top right",
                      annotation_font_size=11)
        fig.update_layout(
            title=dict(text="📦 Storage Equipment Availability<br><sup>Green ≥70% adequate | Red = below benchmark</sup>", font_size=14),
            xaxis=dict(title="% of Pharmacies", range=[0,118]),
            yaxis_title="", height=390,
            margin=dict(l=10, r=20, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("🔑 Red bars indicate critical compliance gaps that directly risk drug quality.")

    # ══════════════════════════════════════════
    # CHART 2: Donut — Temperature Ranges
    # ══════════════════════════════════════════
    with col2:
        temp_short = {
            "Below 25°C  (WHO Optimal)":    "< 25°C ✅ Optimal",
            "25°C – 30°C  (Acceptable)":    "25–30°C ⚠️ Acceptable",
            "30°C – 35°C  (Risk Zone)":     "30–35°C 🔶 Risk Zone",
            "Above 35°C  (High Risk)":      "> 35°C 🔴 High Risk",
            "Not monitored / Unknown":       "Unknown"
        }
        df["temp_label"] = df["usual_temp_range"].map(temp_short).fillna(df["usual_temp_range"])
        tc = df["temp_label"].value_counts().reset_index()
        tc.columns = ["Range","Count"]

        fig2 = px.pie(tc, values="Count", names="Range", hole=0.44,
                      color_discrete_sequence=[GREEN, TEAL, GOLD, CORAL, SLATE])
        fig2.update_traces(
            textinfo='percent+label',
            hovertemplate='%{label}: %{value} pharmacies (%{percent})<extra></extra>'
        )
        fig2.update_layout(
            title=dict(text="🌡️ Usual Temperature in Storage Areas<br><sup>WHO recommends ≤25–30°C for most medicines</sup>", font_size=14),
            showlegend=False, height=390,
            margin=dict(l=10, r=10, t=85, b=10),
            paper_bgcolor="white"
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("🔑 Pharmacies in orange/red segments store drugs above recommended limits, accelerating degradation.")

    # ══════════════════════════════════════════
    # CHART 3: Stacked Bar — GSP Compliance
    # ══════════════════════════════════════════
    col1, col2 = st.columns(2)
    with col1:
        clabels  = ["GSP Training","Written SOP","FIFO Rotation",
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

        fig3 = go.Figure()
        fig3.add_trace(go.Bar(name="Compliant ✅", x=clabels, y=yes_pcts, marker_color=GREEN,
                              text=[f"{v:.0f}%" for v in yes_pcts], textposition='inside',
                              hovertemplate='%{x}<br>Compliant: %{y:.1f}%<extra></extra>'))
        fig3.add_trace(go.Bar(name="Non-compliant ❌", x=clabels, y=no_pcts, marker_color=CORAL,
                              text=[f"{v:.0f}%" for v in no_pcts], textposition='inside',
                              hovertemplate='%{x}<br>Non-compliant: %{y:.1f}%<extra></extra>'))
        fig3.update_layout(
            barmode='stack',
            title=dict(text="✅ WHO Good Storage Practice (GSP) Compliance<br><sup>Green=Compliant | Red=Non-compliant</sup>", font_size=14),
            yaxis_title="% of Pharmacies", xaxis_tickangle=-20, height=400,
            margin=dict(l=20, r=20, t=85, b=90),
            legend=dict(orientation='h', yanchor='bottom', y=-0.38),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("🔑 Large red segments reveal which GSP practices are most neglected.")

    # ══════════════════════════════════════════
    # CHART 4: Pie — Humidity Ranges
    # ══════════════════════════════════════════
    with col2:
        hum_short = {
            "Below 45% RH  (Low)":           "< 45% RH (Low)",
            "45% – 65% RH  (Optimal)":       "45–65% ✅ Optimal",
            "65% – 75% RH  (Elevated Risk)": "65–75% ⚠️ Elevated",
            "Above 75% RH  (High Risk)":     "> 75% 🔴 High Risk",
            "Not monitored / Unknown":        "Unknown"
        }
        df["hum_label"] = df["usual_humidity_range"].map(hum_short).fillna(df["usual_humidity_range"])
        hc = df["hum_label"].value_counts().reset_index()
        hc.columns = ["Humidity","Count"]

        fig4 = px.pie(hc, values="Count", names="Humidity", hole=0,
                      color_discrete_sequence=[TEAL, GREEN, GOLD, CORAL, SLATE])
        fig4.update_traces(
            textinfo='percent+label',
            hovertemplate='%{label}: %{value} pharmacies (%{percent})<extra></extra>'
        )
        fig4.update_layout(
            title=dict(text="💧 Relative Humidity in Storage Areas<br><sup>Optimal: 45–65% RH</sup>", font_size=14),
            showlegend=False, height=400,
            margin=dict(l=10, r=10, t=85, b=10),
            paper_bgcolor="white"
        )
        st.plotly_chart(fig4, use_container_width=True)
        st.caption("🔑 High humidity (>65% RH) accelerates moisture-induced degradation in antibiotics and oral solids.")

    # ══════════════════════════════════════════
    # CHART 5: Radar — Drug Quality Risk Profile
    # ══════════════════════════════════════════
    col1, col2 = st.columns(2)
    with col1:
        cats  = ["Degradation Observed","Colour Changes","Potency Complaints",
                 "Returned Stock","No SOP","No Thermometer"]
        rvals = [
            df["observed_degradation"].mean()*100,
            df["observed_color_change"].mean()*100,
            df["potency_complaints"].mean()*100,
            df["returned_stock_quality"].mean()*100,
            (1-df["has_written_sop"].mean())*100,
            (1-df["has_thermometer"].mean())*100,
        ]
        fig5 = go.Figure(go.Scatterpolar(
            r=rvals+[rvals[0]], theta=cats+[cats[0]], fill='toself',
            fillcolor="rgba(249,97,103,0.20)", line=dict(color=CORAL, width=2.5),
            hovertemplate='%{theta}: %{r:.1f}%<extra></extra>'
        ))
        fig5.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0,100], ticksuffix="%", tickfont_size=10)),
            title=dict(text="🕸️ Drug Quality Risk Profile<br><sup>Larger area = broader systemic risk</sup>", font_size=14),
            height=410, showlegend=False,
            margin=dict(l=60, r=60, t=85, b=60),
            paper_bgcolor="white"
        )
        st.plotly_chart(fig5, use_container_width=True)
        st.caption("🔑 Points near the outer edge signal critical problems requiring urgent attention.")

    # ══════════════════════════════════════════
    # CHART 6: Bar — Self-Rated Compliance
    # ══════════════════════════════════════════
    with col2:
        order = ["Very Poor","Poor","Fair","Good","Excellent"]
        rc = df["self_compliance_rating"].value_counts().reindex(order, fill_value=0).reset_index()
        rc.columns = ["Rating","Count"]
        pct = (rc["Count"]/n*100).round(1)
        c_map = {"Very Poor":CORAL,"Poor":AMBER,"Fair":GOLD,"Good":TEAL,"Excellent":GREEN}
        bcolors = [c_map[r] for r in rc["Rating"]]

        fig6 = go.Figure(go.Bar(
            x=rc["Rating"], y=rc["Count"],
            marker_color=bcolors,
            text=[f"{c}<br>({p}%)" for c,p in zip(rc["Count"],pct)],
            textposition='outside',
            hovertemplate='%{x}: %{y} pharmacies<extra></extra>'
        ))
        fig6.update_layout(
            title=dict(text="🌟 Pharmacists' Self-Rated GSP Compliance<br><sup>Self-perception vs objective data</sup>", font_size=14),
            xaxis_title="Rating", yaxis_title="Number of Pharmacies",
            height=410, margin=dict(l=20, r=20, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig6, use_container_width=True)
        st.caption("🔑 Compare self-perception with objective charts to identify knowledge and awareness gaps.")

    # ══════════════════════════════════════════
    # CHART 7: Line — Cumulative Submissions Over Time
    # ══════════════════════════════════════════
    col1, col2 = st.columns(2)
    with col1:
        if "submitted_at" in df.columns:
            df["submitted_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
            daily = df.dropna(subset=["submitted_dt"]).groupby(df["submitted_dt"].dt.date).size().reset_index()
            daily.columns = ["Date","Count"]
            daily = daily.sort_values("Date")
            daily["Cumulative"] = daily["Count"].cumsum()

            fig7 = go.Figure()
            fig7.add_trace(go.Scatter(
                x=daily["Date"], y=daily["Cumulative"],
                mode='lines+markers',
                line=dict(color=TEAL, width=3),
                marker=dict(size=8, color=GREEN, line=dict(width=2, color=NAVY)),
                fill='tozeroy', fillcolor="rgba(2,128,144,0.12)",
                hovertemplate='%{x}: %{y} total responses<extra></extra>',
                name="Cumulative"
            ))
            fig7.add_trace(go.Bar(
                x=daily["Date"], y=daily["Count"],
                marker_color=MINT, opacity=0.6,
                name="Daily", hovertemplate='%{x}: %{y} new<extra></extra>'
            ))
            fig7.update_layout(
                title=dict(text="📅 Survey Submission Trend<br><sup>Daily count and cumulative total</sup>", font_size=14),
                xaxis_title="Date", yaxis_title="Responses",
                height=390, margin=dict(l=20, r=20, t=85, b=40),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation='h', yanchor='bottom', y=-0.3)
            )
            st.plotly_chart(fig7, use_container_width=True)
            st.caption("🔑 Tracks data collection momentum — useful for fieldwork monitoring and methodology documentation.")

    # ══════════════════════════════════════════
    # CHART 8: Bar — Temperature Monitoring Frequency
    # ══════════════════════════════════════════
    with col2:
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

        fig8 = go.Figure(go.Bar(
            x=fc["Frequency"], y=fc["Count"],
            marker_color=f_colors,
            text=fc["Count"], textposition='outside',
            hovertemplate='%{x}: %{y} pharmacies<extra></extra>'
        ))
        fig8.update_layout(
            title=dict(text="🕐 Temperature Monitoring Frequency<br><sup>WHO GSP requires minimum once-daily recording</sup>", font_size=14),
            xaxis_title="Monitoring Frequency", yaxis_title="Number of Pharmacies",
            height=390, margin=dict(l=20, r=20, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig8, use_container_width=True)
        st.caption("🔑 Infrequent or absent monitoring means temperature excursions go undetected, silently degrading potency.")

    # ══════════════════════════════════════════
    # CHART 9: Funnel — Drug Quality Incidents
    # ══════════════════════════════════════════
    col1, col2 = st.columns(2)
    with col1:
        inc_order = ["None","1 – 3","4 – 6","7 – 10","More than 10"]
        ic = df["num_quality_incidents"].value_counts().reindex(inc_order, fill_value=0).reset_index()
        ic.columns = ["Incidents","Count"]

        fig9 = go.Figure(go.Funnel(
            y=ic["Incidents"], x=ic["Count"],
            textinfo="value+percent initial",
            marker=dict(color=[GREEN, TEAL, GOLD, AMBER, CORAL]),
            connector=dict(line=dict(color=NAVY, width=1.5)),
            hovertemplate='%{y}: %{x} pharmacies<extra></extra>'
        ))
        fig9.update_layout(
            title=dict(text="🔻 Drug Quality Incidents — Last 12 Months<br><sup>Funnel shows proportion of pharmacies per incident band</sup>", font_size=14),
            height=400, margin=dict(l=20, r=20, t=85, b=20),
            paper_bgcolor="white"
        )
        st.plotly_chart(fig9, use_container_width=True)
        st.caption("🔑 Higher incident bands signal systemic storage failures requiring urgent regulatory attention.")

    # ══════════════════════════════════════════
    # CHART 10: Scatter — Experience vs Compliance
    # ══════════════════════════════════════════
    with col2:
        rating_num = {"Very Poor":1,"Poor":2,"Fair":3,"Good":4,"Excellent":5}
        df["compliance_num"] = df["self_compliance_rating"].map(rating_num)
        scatter_df = df.dropna(subset=["years_experience","compliance_num"])

        fig10 = px.scatter(
            scatter_df, x="years_experience", y="compliance_num",
            color="pharmacy_type",
            color_discrete_sequence=[TEAL, GREEN, CORAL, GOLD, NAVY],
            labels={"years_experience":"Years of Experience","compliance_num":"Compliance Rating (1–5)","pharmacy_type":"Type"},
            hover_data=["pharmacy_name","self_compliance_rating"],
            trendline="ols"
        )
        fig10.update_layout(
            title=dict(text="🔬 Experience vs Self-Rated GSP Compliance<br><sup>Scatter with trend line per pharmacy type</sup>", font_size=14),
            yaxis=dict(tickvals=[1,2,3,4,5], ticktext=["Very Poor","Poor","Fair","Good","Excellent"]),
            height=400, margin=dict(l=20, r=20, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig10, use_container_width=True)
        st.caption("🔑 Reveals whether more experienced pharmacists self-report higher compliance — useful for training policy.")

    # ══════════════════════════════════════════
    # CHART 11 & 12: Pie charts — Challenges & Support
    # ══════════════════════════════════════════
    st.markdown("### 🚧 Identified Barriers & Support Needs")
    col1, col2 = st.columns(2)

    with col1:
        ch_short = {
            "Frequent power outages / erratic electricity supply":  "Power Outages",
            "High cost of air conditioning or refrigeration":        "High Equipment Cost",
            "Small or inadequate storage space":                     "Inadequate Space",
            "Lack of temperature/humidity monitoring equipment":     "No Monitoring Equipment",
            "Limited training and awareness on GSP":                 "Limited GSP Training",
            "Insufficient regulatory inspection and enforcement":    "Weak Regulation",
            "Financial constraints to upgrade facilities":           "Financial Constraints"
        }
        df["chall_short"] = df["biggest_challenge"].map(ch_short).fillna(df["biggest_challenge"])
        ch = df["chall_short"].value_counts().sort_values().reset_index()
        ch.columns = ["Challenge","Count"]

        fig11 = px.bar(ch, x="Count", y="Challenge", orientation='h',
                       color="Count",
                       color_continuous_scale=[[0,MINT],[0.5,TEAL],[1,NAVY]],
                       text="Count")
        fig11.update_traces(textposition='outside',
                            hovertemplate='%{y}: %{x} pharmacies<extra></extra>')
        fig11.update_layout(
            title=dict(text="🚧 Biggest Challenges to Proper Drug Storage<br><sup>As reported by pharmacists</sup>", font_size=14),
            showlegend=False, coloraxis_showscale=False,
            xaxis_title="Number of Pharmacies", yaxis_title="",
            height=400, margin=dict(l=10, r=30, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white"
        )
        st.plotly_chart(fig11, use_container_width=True)
        st.caption("🔑 Longest bars identify most common barriers — essential for targeted policy and infrastructure interventions.")

    with col2:
        sup_short = {
            "Subsidised air conditioning and refrigeration equipment": "Subsidised Equipment",
            "Regular GSP training workshops":                          "GSP Training Workshops",
            "Affordable data loggers or thermometers":                 "Affordable Monitoring Tools",
            "More frequent FDA inspections and guidance":              "More FDA Inspections",
            "Financial support / grants for facility upgrades":        "Financial Grants",
            "National policy changes and stricter enforcement":        "Policy & Enforcement Reform"
        }
        df["sup_short"] = df["support_needed"].map(sup_short).fillna(df["support_needed"])
        sp = df["sup_short"].value_counts().reset_index()
        sp.columns = ["Support","Count"]

        fig12 = px.pie(sp, values="Count", names="Support", hole=0.40,
                       color_discrete_sequence=[TEAL, GREEN, NAVY, CORAL, GOLD, SLATE])
        fig12.update_traces(
            textinfo='percent+label',
            hovertemplate='%{label}: %{value} pharmacies (%{percent})<extra></extra>'
        )
        fig12.update_layout(
            title=dict(text="🤝 Type of Support Most Needed<br><sup>Pharmacists' top requested interventions</sup>", font_size=14),
            showlegend=False, height=400,
            margin=dict(l=10, r=10, t=85, b=10),
            paper_bgcolor="white"
        )
        st.plotly_chart(fig12, use_container_width=True)
        st.caption("🔑 Dominant segments reveal what pharmacists believe would most improve storage quality.")

    # ══════════════════════════════════════════
    # CHART 13: Heatmap — Location × Equipment
    # ══════════════════════════════════════════
    st.markdown("### 🗺️ Geographic & Facility Cross-Analysis")
    equip_keys   = ["has_ac","has_refrigerator","has_thermometer","has_hygrometer",
                    "has_proper_shelving","has_ventilation"]
    equip_labels = ["AC","Refrigerator","Thermometer","Hygrometer","Shelving","Ventilation"]

    hm_rows = []
    for loc in df["location_type"].dropna().unique():
        sub = df[df["location_type"]==loc]
        hm_rows.append([round(sub[k].mean()*100,1) for k in equip_keys])

    locs = df["location_type"].dropna().unique().tolist()
    if locs:
        fig13 = go.Figure(go.Heatmap(
            z=hm_rows, x=equip_labels, y=locs,
            colorscale=[[0,CORAL],[0.5,GOLD],[1,GREEN]],
            text=[[f"{v}%" for v in row] for row in hm_rows],
            texttemplate="%{text}",
            hovertemplate='%{y} — %{x}: %{z:.1f}%<extra></extra>',
            colorbar=dict(title="% with equipment")
        ))
        fig13.update_layout(
            title=dict(text="🗺️ Equipment Availability by Location Type<br><sup>Green = high availability | Red = low</sup>", font_size=14),
            height=350, margin=dict(l=20, r=20, t=85, b=20),
            paper_bgcolor="white"
        )
        st.plotly_chart(fig13, use_container_width=True)
        st.caption("🔑 Rural pharmacies typically show lower equipment coverage — highlights geographic equity gaps in drug storage infrastructure.")

    # ══════════════════════════════════════════
    # CHART 14: Grouped Bar — Pharmacy Type Analysis
    # ══════════════════════════════════════════
    qual_indicators = ["observed_degradation","observed_color_change","potency_complaints","returned_stock_quality"]
    qual_labels     = ["Degradation","Colour Change","Potency Complaints","Returned Stock"]
    types = df["pharmacy_type"].dropna().unique().tolist()

    if types:
        fig14 = go.Figure()
        palette = [TEAL, GREEN, CORAL, GOLD, NAVY, AMBER]
        for i, ptype in enumerate(types):
            sub = df[df["pharmacy_type"]==ptype]
            vals14 = [round(sub[k].mean()*100,1) for k in qual_indicators]
            fig14.add_trace(go.Bar(
                name=ptype, x=qual_labels, y=vals14,
                marker_color=palette[i % len(palette)],
                text=[f"{v}%" for v in vals14], textposition='outside',
                hovertemplate=f'{ptype}<br>%{{x}}: %{{y}}%<extra></extra>'
            ))
        fig14.update_layout(
            barmode='group',
            title=dict(text="🏥 Drug Quality Issues by Pharmacy Type<br><sup>Grouped bar showing % reporting each issue</sup>", font_size=14),
            yaxis_title="% Reporting Issue", xaxis_title="Quality Indicator",
            height=430, margin=dict(l=20, r=20, t=85, b=20),
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation='h', yanchor='bottom', y=-0.35)
        )
        st.plotly_chart(fig14, use_container_width=True)
        st.caption("🔑 Compares drug quality problem rates across pharmacy types — informs type-specific regulatory interventions.")


# ─────────────────────────────────────────────
# PAGE: RESPONSES (Admin Only)
# ─────────────────────────────────────────────
def page_responses():
    if not require_admin():
        return

    df = fetch_all()
    if df.empty:
        st.info("📭 No responses submitted yet.")
        return

    st.markdown(f"### 📋 All Submitted Responses &nbsp; — &nbsp; {len(df)} total")

    show_cols = ["id","submitted_at","pharmacy_name","pharmacist_name",
                 "pharmacy_type","location_type","self_compliance_rating","observed_degradation"]
    show_cols = [c for c in show_cols if c in df.columns]
    show = df[show_cols].copy()
    if "observed_degradation" in show.columns:
        show["observed_degradation"] = show["observed_degradation"].map({1:"✅ Yes", 0:"❌ No"})
    show.columns = ["ID","Submitted At","Pharmacy","Pharmacist",
                    "Type","Location","Compliance Rating","Degradation?"][:len(show_cols)]
    st.dataframe(show, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### 🔍 View or Delete a Response")
    rid = st.number_input("Enter Response ID", min_value=1, step=1, key="rid_input")
    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if st.button("👁️ View"):
            row = df[df["id"] == rid]
            if row.empty:
                st.error(f"No response found with ID {rid}.")
            else:
                r = row.iloc[0]
                st.success(f"Showing details for **{r['pharmacy_name']}** — submitted {r['submitted_at']}")
                st.json({k: str(v) for k, v in r.items() if k != "id"})
    with c2:
        if st.button("🗑️ Delete", type="secondary"):
            row = df[df["id"] == rid]
            if row.empty:
                st.error(f"No response found with ID {rid}.")
            else:
                delete_response(int(rid))
                st.success(f"Response ID {rid} deleted successfully.")
                st.rerun()

    st.markdown("---")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download All Responses as CSV",
        data=csv,
        file_name=f"pharmacy_survey_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ─────────────────────────────────────────────
# PAGE: THESIS REPORT (Admin Only)
# ─────────────────────────────────────────────
def page_report():
    if not require_admin():
        return

    df = fetch_all()
    if df.empty:
        st.warning("📭 No data available. Submit responses first.")
        return

    bool_cols = ["has_ac","has_refrigerator","has_thermometer","has_hygrometer",
                 "has_proper_shelving","has_ventilation","has_direct_sunlight",
                 "has_written_sop","gsp_training_received","fda_inspected",
                 "observed_degradation","observed_color_change","potency_complaints",
                 "returned_stock_quality"]
    for c in bool_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    n = len(df)
    now = datetime.now().strftime("%d %B %Y, %H:%M")

    st.markdown(f"""
    ## 📄 Thesis Research Report
    **Generated:** {now} &nbsp;|&nbsp; **Total Responses:** {n}
    ---
    """)

    # ── 1. Descriptive Summary ──────────────────────────────────
    st.markdown("### 1. Descriptive Statistics — Respondent Profile")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Pharmacy Type Distribution**")
        pt = df["pharmacy_type"].value_counts().reset_index()
        pt.columns = ["Type","Count"]
        pt["Percentage"] = (pt["Count"]/n*100).round(1).astype(str) + "%"
        st.dataframe(pt, hide_index=True, use_container_width=True)
    with col2:
        st.markdown("**Location Distribution**")
        lt = df["location_type"].value_counts().reset_index()
        lt.columns = ["Location","Count"]
        lt["Percentage"] = (lt["Count"]/n*100).round(1).astype(str) + "%"
        st.dataframe(lt, hide_index=True, use_container_width=True)
    with col3:
        st.markdown("**Experience Summary**")
        exp_stats = df["years_experience"].describe().round(1)
        st.dataframe(exp_stats.reset_index().rename(columns={"index":"Stat","years_experience":"Years"}),
                     hide_index=True, use_container_width=True)

    # ── 2. Equipment & Infrastructure ──────────────────────────
    st.markdown("### 2. Storage Infrastructure Analysis")
    equip_keys = ["has_ac","has_refrigerator","has_thermometer","has_hygrometer",
                  "has_proper_shelving","has_ventilation"]
    equip_labels = ["Air Conditioning","Refrigerator","Thermometer",
                    "Hygrometer","Proper Shelving","Ventilation"]
    equip_df = pd.DataFrame({
        "Equipment": equip_labels,
        "Count with Equipment": [df[k].sum() for k in equip_keys],
        "% of Pharmacies": [f"{df[k].mean()*100:.1f}%" for k in equip_keys],
        "Status": ["✅ Adequate" if df[k].mean()*100 >= 70 else "❌ Below Benchmark" for k in equip_keys]
    })
    st.dataframe(equip_df, hide_index=True, use_container_width=True)

    st.markdown(f"""
    **Interpretation:** Only pharmacies with ≥70% equipment availability are considered adequately equipped.
    Air conditioning is present in {df['has_ac'].mean()*100:.1f}% of sampled pharmacies, which is
    {"above" if df['has_ac'].mean()*100 >= 70 else "**below**"} the 70% benchmark.
    This has direct implications for maintaining WHO-recommended storage temperatures (≤25–30°C).
    """)

    # ── 3. Temperature & Humidity ───────────────────────────────
    st.markdown("### 3. Temperature & Humidity Monitoring")
    temp_risk = df[df["usual_temp_range"].isin(["30°C – 35°C  (Risk Zone)","Above 35°C  (High Risk)"])]
    hum_risk  = df[df["usual_humidity_range"].isin(["65% – 75% RH  (Elevated Risk)","Above 75% RH  (High Risk)"])]
    never_mon = df[df["temp_monitoring_freq"]=="Never monitored"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Pharmacies in Temp Risk Zone", f"{len(temp_risk)} ({len(temp_risk)/n*100:.1f}%)")
    col2.metric("Pharmacies with Elevated Humidity", f"{len(hum_risk)} ({len(hum_risk)/n*100:.1f}%)")
    col3.metric("Never Monitor Temperature", f"{len(never_mon)} ({len(never_mon)/n*100:.1f}%)")

    st.markdown(f"""
    **Finding:** {len(temp_risk)/n*100:.1f}% of pharmacies operate in temperature zones above WHO recommendations.
    Combined with {len(never_mon)/n*100:.1f}% that never monitor temperature, a significant proportion of 
    drug stock in the Sunyani Municipality is at risk of temperature-induced potency degradation.
    """)

    # ── 4. GSP Compliance ───────────────────────────────────────
    st.markdown("### 4. WHO Good Storage Practice (GSP) Compliance")
    gsp_data = {
        "GSP Indicator": ["GSP Training Received","Written SOP Exists","FIFO Practised (Always)",
                          "Expiry Checks Done (Always)","Thermolabile Drugs Segregated","FDA Inspected (2 yrs)"],
        "Compliant (n)": [
            int(df["gsp_training_received"].sum()),
            int(df["has_written_sop"].sum()),
            int((df["practises_fifo"]=="Yes").sum()),
            int((df["checks_expiry"]=="Yes").sum()),
            int((df["segregates_thermolabile"]=="Yes").sum()),
            int(df["fda_inspected"].sum()),
        ]
    }
    gsp_df = pd.DataFrame(gsp_data)
    gsp_df["% Compliant"] = (gsp_df["Compliant (n)"]/n*100).round(1).astype(str) + "%"
    gsp_df["Non-compliant (n)"] = n - gsp_df["Compliant (n)"]
    gsp_df["Compliance Level"] = gsp_df["Compliant (n)"].apply(
        lambda x: "✅ Good" if x/n >= 0.7 else ("⚠️ Moderate" if x/n >= 0.4 else "❌ Poor")
    )
    st.dataframe(gsp_df, hide_index=True, use_container_width=True)

    # ── 5. Drug Quality Outcomes ─────────────────────────────────
    st.markdown("### 5. Observed Drug Quality & Potency Issues")
    quality_data = {
        "Quality Indicator": [
            "Physical Degradation Observed",
            "Unusual Colour Change Noted",
            "Potency Complaints from Patients",
            "Stock Returned/Discarded for Quality",
        ],
        "Yes (n)": [
            int(df["observed_degradation"].sum()),
            int(df["observed_color_change"].sum()),
            int(df["potency_complaints"].sum()),
            int(df["returned_stock_quality"].sum()),
        ]
    }
    qual_df = pd.DataFrame(quality_data)
    qual_df["% of Pharmacies"] = (qual_df["Yes (n)"]/n*100).round(1).astype(str) + "%"
    qual_df["Research Implication"] = [
        "Indicates active drug deterioration in storage",
        "Suggests chemical/physical instability due to storage conditions",
        "Patient-reported reduced efficacy — potential therapeutic failure",
        "Economic loss and quality breach indicator"
    ]
    st.dataframe(qual_df, hide_index=True, use_container_width=True)

    if "degradation_drug_types" in df.columns:
        all_types = []
        for row in df["degradation_drug_types"].dropna():
            all_types.extend([t.strip() for t in str(row).split(",") if t.strip()])
        if all_types:
            from collections import Counter
            type_counts = Counter(all_types)
            type_df = pd.DataFrame(type_counts.items(), columns=["Drug Type","Count"]).sort_values("Count", ascending=False)
            st.markdown("**Drug categories most frequently affected by degradation:**")
            st.dataframe(type_df, hide_index=True, use_container_width=True)

    # ── 6. Key Findings Summary ──────────────────────────────────
    st.markdown("### 6. Key Research Findings")
    st.markdown(f"""
| # | Finding | Value | Implication |
|---|---------|-------|-------------|
| 1 | AC availability | {df['has_ac'].mean()*100:.1f}% | Suboptimal temperature control risk |
| 2 | GSP trained pharmacists | {df['gsp_training_received'].mean()*100:.1f}% | Training gap requiring intervention |
| 3 | Pharmacies with written SOP | {df['has_written_sop'].mean()*100:.1f}% | Procedural compliance deficit |
| 4 | Observed drug degradation | {df['observed_degradation'].mean()*100:.1f}% | Active quality loss in community supply |
| 5 | Potency complaints received | {df['potency_complaints'].mean()*100:.1f}% | Possible therapeutic failure burden |
| 6 | Never monitor temperature | {(df['temp_monitoring_freq']=="Never monitored").mean()*100:.1f}% | Critical monitoring gap |
| 7 | FDA inspected recently | {df['fda_inspected'].mean()*100:.1f}% | Regulatory oversight level |
    """)

    # ── 7. Recommendations ───────────────────────────────────────
    st.markdown("### 7. Policy Recommendations")
    st.markdown("""
**Based on the survey data, the following evidence-based recommendations are proposed:**

1. **Mandatory temperature monitoring equipment** — The FDA Ghana should require all licensed pharmacies to own and use calibrated thermometers and hygrometers as a condition for renewal of operating licenses.

2. **Subsidised air conditioning access** — Government and pharmaceutical associations should partner to subsidise AC installation costs, especially for rural and peri-urban pharmacies where the risk is highest.

3. **Annual WHO GSP refresher training** — Compulsory annual GSP training for registered pharmacists should be mandated by the Pharmacy Council of Ghana, with digital certification.

4. **Standard Operating Procedure (SOP) templates** — The Pharmacy Council should distribute standardised drug storage SOPs that can be immediately adopted by community pharmacies.

5. **Increased FDA inspection frequency** — Current inspection rates appear insufficient. Risk-based inspection scheduling (targeting pharmacies with known temperature risk) should be implemented.

6. **Community pharmacy infrastructure grants** — The Ministry of Health should develop a dedicated grant programme for facility upgrades in resource-limited settings.
    """)

    # ── 8. Policy Recommendations from Respondents ──────────────
    policy_responses = df["policy_recommendation"].dropna()
    policy_responses = policy_responses[policy_responses.str.strip() != ""]
    if not policy_responses.empty:
        st.markdown("### 8. Verbatim Policy Recommendations from Pharmacists")
        for i, rec in enumerate(policy_responses[:20], 1):
            st.markdown(f"**{i}.** _{rec}_")

    # ── Export button ─────────────────────────────────────────────
    st.markdown("---")
    st.info("💡 **Tip for thesis:** Use the CSV download below for SPSS/Excel analysis, and use browser Print → Save as PDF to export this report page.")
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Full Dataset as CSV (for SPSS / Excel analysis)",
        data=csv_data,
        file_name=f"STU_DrugStorageSurvey_Data_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ─────────────────────────────────────────────
# PAGE: ABOUT
# ─────────────────────────────────────────────
def page_about():
    st.markdown("""
    ## 📖 About This Survey System

    This digital platform supports the research study:

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
    | **Period** | 2026 |

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
    ### 🗄️ Infrastructure

    | Component | Technology |
    |-----------|------------|
    | User Interface | Streamlit (hosted on Streamlit Cloud) |
    | Database | Supabase (PostgreSQL) |
    | Charts | Plotly (interactive) |
    | Email Notifications | Supabase Edge Functions (built-in — no third party) |
    | Language | Python 3.x |

    ---
    ### 🚀 Deployment Guide

    **Step 1 — Supabase Setup**
    1. Create a free project at [supabase.com](https://supabase.com)
    2. Run the SQL in `supabase_schema.sql` in the SQL Editor to create the `responses` table
    3. Deploy `send-thankyou-email` Edge Function (see `supabase/functions/send-thankyou-email/index.ts`)
    4. Copy your **Project URL** and **anon key** from Settings → API

    **Step 2 — Streamlit Cloud**
    1. Push this project to a GitHub repository
    2. Go to [share.streamlit.io](https://share.streamlit.io) and link your repo
    3. Add secrets in the Streamlit Cloud dashboard:
    ```toml
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_KEY = "your-anon-key-here"
    ```
    4. Share the generated URL with pharmacists

    ---
    ### 🔒 Data Privacy
    All responses are stored securely in Supabase (PostgreSQL with row-level security).
    Data is used exclusively for academic research.
    Respondent identities are handled with strict confidentiality.
    The Admin Panel is password-protected to prevent unauthorised access.
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
    ["📋  Fill Survey", "📊  Dashboard & Charts", "📁  Responses (Admin)", "📄  Thesis Report (Admin)", "ℹ️  About"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
count = response_count()
st.sidebar.markdown(f"""
<div style="background:linear-gradient(135deg,#028090,#065A82);
            color:white; border-radius:10px; padding:14px; text-align:center;">
    <div style="font-size:2em; font-weight:800;">{count}</div>
    <div style="font-size:0.82em; opacity:0.9;">Responses Collected</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style="margin-top:18px; font-size:0.76em; color:#999; text-align:center; line-height:1.6;">
    <b>Hosted on:</b><br>Streamlit Cloud<br>
    <b>Database:</b><br>Supabase (PostgreSQL)<br><br>
    <b>Admin panel</b> is password protected.
</div>
""", unsafe_allow_html=True)

if   "Fill Survey"   in page: page_survey()
elif "Dashboard"     in page: page_dashboard()
elif "Responses"     in page: page_responses()
elif "Thesis Report" in page: page_report()
elif "About"         in page: page_about()
