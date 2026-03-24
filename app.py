import streamlit as st
import pandas as pd
import numpy as np
from image_module import process_images  # import your module

# Page Config
st.set_page_config(page_title="VTCS & GPS Auditor", layout="wide")

# ---------------- SIDEBAR NAVIGATION ----------------
st.sidebar.title("Navigation")

module = st.sidebar.radio(
    "Select Module",
    ["VTCS & GPS Audit", "Image Verification"]
)

# =========================================================
# 🟢 MODULE 1: VTCS & GPS AUDIT
# =========================================================
if module == "VTCS & GPS Audit":

    st.title("🚛 VTCS & GPS Tracking Auditor")

    st.sidebar.header("Upload Data")
    vtcs_file = st.sidebar.file_uploader("1. Upload VTCS Data", type=['xlsx', 'csv'])
    tracking_file = st.sidebar.file_uploader("2. Upload Tracking Report", type=['xlsx', 'csv'])

    def process_audit(vtcs_df, track_df=None):

        # Weight Conversion
        cols_to_fix = ['Waste Collected (Kg)', 'Before Weight', 'After Weight (Kg)']
        for col in cols_to_fix:
            if col in vtcs_df.columns:
                vtcs_df[col] = pd.to_numeric(
                    vtcs_df[col].astype(str).str.replace(',', ''), errors='coerce'
                )

        vtcs_df['Tonnage'] = vtcs_df['Waste Collected (Kg)'] / 1000

        # Time Conversion
        vtcs_df['Time In'] = pd.to_datetime(vtcs_df['Time In'], errors='coerce')
        vtcs_df['Time Out'] = pd.to_datetime(vtcs_df['Time Out'], errors='coerce')

        vtcs_df['Duration_Mins'] = (
            vtcs_df['Time Out'] - vtcs_df['Time In']
        ).dt.total_seconds() / 60

        vtcs_df['Time_Status'] = vtcs_df['Duration_Mins'].apply(
            lambda x: "🚨 Suspicious (>30m)" if x > 30 else "✅ Normal"
        )

        # GPS Merge
        if track_df is not None:

            track_df['Time'] = pd.to_datetime(track_df.iloc[:, 1], errors='coerce')
            track_df.columns = [c.strip() for c in track_df.columns]

            vtcs_df['Match_Time'] = vtcs_df['Time In'].dt.floor('min')
            track_df['Match_Time'] = track_df['Time'].dt.floor('min')

            merged = pd.merge(
                vtcs_df,
                track_df[['Vehicle', 'Match_Time', 'Status']],
                on=['Vehicle', 'Match_Time'],
                how='left'
            )

            def check_idle(row):
                gps_status = str(row['Status']).lower()
                if 'idle' in gps_status:
                    return "✅ Verified (Idle)"
                elif 'moving' in gps_status:
                    return "❌ Conflict (Moving)"
                else:
                    return "❓ No GPS Data"

            merged['GPS_Audit'] = merged.apply(check_idle, axis=1)
            return merged

        return vtcs_df

    # RUN
    if vtcs_file:
        df_vtcs = pd.read_excel(vtcs_file) if vtcs_file.name.endswith('xlsx') else pd.read_csv(vtcs_file)

        df_track = None
        if tracking_file:
            df_track = pd.read_excel(tracking_file) if tracking_file.name.endswith('xlsx') else pd.read_csv(tracking_file)

        results = process_audit(df_vtcs, df_track)

        # Dashboard
        st.header("📋 Audit Dashboard")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Tonnage", f"{results['Tonnage'].sum():.2f} Tons")
        m2.metric("Delayed Trips", len(results[results['Time_Status'].str.contains("🚨")]))

        if 'GPS_Audit' in results.columns:
            conflicts = len(results[results['GPS_Audit'] == "❌ Conflict (Moving)"])
            m3.metric("GPS Conflicts", conflicts)

        # Table
        st.subheader("Vehicle Summary")
        summary = results.groupby('Vehicle').agg({'Tonnage': 'sum', 'Data ID': 'count'}).rename(columns={'Data ID': 'Trips'})
        st.table(summary)

        st.subheader("Detailed Logs")

        display_cols = ['Vehicle', 'Time In', 'Time Out', 'Duration_Mins', 'Tonnage', 'Time_Status']
        if 'GPS_Audit' in results.columns:
            display_cols.append('GPS_Audit')

        st.dataframe(results[display_cols], use_container_width=True)

    else:
        st.info("Please upload VTCS file")

# =========================================================
# 🖼️ MODULE 2: IMAGE VERIFICATION
# =========================================================
elif module == "Image Verification":

    st.title("🖼️ VTCS Image Verification")

    before_file = st.file_uploader("Upload BEFORE Image", type=["jpg", "png"])
    after_file = st.file_uploader("Upload AFTER Image", type=["jpg", "png"])

    activity_time = st.datetime_input("Select Activity Time")

    if st.button("Verify Images"):

        if before_file and after_file:

            result = process_images(before_file, after_file, activity_time)

            st.success(f"Status: {result['status']}")
            st.write(f"Difference Score: {result['difference_score']}")
            st.write(f"Time Difference (minutes): {result['time_difference_minutes']}")

        else:
            st.warning("Please upload both images")
