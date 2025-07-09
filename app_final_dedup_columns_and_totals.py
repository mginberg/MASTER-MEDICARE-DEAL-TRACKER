
import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
import glob

# Constants
PAYABLE = [
    "active", "submitted", "approved", "enrolled",
    "future active policy", "in progress", "pending"
]
CANCELLED = [
    "cancelled", "closed", "denied", "duplicate", "early cancellation", "inactive",
    "invalid election period", "member cancellation", "no carrier match", "not found",
    "pended", "plan change", "rejected", "request for information", "unknown"
]

def safe_to_datetime(value):
    if isinstance(value, datetime):
        return value
    elif isinstance(value, int):
        try:
            return datetime.fromordinal(datetime(1900, 1, 1).toordinal() + value - 2)
        except:
            return None
    elif isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
            try:
                return datetime.strptime(value, fmt)
            except:
                continue
    return None

# Save snapshot if today is 1st or 30th
today = date.today()
if today.day in [1, 30]:
    os.makedirs("snapshots", exist_ok=True)
    pd.read_csv("SNAPSHOT CSV.csv").to_csv(f"snapshots/snapshot_{today}.csv", index=False)

# Load latest data
df = pd.read_csv("SNAPSHOT CSV.csv")
df.columns = df.columns.str.upper()

# Agent dropdown
df["CLOSER"] = df["CLOSER"].fillna("Unknown")
agents = sorted(df["CLOSER"].unique())
selected_agent = st.sidebar.selectbox("Select Agent", ["ALL"] + agents)

# Filter by agent
if selected_agent != "ALL":
    df = df[df["CLOSER"] == selected_agent]

# Convert DATE field
df["DATE"] = df["DATE"].apply(safe_to_datetime)
df = df[df["DATE"].notnull()]
df["WEEK"] = df["DATE"].dt.to_period("W").apply(lambda r: r.start_time)

# Weekly summary
st.title("Weekly Deal Tracker")
for week, group in df.groupby("WEEK"):
    week_label = safe_to_datetime(week).strftime('%B %d, %Y') if safe_to_datetime(week) else str(week)
    st.subheader(f"Week of {week_label} – Total Deals: {len(group)}")
    display_cols = [col for col in ["NAME", "CARRIER", "SEP", "STATUS"] if col in group.columns]
    # Drop duplicate columns in advance to prevent pyarrow crash
    group = group.loc[:, ~group.columns.duplicated()]
    st.dataframe(group[display_cols])

# --- Monthly Bonus Summary ---
st.title("Monthly Bonus Summary")

# Current month filter
current_month = datetime.now().month
monthly = df[df["DATE"].dt.month == current_month]
monthly["STATUS"] = monthly["STATUS"].str.lower()
monthly_good = monthly[monthly["STATUS"].isin(PAYABLE)]
monthly_bad = monthly[monthly["STATUS"].isin(CANCELLED)]

# Load prior snapshots (only if available)
snapshot_files = sorted(glob.glob("snapshots/snapshot_*.csv"))[-3:]  # last 3 snapshots
reinstated, chargebacks = [], []

if len(snapshot_files) >= 1:
    for file in snapshot_files:
        snap = pd.read_csv(file)
        snap.columns = snap.columns.str.upper()
        merged = pd.merge(snap, df, on=["NAME", "MBI NUMBER"], suffixes=("_old", "_new"))
        merged["STATUS_old"] = merged["STATUS_old"].str.lower()
        merged["STATUS_new"] = merged["STATUS_new"].str.lower()

        merged["was_active"] = merged["STATUS_old"].isin(PAYABLE)
        merged["now_cancelled"] = merged["STATUS_new"].isin(CANCELLED)
        merged["was_cancelled"] = merged["STATUS_old"].isin(CANCELLED)
        merged["now_active"] = merged["STATUS_new"].isin(PAYABLE)

        reinstated.append(merged[merged["was_cancelled"] & merged["now_active"]])
        chargebacks.append(merged[merged["was_active"] & merged["now_cancelled"]])

    reinstated_df = pd.concat(reinstated) if reinstated else pd.DataFrame()
    chargebacks_df = pd.concat(chargebacks) if chargebacks else pd.DataFrame()
else:
    reinstated_df = chargebacks_df = pd.DataFrame()

st.subheader("✅ Good Deals (This Month)")
st.dataframe(monthly_good[["NAME", "STATUS", "DATE", "CARRIER"]])
st.write("Count:", len(monthly_good))

st.subheader("❌ Bad Deals (This Month)")
st.dataframe(monthly_bad[["NAME", "STATUS", "DATE", "CARRIER"]])
st.write("Count:", len(monthly_bad))

st.subheader("🔁 Reinstated (from Cancelled → Active)")
st.dataframe(reinstated_df[["NAME", "STATUS_old", "STATUS_new", "CARRIER_new"]] if not reinstated_df.empty else "None")
st.write("Count:", len(reinstated_df))

st.subheader("🔻 Chargebacks (from Active → Cancelled)")
st.dataframe(chargebacks_df[["NAME", "STATUS_old", "STATUS_new", "CARRIER_new"]] if not chargebacks_df.empty else "None")
st.write("Count:", len(chargebacks_df))

net_bonus = len(monthly_good) + len(reinstated_df) - len(chargebacks_df)
st.subheader(f"💰 Net Monthly Bonus Deals: {net_bonus}")


# Display Monthly Summary Totals
monthly_total = len(monthly_df)
st.markdown(f"### 🧮 Total Monthly Deals: {monthly_total}")