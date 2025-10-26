# teacher_viewer.py
"""
Teacher — Weekly Timetable Viewer (single-file Streamlit app)

Behavior:
- Loads local file 'timetableNov25.xlsx' (or shows message if missing).
- Auto-detects period columns (p0, p1, ...), fallback to p0..p8.
- Searchable dropdown (selectbox) for teacher names (type-to-filter).
- Each successful display of the timetable increments the session attempt counter.
  - Max 5 successful displays per session.
  - When 2 attempts remain after a display a warning is shown (message preserved).
  - When 1 attempt remains after a display a last-chance message is shown (message preserved).
  - After 5 successful displays session is locked (message preserved).
- Admin/debug controls removed from the UI (no reset available to regular users).
"""

import os
import re
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Teacher Timetable Viewer", layout="wide")
st.title("Teacher — Weekly Timetable Viewer")

# ---------- CONFIG ----------
LOCAL_FILENAME = "timetableNov25.xlsx"   # must be present next to this script
DEFAULT_PERIOD_COUNT = 9
MAX_ATTEMPTS = 5

# ---------- Helpers ----------
@st.cache_data
def load_timetable(path):
    """Load local Excel timetable and normalize column names to lowercase."""
    if not path or not os.path.exists(path):
        return None
    df = pd.read_excel(path, header=0)
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
    if rows.empty:
        return total, per_day
    for day_name, grp in rows.groupby('day'):
        day_count = 0
        for _, r in grp.iterrows():
            for p in expected_periods:
                v = r.get(p, None)
                if pd.notna(v) and str(v).strip() != "":
                    day_count += 1
        per_day.append({"day": day_name, "periods_on_day": day_count})
        total += day_count
    per_day_sorted = sorted(per_day, key=lambda x: str(x["day"]))
    return total, per_day_sorted

# ---------- Load local timetable (no uploader) ----------
tt = load_timetable(LOCAL_FILENAME)
if tt is None:
    st.error(
        f"Local timetable file not found: '{LOCAL_FILENAME}'.\n"
        "Please place the Excel file with that exact name in the same folder as this script."
    )
    st.stop()

# ---------- Validate columns ----------
expected_periods = detect_period_columns(tt)
required_columns = ['day', 'tname'] + expected_periods
missing = [c for c in required_columns if c not in tt.columns]
if missing:
    st.error(f"Timetable is missing required columns: {missing}. Ensure the Excel has these columns.")
    st.stop()

# ---------- Session state for successful-view limiting ----------
if 'successful_views' not in st.session_state:
    st.session_state.successful_views = 0
if 'locked' not in st.session_state:
    st.session_state.locked = False

# ---------- UI: selection & behavior ----------
if st.session_state.locked:
    st.error("Aapne is session mein adhiktam (maximum) timetable views (5) poore kar liye hain. Kripya prashasan se sampark karein.")
    st.stop()

teachers_all = sorted(tt['tname'].dropna().unique().tolist())
if not teachers_all:
    st.error("No teacher names found in 'tname' column.")
    st.stop()

placeholder = "-- Select your name (start typing) --"
options = [placeholder] + teachers_all

col1, col2 = st.columns([3, 1])
with col1:
    name_input = st.text_input("Your name (case-insensitive)")
with col2:
    submitted = st.button("View my weekly timetable")

# also show helpful hint of available teacher names (collapsed)
with st.expander("Dekhen: sabhi naam (copy/paste ke liye)"):
    st.write(teachers_all)

