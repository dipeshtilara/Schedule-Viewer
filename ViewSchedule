# teacher_viewer.py
"""
Teacher — Weekly Timetable Viewer (single-file Streamlit app)

Behavior:
- Load timetable from local file 'timetableNov25.xlsx' or accept an uploaded file.
- Detect period columns (p0, p1, ...), fallback to p0..p8.
- Teacher selects their name from a searchable dropdown (selectbox).
- Each successful display of the timetable counts as one attempt.
  - Maximum 5 successful displays per session.
  - When 2 attempts remain (after this display) a warning is shown.
  - When 1 attempt remains (after this display) a stronger 'last chance' message is shown.
  - After 5 successful displays, access is locked for that session.
- Admin/Debug expander to reset attempts for the session.

Run:
    streamlit run teacher_viewer.py
"""

import os
import re
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Teacher Timetable Viewer", layout="wide")
st.title("Teacher — Weekly Timetable Viewer")

# ---------- CONFIG ----------
LOCAL_FILENAME = "timetableNov25.xlsx"
DEFAULT_PERIOD_COUNT = 9
MAX_ATTEMPTS = 5

# ---------- Helpers ----------
@st.cache_data
def load_timetable(path=None, uploaded_file=None):
    """
    Load Excel timetable (DataFrame) and normalize column names to lowercase.
    """
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, header=0)
    else:
        if path and os.path.exists(path):
            df = pd.read_excel(path, header=0)
        else:
            return None
    df.columns = df.columns.str.strip().str.lower()
    return df

def detect_period_columns(df):
    cols = list(df.columns)
    period_cols = [c for c in cols if re.fullmatch(r'p\d+', c)]
    if not period_cols:
        period_cols = [c for c in cols if re.match(r'p[_\-\s]?\d+', c)]
    if not period_cols:
        period_cols = [f"p{i}" for i in range(DEFAULT_PERIOD_COUNT)]
    expected = sorted(period_cols, key=lambda x: int(re.findall(r'\d+', x)[0]))
    return expected

def count_periods_for_rows(rows, expected_periods):
    total = 0
    per_day = []
    for day_name, grp in rows.groupby('day'):
        day_count = 0
        for _, r in grp.iterrows():
            for p in expected_periods:
                v = r.get(p, None)
                if pd.notna(v) and str(v).strip() != "":
                    day_count += 1
        per_day.append({"day": day_name, "periods_on_day": day_count})
        total += day_count
    return total, sorted(per_day, key=lambda x: str(x["day"]))

# ---------- Load timetable ----------
uploaded = st.file_uploader("(Optional) Upload timetable Excel (xlsx) — otherwise app tries to use 'timetableNov25.xlsx'", type=["xlsx"])
tt = load_timetable(path=LOCAL_FILENAME, uploaded_file=uploaded)
if tt is None:
    st.warning("Timetable not found. Please place 'timetableNov25.xlsx' next to this script or upload an Excel file.")
    st.stop()

# detect period columns and required columns
expected_periods = detect_period_columns(tt)
required_columns = ['day', 'tname'] + expected_periods
missing = [c for c in required_columns if c not in tt.columns]
if missing:
    st.error(f"Timetable is missing required columns: {missing}. Make sure your Excel has these columns (case-insensitive).")
    st.stop()

# ---------- Session state (attempt limiting) ----------
if 'successful_views' not in st.session_state:
    # Number of times the user has successfully viewed a timetable this session
    st.session_state.successful_views = 0
if 'locked' not in st.session_state:
    st.session_state.locked = False

with st.expander("Admin / debug (reset attempts)"):
    if st.button("Reset successful-view counter for this session"):
        st.session_state.successful_views = 0
        st.session_state.locked = False
        st.success("Session counter reset.")

# ---------- UI: name selection with auto-suggest ----------
if st.session_state.locked:
    st.error("Aapne is session mein adhiktam number of timetable views (5) poore kar liye hain. Kripya prashasan se sampark karein (contact admin).")
    st.stop()

