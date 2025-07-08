
import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta

st.set_page_config(page_title='Agent Deal Tracker', layout='wide')

HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN")
SNAPSHOT_FILE = "original_snapshot.csv"
CACHE_FILE = "hubspot_cache.json"

PAYABLE_STATUSES = [
    "Active", "Submitted", "Approved", "Enrolled",
    "Future Active Policy", "In Progress", "Pending"
]
CANCELLED_STATUSES = [
    "Cancelled", "Closed", "Denied", "Duplicate", "Early Cancellation",
    "Inactive", "Invalid Election Period", "Member Cancellation",
    "No Carrier Match", "Not Found", "Pended", "Plan Change",
    "Rejected", "Request for Information", "Unknown"
]

def fetch_from_hubspot():
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}"
    }
    url = "https://api.hubapi.com/crm/v3/objects/contacts?limit=100&properties=NAME,DATE,MBI NUMBER,CARRIER,SEP,STATE,LANGUAGE,STATUS"

    all_data = []
    while url:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        all_data.extend(data.get('results', []))
        paging = data.get('paging', {}).get('next', {}).get('link')
        url = paging if paging else None

    records = []
    for contact in all_data:
        props = contact.get('properties', {})
        records.append({
            "Record ID": contact.get("id"),
            "NAME": props.get("NAME"),
            "DATE": props.get("DATE"),
            "MBI NUMBER": props.get("MBI NUMBER"),
            "CARRIER": props.get("CARRIER"),
            "SEP": props.get("SEP"),
            "STATE": props.get("STATE"),
            "LANGUAGE": props.get("LANGUAGE"),
            "STATUS": props.get("STATUS")
        })

    df = pd.DataFrame(records)
    df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')
    df = df.dropna(subset=["DATE"])
    df["Submission Week"] = df["DATE"].apply(lambda x: x - timedelta(days=x.weekday()))
    df["Submission Month"] = df["DATE"].dt.strftime("%B %Y")
    return df

def load_cached_data():
    if os.path.exists(CACHE_FILE):
        modified = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        if datetime.now() - modified < timedelta(hours=24):
            with open(CACHE_FILE, "r") as f:
                return pd.read_json(f)
    df = fetch_from_hubspot()
    df.to_json(CACHE_FILE)
    return df

df = load_cached_data()

if not os.path.exists(SNAPSHOT_FILE):
    st.error("Missing original snapshot file (original_snapshot.csv). Upload it to the app directory.")
    st.stop()
snapshot = pd.read_csv(SNAPSHOT_FILE)
snapshot["DATE"] = pd.to_datetime(snapshot["DATE"], errors='coerce')
snapshot["Submission Month"] = snapshot["DATE"].dt.strftime("%B %Y")
snapshot["Record ID"] = snapshot["Record ID"].astype(str)

df["Record ID"] = df["Record ID"].astype(str)

query_params = st.query_params
url_agent = query_params.get("agent", [None])[0] if query_params.get("agent") else None

agents = sorted(df["NAME"].dropna().unique())
selected_agent = None

if url_agent and url_agent.upper() in (a.upper() for a in agents):
    selected_agent = url_agent
else:
    selected_agent = st.selectbox("Select Agent", agents)

st.title(f"Agent Deal Tracker – {selected_agent}")
agent_df = df[df["NAME"].str.upper() == selected_agent.upper()]
agent_snapshot = snapshot[snapshot["NAME"].str.upper() == selected_agent.upper()]

st.header("📅 Weekly Tracker")
weekly = agent_df.groupby("Submission Week")
for week, group in weekly:
    st.subheader(f"Week of {week.strftime('%B %d, %Y')} – Total Deals: {len(group)}")
    st.dataframe(group[["DATE", "CARRIER", "STATUS", "Submission Month"]].sort_values("DATE"))

st.header("🏆 Monthly Bonus Tracker")
months = sorted(agent_df["Submission Month"].unique())
for month in months:
    current_df = agent_df[agent_df["Submission Month"] == month]
    good = current_df[current_df["STATUS"].isin(PAYABLE_STATUSES)]
    bad = current_df[current_df["STATUS"].isin(CANCELLED_STATUSES)]

    st.subheader(f"{month}")
    st.markdown("**✅ Good Deals**")
    st.dataframe(good[["DATE", "CARRIER", "STATUS"]])
    st.markdown("**❌ Bad Deals**")
    st.dataframe(bad[["DATE", "CARRIER", "STATUS"]])

    current_month_dt = pd.to_datetime(f"1 {month}")
    trailing_months = [
        (current_month_dt - pd.DateOffset(months=i)).strftime("%B %Y")
        for i in range(3)
    ]
    trailing_df = snapshot[
        (snapshot["Submission Month"].isin(trailing_months)) &
        (snapshot["NAME"].str.upper() == selected_agent.upper()) &
        (snapshot["STATUS"].isin(PAYABLE_STATUSES))
    ]
    trailing_ids = set(trailing_df["Record ID"])
    current_cancellations = set(bad["Record ID"])
    chargebacks = trailing_ids.intersection(current_cancellations)

    st.markdown("**🔁 Chargebacks (from trailing 3 months)**")
    if chargebacks:
        st.dataframe(bad[bad["Record ID"].isin(chargebacks)][["DATE", "CARRIER", "STATUS"]])
    else:
        st.write("None")

    st.markdown(f"**💰 Net Bonus: {len(good) - len(chargebacks)}**")
