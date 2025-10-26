# teacher_viewer.py
"""
Teacher — Weekly Timetable Viewer (single-file Streamlit app)
- Automatically loads local file 'timetableNov25.xlsx' (no uploader).
- Auto-detects period columns (p0, p1, ...), fallback to p0..p8.
- Searchable dropdown (selectbox) for teacher names (type-to-filter).
- Each successful display counts as one attempt. Max 5 successful displays per session.
  - When 2 displays remain after this one: warning shown.
  - When 1 remains after this one: last-chance message shown.
  - After 5 successful displays session is locked until admin reset.
- Admin expander to reset the counter for the session.
"""

import os
import re
import streamlit as st
import pandas as pd
import calendar
from dateutil.parser import parse as parse_date  # used for day normalization if needed

# canonical weekday order (Monday → Saturday)
WEEK_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
WEEK_MAP = {name: idx for idx, name in enumerate(WEEK_ORDER)}

st.set_page_config(page_title="Teacher Timetable Viewer", layout="wide")
st.title("Teacher — Weekly Timetable Viewer")

def normalize_day_value(val):
    """
    Convert val (string or date) to a canonical weekday name (lowercase),
    or return None if it can't be resolved.
    Handles:
      - 'Monday', 'mon', 'MON', 'Mon'
      - numeric dates like '2025-11-03' (will be parsed to weekday)
      - strings with extra whitespace / casing
    """
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s == "":
        return None

    s_lower = s.lower()
    short_map = {
        "mon": "monday", "monday": "monday",
        "tue": "tuesday", "tues": "tuesday", "tuesday": "tuesday",
        "wed": "wednesday", "weds": "wednesday", "wednesday": "wednesday",
        "thu": "thursday", "thurs": "thursday", "thursday": "thursday",
        "fri": "friday", "friday": "friday",
        "sat": "saturday", "saturday": "saturday",
        "sun": "sunday", "sunday": "sunday"
    }
    if s_lower in short_map:
        return short_map[s_lower]

    # try to parse as a date
    try:
        dt = parse_date(s, dayfirst=True, fuzzy=True)
        return calendar.day_name[dt.weekday()].lower()  # monday, tuesday...
    except Exception:
        pass

    # fallback: try to find any weekday substring inside the string
    for wk in WEEK_ORDER + ["sunday"]:
        if wk in s_lower:
            return wk

    return None

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

def cell_has_class(val, period_name=None):
    """
    Return True if this cell counts as a class period for counting purposes.
    Rules:
      - Empty/NaN -> False
      - For zero period (period_name 'p0', case-insensitive): only count if 'skill' appears in the cell text (case-insensitive)
      - If cell explicitly indicates 'zero pd' / '0 pd' / 'zero' -> False unless it contains 'skill'
      - All other non-empty cells count as class
    """
    if pd.isna(val):
        return False
    s = str(val).strip()
    if s == "":
        return False
    s_lower = s.lower()

    # p0 special handling: only count if it contains 'skill'
    if period_name and period_name.lower() == "p0":
        return "skill" in s_lower

    # explicit zero pd indicators -> ignore unless mentions skill
    if (("zero pd" in s_lower) or (s_lower == "0 pd") or (s_lower == "zero")) and ("skill" not in s_lower):
        return False

    # otherwise counted
    return True

def count_periods_for_rows(rows, expected_periods):
    """
    Count total periods and periods per day for a given teacher rows DataFrame.
    Uses cell_has_class to decide counting, particularly for p0.
    Returns (total, per_day_list) where per_day_list is ordered by weekday order if possible.
    """
    total = 0
    per_day = []
    if rows.empty:
        return total, per_day

    for day_name, grp in rows.groupby('day'):
        day_count = 0
        for _, r in grp.iterrows():
            for p in expected_periods:
                v = r.get(p, None)
                if cell_has_class(v, p):
                    day_count += 1
        per_day.append({"day": day_name, "periods_on_day": day_count})
        total += day_count

    # sort per_day by weekday order if possible, otherwise unknowns go last
    def _day_sort_key(day_val):
        dn = normalize_day_value(day_val)
        return WEEK_MAP.get(dn, 999)
    per_day_sorted = sorted(per_day, key=lambda x: _day_sort_key(x["day"]))
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
    selected_name = st.selectbox(
        "Aapka naam chuniye (type kar ke search kar sakte hain):",
        options=options,
        index=0,
        key="teacher_selectbox"
    )