teachers_all = sorted(tt['tname'].dropna().unique().tolist())
placeholder = "-- Select your name (start typing) --"
options = [placeholder] + teachers_all

col1, col2 = st.columns([3, 1])
with col1:
    selected_name = st.selectbox("Aapka naam chuniye (aap type kar ke search kar sakte hain):", options=options, index=0, key="teacher_selectbox")
with col2:
    view_button = st.button("View my weekly timetable")

with st.expander("Dekhen: sabhi naam (list) — agar aap copy/paste karna chahein)"):
    st.write(teachers_all)

# ---------- Handle view request ----------
if view_button:
    if selected_name == placeholder:
        st.warning("Kripya apna naam select kariye (name not selected).")
    else:
        # If attempts exhausted, lock and stop
        if st.session_state.successful_views >= MAX_ATTEMPTS:
            st.session_state.locked = True
            st.error("Aapne adhiktam sankhya (maximum) timetable views is session mein use kar liye hain. Access blocked.")
        else:
            name_choice = selected_name.strip()
            # find exact case-insensitive rows for this teacher
            teacher_rows = tt[tt['tname'].str.lower() == name_choice.lower()].copy()

            if teacher_rows.empty:
                # extremely unlikely since selection is from list, but handle gracefully
                st.error("Naam ke liye timetable nahi mila (selected name not present). Kripya sahi naam chunen.")
            else:
                # Will show the timetable — this counts as one successful view (attempt)
                next_count = st.session_state.successful_views + 1
                views_left_after = MAX_ATTEMPTS - next_count

                # Display timetable
                st.success(f"Aapka timetable mil gaya: {name_choice}")
                try:
                    teacher_rows = teacher_rows.sort_values(by='day')
                except Exception:
                    pass

                st.write(f"### Weekly timetable for {name_choice}")
                st.dataframe(teacher_rows.reset_index(drop=True))

                total, per_day = count_periods_for_rows(teacher_rows, expected_periods)
                st.write(f"**Total periods this week:** {total}")
                if per_day:
                    st.write("Periods per day:")
                    st.dataframe(pd.DataFrame(per_day).reset_index(drop=True))

                # increment successful view counter now
                st.session_state.successful_views = next_count

                # Show warnings based on remaining allowed views AFTER this display
                if views_left_after == 2:
                    st.warning(
                        "Dhyaan: Aapke paas ab sirf 2 aur mauke (attempts) shesh hain. Kripya dhyaan se apna naam chunen."
                    )
                elif views_left_after == 1:
                    st.error(
                        "Aakhri mauka: Ab keval 1 antim prayas (last attempt) shesh hai. Kripya sahi naam chunen — yeh antim mauka hai."
                    )
                elif views_left_after == 0:
                    st.info("Aapne abhi apna antim (5th) view istemal kiya. Agla view allowed nahi hoga.")
                    st.session_state.locked = True

                # Offer to clear counter after successful view if user wants
                if st.button("Done — clear successful-view counter for this session"):
                    st.session_state.successful_views = 0
                    st.session_state.locked = False
                    st.success("Session counter cleared.")

# Footer: attempts used
st.caption(f"Session successful displays used: {st.session_state.successful_views} / {MAX_ATTEMPTS}")

# If user hasn't clicked view yet and remaining displays are low, preemptive warning
if not view_button and st.session_state.successful_views < MAX_ATTEMPTS:
    preview_left = MAX_ATTEMPTS - st.session_state.successful_views
    if preview_left <= 2:
        st.warning(f"Suchetan: Aapke paas ab {preview_left} successful timetable views shesh hain. Aakhri 2 views par sakht message dikhai dega.")

st.caption("Notes: Only each successful display of your timetable counts as one attempt. Select box supports typing to search/filter names (start typing your name).")
