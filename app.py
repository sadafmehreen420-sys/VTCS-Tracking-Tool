import streamlit as st
import pandas as pd

st.title("Penalty Categorizer (Simple AI Tool)")

st.write("Upload Model Sheet (with correct categories)")
model_file = st.file_uploader("Upload Model Sheet", type=["xlsx", "csv"])

st.write("Upload Penalty Sheet (raw data)")
penalty_file = st.file_uploader("Upload Penalty Sheet", type=["xlsx", "csv"])

if model_file and penalty_file:
    model_df = pd.read_excel(model_file) if model_file.name.endswith("xlsx") else pd.read_csv(model_file)
    penalty_df = pd.read_excel(penalty_file) if penalty_file.name.endswith("xlsx") else pd.read_csv(penalty_file)

    st.success("Files uploaded successfully")

    # simple matching logic
    if "penalty type" in model_df.columns and "complaint" in model_df.columns:
        def classify(text):
            for _, row in model_df.iterrows():
                if str(row["complaint"]).lower() in str(text).lower():
                    return row["penalty type"]
            return "Unknown"

        penalty_df["Predicted Type"] = penalty_df.iloc[:, 1].apply(classify)

    st.write("### Result")
    st.dataframe(penalty_df)

    # download
    st.download_button(
        "Download Result",
        penalty_df.to_csv(index=False),
        file_name="result.csv"
    )