with col2:
    view_button = st.button("View my weekly timetable")

with st.expander("Dekhen: sabhi naam (copy/paste ke liye)"):
    st.write(teachers_all)

# ---------- Handle view request ----------
if view_button:
    if selected_name == placeholder:
        st.warning("Kripya apna naam select kariye.")
    else:
        # check if already exhausted
        if st.session_state.successful_views >= MAX_ATTEMPTS:
            st.session_state.locked = True
            st.error("Aapne adhiktam sankhya (maximum) timetable views is session mein use kar liye hain. Access blocked.")
        else:
            name_choice = selected_name.strip()
            teacher_rows = tt[tt['tname'].str.lower() == name_choice.lower()].copy()
            if teacher_rows.empty:
                # extremely unlikely because selection is from list, but handle gracefully
                st.error("Selected name not found in the timetable. Kripya admin se sampark karein.")
            else:
                # Display timetable — this counts as one successful view
                next_count = st.session_state.successful_views + 1
                views_left_after = MAX_ATTEMPTS - next_count

                st.success(f"Aapka timetable mil gaya: {name_choice}")

                # Sort day-wise (Mon → Tue → Wed → Thu → Fri → Sat)
                try:
                    teacher_rows = teacher_rows.copy()
                    # create normalized day and mapped order (unknown days get large index)
                    teacher_rows['day_norm'] = teacher_rows['day'].apply(normalize_day_value)
                    teacher_rows['day_order'] = teacher_rows['day_norm'].map(WEEK_MAP).fillna(999).astype(int)
                    teacher_rows['_orig_idx'] = teacher_rows.index

                    # Sort first by day_order, then by original index for stable display
                    teacher_rows = teacher_rows.sort_values(by=['day_order', '_orig_idx'])

                    # remove helper cols if present
                    for c in ['day_norm', 'day_order', '_orig_idx']:
                        if c in teacher_rows.columns:
                            teacher_rows = teacher_rows.drop(columns=[c])
                except Exception:
                    # fallback to original alphabetical if anything goes wrong
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

                # increment successful view counter
                st.session_state.successful_views = next_count

                # Post-display warnings based on remaining allowed views
                if views_left_after == 2:
                    st.warning("Dhyaan: Aapke paas ab sirf 2 aur mauke (attempts) shesh hain. Kripya dhyaan se apna naam chunen.")
                elif views_left_after == 1:
                    st.error("Aakhri mauka: Ab keval 1 antim prayas (last attempt) shesh hai. Kripya sahi naam chunen — yeh antim mauka hai.")
                elif views_left_after == 0:
                    st.info("Aapne abhi apna antim (5th) view istemal kiya. Agla view allowed nahi hoga.")
                    st.session_state.locked = True

                # Optional reset button removed from main UI to avoid bypassing the 5 attempts
                # (If an admin reset is required, add a protected mechanism.)

# ---------- Footer ----------
st.caption(f"Session successful displays used: {st.session_state.successful_views} / {MAX_ATTEMPTS}")
preview_left = MAX_ATTEMPTS - st.session_state.successful_views
if preview_left <= 2 and preview_left > 0:
    st.warning(f"Please Note: Aapke paas ab {preview_left} successful timetable views shesh hain. Kripya Apne timetable me hi interested rahe ")
st.caption("Thank you for your prompt action. Applicable from Monday i.e. 27 Nov onwards")