# ---------- Submission handling ----------
# Note: only successful displays increment successful_views.
if submitted:
    # If already exhausted (locked), block
    if st.session_state.successful_views >= MAX_ATTEMPTS:
        st.session_state.locked = True
        st.error("Aapne adhiktam sankhya (maximum) timetable views is session mein use kar liye hain. Access blocked.")
    else:
        name_query = (name_input or "").strip()
        if name_query == "":
            st.warning("Kripya apna naam select kariye.")  # keep warning style consistent
        else:
            # find matching tname rows (case-insensitive exact or substring match)
            mask_exact = tt['tname'].dropna().str.lower() == name_query.lower()
            mask_contains = tt['tname'].dropna().str.lower().str.contains(name_query.lower())
            matched_names = tt.loc[mask_exact | mask_contains, 'tname'].dropna().unique().tolist()

            if len(matched_names) == 0:
                # not found — DO NOT increment attempts here
                attempts_left = MAX_ATTEMPTS - st.session_state.successful_views
                if attempts_left <= 2 and attempts_left > 0:
                    st.warning(f"Name not found. THIS IS A LAST CHANCE(S) WARNING: you have {attempts_left} attempt(s) remaining — please enter the correct name.")
                elif attempts_left == 0:
                    st.error("Name not found. You have used all attempts. Access locked for this session.")
                    st.session_state.locked = True
                else:
                    st.warning(f"Name not found. Attempts left: {attempts_left}")
            else:
                # If multiple matches, let user pick exact one and display only when they confirm
                if len(matched_names) > 1:
                    selected_teacher = st.selectbox("Multiple matches found — please select the exact teacher name:", options=sorted(matched_names))
                    # show a separate button to confirm viewing the selected teacher's timetable
                    if st.button("View selected teacher timetable"):
                        teacher_rows = tt[tt['tname'].str.lower() == selected_teacher.lower()].copy()
                        if teacher_rows.empty:
                            st.error("Selected name not found in the timetable. Kripya admin se sampark karein.")
                        else:
                            # Display timetable — this counts as one successful view
                            next_count = st.session_state.successful_views + 1
                            views_left_after = MAX_ATTEMPTS - next_count

                            st.success(f"Found timetable for: {selected_teacher}")
                            try:
                                teacher_rows = teacher_rows.sort_values(by='day')
                            except Exception:
                                pass

                            st.write(f"### Weekly timetable for {selected_teacher}")
                            st.dataframe(teacher_rows.reset_index(drop=True))

                            total, per_day = count_periods_for_rows(teacher_rows, expected_periods)
                            st.write(f"**Total periods this week:** {total}")
                            if per_day:
                                st.write("Periods per day:")
                                st.dataframe(pd.DataFrame(per_day).sort_values(by='day').reset_index(drop=True))

                            # increment successful view counter
                            st.session_state.successful_views = next_count

                            # Post-display warnings based on remaining allowed views (messages preserved)
                            if views_left_after == 2:
                                st.warning("Dhyaan: Aapke paas ab sirf 2 aur mauke (attempts) shesh hain. Kripya dhyaan se apna naam chunen.")
                            elif views_left_after == 1:
                                st.error("Aakhri mauka: Ab keval 1 antim prayas (last attempt) shesh hai. Kripya sahi naam chunen — yeh antim mauka hai.")
                            elif views_left_after == 0:
                                st.info("Aapne abhi apna antim (5th) view istemal kiya. Agla view allowed nahi hoga.")
                                st.session_state.locked = True
                else:
                    # single match — display directly and increment
                    selected_teacher = matched_names[0]
                    teacher_rows = tt[tt['tname'].str.lower() == selected_teacher.lower()].copy()
                    if teacher_rows.empty:
                        st.error("Selected name not found in the timetable. Kripya admin se sampark karein.")
                    else:
                        # Display timetable — this counts as one successful view
                        next_count = st.session_state.successful_views + 1
                        views_left_after = MAX_ATTEMPTS - next_count

                        st.success(f"Found timetable for: {selected_teacher}")
                        try:
                            teacher_rows = teacher_rows.sort_values(by='day')
                        except Exception:
                            pass

                        st.write(f"### Weekly timetable for {selected_teacher}")
                        st.dataframe(teacher_rows.reset_index(drop=True))

                        total, per_day = count_periods_for_rows(teacher_rows, expected_periods)
                        st.write(f"**Total periods this week:** {total}")
                        if per_day:
                            st.write("Periods per day:")
                            st.dataframe(pd.DataFrame(per_day).sort_values(by='day').reset_index(drop=True))

                        # increment successful view counter
                        st.session_state.successful_views = next_count

                        # Post-display warnings based on remaining allowed views (messages preserved)
                        if views_left_after == 2:
                            st.warning("Dhyaan: Aapke paas ab sirf 2 aur mauke (attempts) shesh hain. Kripya dhyaan se apna naam chunen.")
                        elif views_left_after == 1:
                            st.error("Aakhri mauka: Ab keval 1 antim prayas (last attempt) shesh hai. Kripya sahi naam chunen — yeh antim mauka hai.")
                        elif views_left_after == 0:
                            st.info("Aapne abhi apna antim (5th) view istemal kiya. Agla view allowed nahi hoga.")
                            st.session_state.locked = True

# show attempt status in footer
st.caption(f"Attempts used this session: {st.session_state.successful_views} / {MAX_ATTEMPTS}")
preview_left = MAX_ATTEMPTS - st.session_state.successful_views
if preview_left <= 2 and preview_left > 0:
    st.warning(f"Please Note: Aapke paas ab {preview_left} successful timetable views shesh hain. Kripya Apne timetable me hi interested rahe ")
st.caption("Thank you for your prompt action. Applicable from Monday i.e. 27 Nov onwards")
