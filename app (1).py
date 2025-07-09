
import streamlit as st
import pandas as pd
import datetime as dt
from io import StringIO

# Title
st.set_page_config(layout="wide")
st.title("Agent Deal Tracker")

# Load latest data (export from HubSpot)
uploaded_file = st.file_uploader("Upload latest snapshot CSV", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()
else:
    st.stop()

# Load original snapshot only once (book of business as of the 1st of month)
try:
    original_df = pd.read_csv("original_snapshot.csv")
    original_df.columns = original_df.columns.str.strip().str.upper()
except FileNotFoundError:
    st.error("Missing original snapshot file (original_snapshot.csv). Upload it to the app directory.")
    st.stop()

# Agent Dropdown
agent_list = sorted(df["CLOSER"].dropna().unique())
selected_agent = st.sidebar.selectbox("Select Agent", agent_list)

if not selected_agent:
    st.error("No agent selected or invalid agent name.")
    st.stop()

# Filter by selected agent
agent_df = df[df["CLOSER"].str.upper() == selected_agent.upper()]

# Convert DATE column to datetime
agent_df["DATE"] = pd.to_datetime(agent_df["DATE"], errors="coerce")
agent_df = agent_df.dropna(subset=["DATE"])

# Group by week
agent_df["WEEK"] = agent_df["DATE"].dt.to_period("W-SUN").apply(lambda r: r.start_time)
weekly_groups = agent_df.groupby("WEEK")

# Weekly Summary
st.header("Weekly Deal Tracker")
for week, group in weekly_groups:
    st.subheader(f"Week of {week.strftime('%B %d, %Y')} – Total Deals: {len(group)}")
    display_cols = [col for col in ["NAME", "CARRIER", "SEP", "STATUS"] if col in group.columns]
    st.dataframe(group[display_cols])

# Monthly Bonus Summary
st.header("Monthly Bonus Summary")

# Convert STATUS columns to lowercase for comparison
df["STATUS"] = df["STATUS"].astype(str).str.lower()
original_df["STATUS"] = original_df["STATUS"].astype(str).str.lower()

# Filter both to trailing 3 months
today = dt.date.today()
start_3_months_ago = (today.replace(day=1) - pd.DateOffset(months=2)).date()
df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
original_df["DATE"] = pd.to_datetime(original_df["DATE"], errors="coerce")
df_filtered = df[(df["CLOSER"].str.upper() == selected_agent.upper()) & (df["DATE"].dt.date >= start_3_months_ago)]
original_filtered = original_df[original_df["CLOSER"].str.upper() == selected_agent.upper()]

# Merge to detect changes
merged = pd.merge(
    df_filtered,
    original_filtered,
    on=["MBI NUMBER"],
    suffixes=("_NEW", "_OLD"),
    how="outer",
    indicator=True
)

# Identify chargebacks and reinstatements
chargebacks = merged[(merged["STATUS_OLD"] == "active") & (merged["STATUS_NEW"] != "active")]
reinstated = merged[(merged["STATUS_OLD"] != "active") & (merged["STATUS_NEW"] == "active")]

# Calculate net bonus
active_new = df_filtered[df_filtered["STATUS"] == "active"]
net_bonus_count = len(active_new) - len(chargebacks)

st.markdown(f"**Active Deals (June):** {len(active_new)}")
st.markdown(f"**Chargebacks from May Snapshot:** {len(chargebacks)}")
st.markdown(f"**Reinstated from May Snapshot:** {len(reinstated)}")
st.markdown(f"**Net Bonus Count for June:** {net_bonus_count}")
