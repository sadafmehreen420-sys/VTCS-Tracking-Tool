import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import plotly.express as px

# --- PAGE CONFIG ---
st.set_page_config(page_title="VTCS & GPS Auditor", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR MODERN UI ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTable { background-color: white; border-radius: 10px; }
    .stHeader { color: #1e3d59; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 VTCS & GPS Tracking Analytics")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("📂 Data Upload")
vtcs_file = st.sidebar.file_uploader("1. Upload VTCS Portal Data", type=['xlsx', 'csv'])
tracking_file = st.sidebar.file_uploader("2. Upload Tracking Report", type=['xlsx', 'csv'])

def convert_df_to_csv(df):
    return df.to_csv(index=True if 'Vehicle' in df.index.names else False).encode('utf-8')

def process_audit(vtcs_df, track_df=None):
    # --- 1. VTCS PROCESSING ---
    for col in ['Waste Collected (Kg)', 'Before Weight', 'After Weight (Kg)']:
        if col in vtcs_df.columns:
            vtcs_df[col] = pd.to_numeric(vtcs_df[col].astype(str).str.replace(',', ''), errors='coerce')
    
    vtcs_df['Tonnage'] = vtcs_df['Waste Collected (Kg)'] / 1000
    vtcs_df['Time In'] = pd.to_datetime(vtcs_df['Time In'], errors='coerce')
    vtcs_df['Time Out'] = pd.to_datetime(vtcs_df['Time Out'], errors='coerce')
    
    vtcs_df['Duration_Mins'] = (vtcs_df['Time Out'] - vtcs_df['Time In']).dt.total_seconds() / 60
    vtcs_df['Time_Status'] = vtcs_df['Duration_Mins'].apply(lambda x: "🚨 Suspicious (>30m)" if x > 30 else "✅ Normal")

    # --- 2. TRACKING CROSS-CHECK ---
    if track_df is not None:
        if 'Time' not in [str(c).strip() for c in track_df.columns]:
            for i in range(min(len(track_df), 20)):
                row_values = [str(val).strip() for val in track_df.iloc[i].values]
                if 'Time' in row_values:
                    track_df.columns = row_values
                    track_df = track_df.iloc[i+1:].reset_index(drop=True)
                    break
        
        track_df.columns = [str(c).strip() for c in track_df.columns]
        
        if 'Time' in track_df.columns and 'Status' in track_df.columns:
            track_df['Time'] = pd.to_datetime(track_df['Time'], errors='coerce')
            
            gps_audit_results = []
            for idx, row in vtcs_df.iterrows():
                target_time = row['Time In']
                if pd.isnull(target_time):
                    gps_audit_results.append("❓ Invalid Time")
                    continue

                mask = (track_df['Time'] >= target_time - timedelta(minutes=2)) & \
                       (track_df['Time'] <= target_time + timedelta(minutes=2))
                
                nearby_pings = track_df[mask]
                
                if nearby_pings.empty:
                    gps_audit_results.append("❓ No GPS Data")
                else:
                    statuses = nearby_pings['Status'].astype(str).str.lower().values
                    is_valid = any(('idle' in s or 'parked' in s or 'stopped' in s) for s in statuses)
                    gps_audit_results.append("✅ Verified (Idle)" if is_valid else "❌ Conflict (Moving)")
            
            vtcs_df['GPS_Audit'] = gps_audit_results
            
    return vtcs_df

if vtcs_file:
    df_vtcs = pd.read_excel(vtcs_file) if vtcs_file.name.endswith('xlsx') else pd.read_csv(vtcs_file)
    df_track = None
    if tracking_file:
        df_track = pd.read_excel(tracking_file) if tracking_file.name.endswith('xlsx') else pd.read_csv(tracking_file)
    
    results = process_audit(df_vtcs, df_track)

    # --- TOP METRICS CARDS ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Weight Collected", f"{results['Tonnage'].sum():.2f} Tons")
    with col2:
        st.metric("Total Trips", len(results))
    with col3:
        delayed = len(results[results['Time_Status'].str.contains("🚨")])
        st.metric("Delayed Trips (>30m)", delayed)
    with col4:
        if 'GPS_Audit' in results.columns:
            conflicts = len(results[results['GPS_Audit'] == "❌ Conflict (Moving)"])
            st.metric("GPS Conflicts", conflicts)

    st.markdown("---")

    # --- VISUAL CHARTS SECTION ---
    st.subheader("📈 Operation Performance Analysis")
    char_col1, char_col2 = st.columns(2)

    with char_col1:
        # Chart 1: Tonnage by Vehicle
        fig_tonnage = px.bar(results.groupby('Vehicle')['Tonnage'].sum().reset_index(), 
                             x='Vehicle', y='Tonnage', 
                             title="Tonnage Distribution per Vehicle",
                             color='Tonnage', color_continuous_scale='Blues')
        st.plotly_chart(fig_tonnage, use_container_width=True)

    with char_col2:
        # Chart 2: Trip Status Distribution
        fig_pie = px.pie(results, names='Time_Status', title='Time Compliance Ratio',
                         color_discrete_map={'✅ Normal':'#2ecc71', '🚨 Suspicious (>30m)':'#e74c3c'})
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- VEHICLE SUMMARY TABLE WITH HEATMAP ---
    st.subheader("📋 Vehicle Performance Summary")
    summary = results.groupby('Vehicle').agg({
        'Tonnage': 'sum', 
        'Data ID': 'count'
    }).rename(columns={'Data ID': 'Total Trips', 'Tonnage': 'Total Tonnage (Tons)'})
    
    # Adding a background gradient to the Tonnage column for better visual heat-mapping
    st.dataframe(summary.style.background_gradient(cmap='YlGnBu', subset=['Total Tonnage (Tons)']), use_container_width=True)
    
    sum_csv = convert_df_to_csv(summary)
    st.download_button("📥 Download Vehicle Summary CSV", data=sum_csv, file_name="Vehicle_Summary.csv")

    # --- DETAILED LOGS ---
    st.divider()
    st.subheader("🔍 Detailed Audit Logs")
    display_cols = ['Vehicle', 'Time In', 'Time Out', 'Duration_Mins', 'Tonnage', 'Time_Status']
    if 'GPS_Audit' in results.columns:
        display_cols.append('GPS_Audit')

    def color_rows(val):
        if '🚨' in str(val) or '❌' in str(val): return 'color: #721c24; background-color: #f8d7da'
        if '✅' in str(val): return 'color: #155724; background-color: #d4edda'
        return ''

    st.dataframe(results[display_cols].style.applymap(color_rows), use_container_width=True)

    full_csv = convert_df_to_csv(results[display_cols])
    st.download_button("📥 Download Full Audit Report", data=full_csv, file_name="Full_Audit_Report.csv")

else:
    st.info("👋 Welcome! Please upload your VTCS and Tracking files to generate the dashboard.")import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="VTCS & GPS Auditor", layout="wide")
st.title("🚛 VTCS & GPS Tracking Auditor")

# --- SIDEBAR: FILE UPLOADS ---
st.sidebar.header("Upload Data")
vtcs_file = st.sidebar.file_uploader("1. Upload VTCS Data (Excel/CSV)", type=['xlsx', 'csv'])
tracking_file = st.sidebar.file_uploader("2. Upload Tracking Report (Excel/CSV)", type=['xlsx', 'csv'])

def process_audit(vtcs_df, track_df=None):
    # --- 1. VTCS PROCESSING ---
    # Weight Conversion
    cols_to_fix = ['Waste Collected (Kg)', 'Before Weight', 'After Weight (Kg)']
    for col in cols_to_fix:
        if col in vtcs_df.columns:
            vtcs_df[col] = pd.to_numeric(vtcs_df[col].astype(str).str.replace(',', ''), errors='coerce')
    
    vtcs_df['Tonnage'] = vtcs_df['Waste Collected (Kg)'] / 1000
    
    # Time Conversion (Portal format: Mar 17, 2026, 2:01:12 PM)
    vtcs_df['Time In'] = pd.to_datetime(vtcs_df['Time In'], errors='coerce')
    vtcs_df['Time Out'] = pd.to_datetime(vtcs_df['Time Out'], errors='coerce')
    
    # 30-Minute Logic (Above 30 is Suspicious)
    vtcs_df['Duration_Mins'] = (vtcs_df['Time Out'] - vtcs_df['Time In']).dt.total_seconds() / 60
    vtcs_df['Time_Status'] = vtcs_df['Duration_Mins'].apply(lambda x: "🚨 Suspicious (>30m)" if x > 30 else "✅ Normal")

    # --- 2. GPS TRACKING CROSS-CHECK ---
    if track_df is not None:
        # Standardize Tracking Columns
        # We assume tracking has 'Vehicle', 'Time', and 'Status'
        track_df['Time'] = pd.to_datetime(track_df.iloc[:, 1], errors='coerce') # Assuming 2nd column is time
        track_df.columns = [c.strip() for c in track_df.columns]
        
        # Merge Logic: Find GPS status at VTCS 'Time In'
        # To handle seconds difference, we round to nearest minute
        vtcs_df['Match_Time'] = vtcs_df['Time In'].dt.floor('min')
        track_df['Match_Time'] = track_df['Time'].dt.floor('min')
        
        # Merge VTCS with Tracking on Vehicle and Time
        merged = pd.merge(
            vtcs_df, 
            track_df[['Vehicle', 'Match_Time', 'Status']], 
            on=['Vehicle', 'Match_Time'], 
            how='left'
        )
        
        # IDLE Logic: Check if GPS status matches "Idle" at Portal entry time
        def check_idle(row):
            gps_status = str(row['Status']).lower()
            if 'idle' in gps_status:
                return "✅ Verified (Idle)"
            elif 'moving' in gps_status or 'active' in gps_status:
                return "❌ Conflict (Moving)"
            else:
                return "❓ No GPS Data"

        merged['GPS_Audit'] = merged.apply(check_idle, axis=1)
        return merged
    
    return vtcs_df

if vtcs_file:
    df_vtcs = pd.read_excel(vtcs_file) if vtcs_file.name.endswith('xlsx') else pd.read_csv(vtcs_file)
    
    df_track = None
    if tracking_file:
        df_track = pd.read_excel(tracking_file) if tracking_file.name.endswith('xlsx') else pd.read_csv(tracking_file)
    
    # Run the Audit
    results = process_audit(df_vtcs, df_track)

    # --- DASHBOARD UI ---
    st.header("📋 Audit Dashboard")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Tonnage (Day)", f"{results['Tonnage'].sum():.2f} Tons")
    m2.metric("Delayed Trips (>30m)", len(results[results['Time_Status'].str.contains("🚨")]))
    
    if 'GPS_Audit' in results.columns:
        conflicts = len(results[results['GPS_Audit'] == "❌ Conflict (Moving)"])
        m3.metric("GPS Conflicts", conflicts)

    # Vehicle Table
    st.subheader("Vehicle Summary")
    summary = results.groupby('Vehicle').agg({'Tonnage': 'sum', 'Data ID': 'count'}).rename(columns={'Data ID': 'Trips'})
    st.table(summary)

    # Main Data Table
    st.subheader("Detailed Logs")
    
    # Column selection for cleaner view
    display_cols = ['Vehicle', 'Time In', 'Time Out', 'Duration_Mins', 'Tonnage', 'Time_Status']
    if 'GPS_Audit' in results.columns:
        display_cols.append('GPS_Audit')

    # Color highlighting
    def color_rows(val):
        if '🚨' in str(val) or '❌' in str(val): return 'background-color: #ffcccc'
        if '✅' in str(val): return 'background-color: #ccffcc'
        return ''

    st.dataframe(results[display_cols].style.applymap(color_rows), use_container_width=True)

else:
    st.info("Please upload your VTCS file from the sidebar to start.")
