%%writefile app.py
import os, re, calendar
from datetime import date, datetime
import requests, streamlit as st
import matplotlib.pyplot as plt
from db import (init_db, save_mood_log, save_manual_mood, MOOD_LABELS,
                 get_mood_logs_for_month, get_user_mood_history,
                 get_all_employee_mood_logs, get_latest_mood_per_employee,
                 NLP_TO_MOOD_LABEL)
from auth import (make_token, read_token, get_user, username_taken, create_user,
                   verify_user, set_password, check_pw, new_otp, save_otp, check_otp)
from email_utils import send_otp

st.set_page_config(page_title="MoodMentor",  layout="wide")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

## ---- Palette: lavender gradient background + royal blue + coral accent ----
BRAND_GREEN = "#4C6EF5"        # primary royal blue — buttons, active states, links
BRAND_GREEN_DARK = "#3B57D6"   # deeper blue — hover state
PINE_DEEPER = "#232A55"        # deep indigo-navy — headings
ACCENT = "#E8735C"             # coral — eyebrow labels, streak highlights
ACCENT_LIGHT = "#F3A392"       # pale coral — soft badges, hover glows
INK = "#232A55"
MUTED = "#6b6f8c"
BG = "#EDEBFB"                 # light lavender canvas (used as CSS fallback)
BG_TOP = "#F1EEFC"
BG_BOTTOM = "#C6C2EF"
CARD_BORDER = "#e6e3f6"

MOOD_STYLE = {
    "Amazing": {"emoji": "😂", "color": "#1abc9c"},
    "Happy":   {"emoji": "😃", "color": "#2ecc71"},
    "Normal":  {"emoji": "🙂", "color": "#3498db"},
    "Sad":     {"emoji": "😟", "color": "#e67e22"},
    "Angry":   {"emoji": "😠", "color": "#e74c3c"},
}
def style_for(label):
    return MOOD_STYLE.get(label, {"emoji": "⬜", "color": "#bdbdbd"})

MOOD_TO_NUM = {"Amazing": 2, "Happy": 1, "Normal": 0, "Sad": -1, "Angry": -2}

def inject_css():
    st.markdown(f"""
    <style>
        .stApp {{
            background: linear-gradient(150deg, {BG_TOP} 0%, #DAD6F6 45%, {BG_BOTTOM} 100%);
            background-attachment: fixed;
        }}
        #MainMenu, footer {{visibility: hidden;}}
        html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}

        /* Base text color for anything on the app background that isn't inside a
           styled component — prevents theme-inherited white-on-light or
           black-on-dark text. */
        .stApp, .stApp p, .stApp span, .stApp li, .stMarkdown {{ color: {INK}; }}
        .stApp h1, .stApp h2, .stApp h3, .stApp h4 {{ color: {PINE_DEEPER}; }}
        .stCaption, [data-testid="stCaptionContainer"] {{ color: {MUTED} !important; }}

        /* ================= Sidebar — colorful panel, guaranteed-legible text ================= */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #E9E4FB 0%, #F4F1FD 40%, #FBFAFF 100%);
            border-right: 1px solid {CARD_BORDER};
        }}
        section[data-testid="stSidebar"] * {{ color: {INK} !important; }}
        section[data-testid="stSidebar"] hr {{ border-color: {CARD_BORDER} !important; }}
        .mm-sb-brand {{
            display:flex; align-items:center; gap:10px; padding:4px 4px 18px 4px;
        }}
        .mm-sb-logo {{
            width:34px; height:34px; border-radius:10px; flex-shrink:0;
            background: linear-gradient(135deg, {BRAND_GREEN} 0%, {ACCENT} 100%);
            display:flex; align-items:center; justify-content:center;
            font-size:17px; box-shadow: 0 3px 10px rgba(76,110,245,0.35);
        }}
        .mm-sb-nav-label {{
            font-size:11px; font-weight:800; letter-spacing:.08em; color:{ACCENT} !important;
            text-transform:uppercase; padding: 4px 4px 6px 4px;
        }}
        .mm-sb-user {{
            display:flex; align-items:center; gap:10px; padding: 10px 6px;
            background:#ffffff; border-radius:14px; border:1px solid {CARD_BORDER};
            margin-bottom:10px;
        }}
        .mm-sb-avatar {{
            width:36px; height:36px; border-radius:50%; flex-shrink:0;
            background: linear-gradient(135deg, {ACCENT} 0%, {BRAND_GREEN} 100%);
            color:#fff !important; display:flex; align-items:center; justify-content:center;
            font-weight:800; font-size:15px;
        }}

        section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 2px; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label {{
            padding: 11px 14px; border-radius: 10px; margin-bottom: 2px;
            transition: background 0.15s ease;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label p {{
            color: {INK} !important; font-weight: 600; font-size: 14.5px;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
            background: #EEEBFC;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
            background: linear-gradient(90deg, {BRAND_GREEN} 0%, #7C97F8 100%);
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {{
            color: #ffffff !important; font-weight: 700;
        }}
        /* hide the default circular radio dot — the pill itself shows selection */
        section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{
            display: none;
        }}
        section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {{
            color: {MUTED} !important;
        }}
        section[data-testid="stSidebar"] div.stButton > button {{
            background: #ffffff; border: 1.5px solid {CARD_BORDER};
            color: {INK} !important;
        }}
        section[data-testid="stSidebar"] div.stButton > button:hover {{
            background: #F1EEFC; border-color: {ACCENT};
        }}

        /* ================= Generic card ================= */
        .mm-card {{
            background: #ffffff; border-radius: 18px; padding: 22px 24px; margin-bottom: 18px;
            border: 1px solid {CARD_BORDER};
            box-shadow: 0 4px 16px rgba(76,70,190,0.08);
        }}
        .mm-card, .mm-card p, .mm-card span, .mm-card li {{ color: {INK}; }}
        .mm-card h4 {{ margin-top: 0; color: {PINE_DEEPER}; }}

        /* ================= Metric tiles (Home page) ================= */
        .mm-metric {{
            background: #ffffff; border-radius: 16px; padding: 18px 18px 16px;
            border: 1px solid {CARD_BORDER}; border-top: 3px solid {BRAND_GREEN};
            text-align: center; box-shadow: 0 4px 14px rgba(76,70,190,0.08);
        }}
        .mm-metric .mm-label {{ color: {MUTED}; font-size: 12px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }}
        .mm-metric .mm-value {{ font-size: 27px; font-weight: 800; color: {PINE_DEEPER}; margin-top: 6px; }}
        .mm-metric .mm-sub {{ font-size: 12px; color: {ACCENT}; font-weight: 700; margin-top: 3px; }}

        /* ================= Badges ================= */
        .mm-badge-positive {{
            display:inline-block; background:#EAEEFE; color:{BRAND_GREEN_DARK};
            padding:3px 10px; border-radius:20px; font-size:12.5px; font-weight:700;
            border: 1px solid rgba(76,110,245,0.2);
        }}
        .mm-eyebrow {{
            color: {ACCENT}; font-size: 12px; font-weight: 800; letter-spacing: .08em;
            text-transform: uppercase;
        }}

        /* ================= Top header bar ================= */
        .mm-header {{
            display:flex; justify-content:space-between; align-items:center;
            padding-bottom: 10px; margin-bottom: 14px;
            border-bottom: 1px solid rgba(35,42,85,0.1);
        }}
        .mm-header h2 {{ margin: 0; color:{PINE_DEEPER}; }}
        .mm-header p {{ margin: 0; color:{MUTED}; font-size: 13px; }}

        /* ================= Buttons ================= */
        div.stButton > button, .stFormSubmitButton > button {{
            border-radius: 10px; font-weight: 600; border: 1.5px solid {CARD_BORDER};
            background: #ffffff; color: {INK} !important;
            transition: all 0.15s ease;
        }}
        div.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
            background: linear-gradient(90deg, {BRAND_GREEN} 0%, #7C97F8 100%);
            border-color: {BRAND_GREEN}; color: #ffffff !important;
        }}
        div.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
            background: linear-gradient(90deg, {BRAND_GREEN_DARK} 0%, {BRAND_GREEN} 100%);
            border-color: {BRAND_GREEN_DARK};
        }}
        div.stButton > button:not([kind="primary"]):hover {{
            border-color: {ACCENT}; color: {BRAND_GREEN_DARK} !important;
        }}

        /* ================= Welcome / auth split screen ================= */
        .welcome-box {{
            background: transparent;
            padding: 20px 4px; color: {INK}; height: 100%;
        }}
        .welcome-box h1, .welcome-box h2 {{ color: {PINE_DEEPER}; }}
        .welcome-box p {{ color: {MUTED}; }}
        .mm-brand-dark {{ color: {BRAND_GREEN}; }}
        .auth-card {{
            background: #ffffff; border-radius: 20px; padding: 30px 32px;
            border: 1px solid {CARD_BORDER}; box-shadow: 0 10px 28px rgba(76,70,190,0.14);
        }}
        .auth-card h3 {{ color: {PINE_DEEPER}; }}
        .auth-card, .auth-card p, .auth-card label {{ color: {INK}; }}

        /* Inputs: force readable text/background regardless of Streamlit theme */
        .stTextInput input, .stTextArea textarea {{
            background: #ffffff !important; color: {INK} !important;
            border: 1.5px solid {CARD_BORDER} !important;
        }}
        [data-testid="stDataFrame"] {{ color: {INK}; }}
    </style>
    """, unsafe_allow_html=True)

def donut_chart(counts: dict, size=2.6):
    """Small donut chart themed to the mood/emotion colors — used for
    'Top Emotions' / 'Emotion Distribution' style widgets."""
    labels, values, colors = [], [], []
    for k, v in counts.items():
        if v > 0:
            labels.append(k); values.append(v)
            colors.append(style_for(k)["color"])
    if not values:
        return None
    fig, ax = plt.subplots(figsize=(size, size))
    ax.pie(values, colors=colors, startangle=90, wedgeprops=dict(width=0.38, edgecolor="white"))
    ax.set(aspect="equal")
    fig.patch.set_alpha(0.0)
    return fig

# A varied palette (blue / coral / teal / violet / amber / mint) so bar charts
# don't render as flat single-tone bars.
CHART_PALETTE = ["#4C6EF5", "#E8735C", "#2FB4A6", "#9C6ADE",
                  "#F0B429", "#3AC7B0", "#F2789F", "#6BA4F7"]

def colored_bar_chart(data: dict, size=(5.2, 3.0)):
    """Horizontal-friendly colorful bar chart replacing st.bar_chart, so each
    bar gets a distinct color instead of one flat theme color."""
    if not data:
        return None
    labels = list(data.keys())
    values = list(data.values())
    colors = [CHART_PALETTE[i % len(CHART_PALETTE)] for i in range(len(labels))]
    fig, ax = plt.subplots(figsize=size)
    ax.bar(labels, values, color=colors, edgecolor="white", linewidth=1.2, width=0.65)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(axis="x", colors=INK, labelsize=9, rotation=20)
    ax.tick_params(axis="y", colors=MUTED, labelsize=8)
    ax.set_yticklabels([])
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")
    fig.tight_layout()
    return fig

def metric_tile(label, value, sub=None):
    sub_html = f"<div class='mm-sub'>{sub}</div>" if sub else ""
    st.markdown(
        f"<div class='mm-metric'><div class='mm-label'>{label}</div>"
        f"<div class='mm-value'>{value}</div>{sub_html}</div>",
        unsafe_allow_html=True,
    )

SENTIMENT_COLORS = {"pos": "#F0B429", "neg": "#E8735C", "neu": "#4C6EF5"}
SENTIMENT_LABELS = {"pos": "Positive", "neg": "Negative", "neu": "Neutral"}

def sentiment_bar_chart(scores: dict, size=(5.4, 2.8)):
    """Bar chart of the VADER Positive/Negative/Neutral components (compound
    is shown separately as a headline number) — matches the
    'SENTIMENT - POSITIVE' style widget."""
    keys = [k for k in ("pos", "neg", "neu") if k in scores]
    if not keys:
        return None
    labels = [SENTIMENT_LABELS[k] for k in keys]
    values = [scores[k] for k in keys]
    colors = [SENTIMENT_COLORS[k] for k in keys]
    fig, ax = plt.subplots(figsize=size)
    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=1.2, width=0.55)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01, f"{v:.2f}",
                ha="center", va="bottom", fontsize=9, color=INK, fontweight="bold")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(axis="x", colors=INK, labelsize=10)
    ax.set_yticks([])
    ax.set_ylim(0, max(values + [0.1]) * 1.25)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")
    fig.tight_layout()
    return fig

def styled_table(rows, headers=None):
    """Renders a list-of-dicts as a colorful HTML table instead of
    st.dataframe (which inherits Streamlit's dark theme and shows up black)."""
    if not rows:
        st.caption("No data yet.")
        return
    headers = headers or list(rows[0].keys())
    thead = "".join(f"<th>{h}</th>" for h in headers)
    trs = []
    for i, row in enumerate(rows):
        bg = "#F6F4FE" if i % 2 == 0 else "#ffffff"
        tds = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
        trs.append(f"<tr style='background:{bg}'>{tds}</tr>")
    html = f"""
    <div style="overflow-x:auto;border-radius:12px;border:1px solid {CARD_BORDER}">
    <table style="width:100%;border-collapse:collapse;font-size:13.5px;">
      <thead>
        <tr style="background:linear-gradient(90deg,{BRAND_GREEN} 0%, #7C97F8 100%);">
          {thead.replace('<th>', f'<th style="padding:10px 14px;text-align:left;color:#fff;font-weight:700;">')}
        </tr>
      </thead>
      <tbody>
        {''.join(trs).replace('<td>', f'<td style="padding:9px 14px;color:{INK};border-top:1px solid {CARD_BORDER};">')}
      </tbody>
    </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

inject_css()


@st.cache_resource
def setup(): init_db()
setup()

if "page" not in st.session_state: st.session_state.page = "welcome"
if "show_auth_panel" not in st.session_state: st.session_state.show_auth_panel = False
if "auth_mode" not in st.session_state: st.session_state.auth_mode = "login"
if "token" not in st.session_state: st.session_state.token = None
if "email" not in st.session_state: st.session_state.email = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "cal_year" not in st.session_state: st.session_state.cal_year = date.today().year
if "cal_month" not in st.session_state: st.session_state.cal_month = date.today().month
if "today_mood_saved" not in st.session_state: st.session_state.today_mood_saved = False
if "nav" not in st.session_state: st.session_state.nav = "Home"

def goto_auth(mode): st.session_state.auth_mode = mode; st.rerun()

def valid_pw(pw):
    return len(pw) >= 8 and re.search(r"[A-Za-z]", pw) and re.search(r"[0-9]", pw)


if st.session_state.token:
    user = read_token(st.session_state.token)
    if user:
        role = user.get("role", "employee")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}

        with st.sidebar:
            st.markdown(
                f"<div class='mm-sb-brand'>"
                f"<div class='mm-sb-logo'>🧠</div>"
                f"<span style='font-size:19px;font-weight:800;color:{INK} !important'>Mood<span style='color:{BRAND_GREEN} !important'>Mentor</span></span>"
                f"</div>", unsafe_allow_html=True,
            )
            NAV_ICONS = {
                "Home": "🏠", "Analyze Text": "📝", "Journal": "📔",
                "Wellness Chat": "💬", "Dashboard": "📊", "Reports": "📈",
            }
            if role == "employee":
                nav_options = ["Home", "Analyze Text", "Journal", "Wellness Chat", "Dashboard"]
            else:
                nav_options = ["Reports"]
            st.markdown("<div class='mm-sb-nav-label'>Main</div>", unsafe_allow_html=True)
            st.session_state.nav = st.radio(
                "Navigate", nav_options,
                index=nav_options.index(st.session_state.nav) if st.session_state.nav in nav_options else 0,
                label_visibility="collapsed",
                format_func=lambda x: f"{NAV_ICONS.get(x, '•')}  {x}",
            )
            st.divider()
            initials = "".join(p[0].upper() for p in user["username"].split()[:2]) or "U"
            st.markdown(
                f"<div class='mm-sb-user'>"
                f"<div class='mm-sb-avatar'>{initials}</div>"
                f"<div><div style='font-weight:700;font-size:13.5px'>{user['username']}</div>"
                f"<div style='font-size:11.5px;color:{MUTED} !important'>{user['email']} · {role.capitalize()}</div></div>"
                f"</div>", unsafe_allow_html=True,
            )
            if st.button("Log out", use_container_width=True):
                st.session_state.token = None
                st.session_state.page = "welcome"
                st.session_state.show_auth_panel = False
                st.rerun()

        greeting = "Good Morning" if datetime.now().hour < 12 else (
            "Good Afternoon" if datetime.now().hour < 18 else "Good Evening")
        st.markdown(
            f"<div class='mm-header'><div><h2>{greeting}, {user['username']}! </h2>"
            f"<p>Here's your emotional wellness overview.</p></div></div>",
            unsafe_allow_html=True,
        )

        if role == "employee":
            section = st.session_state.nav

            if section == "Home":
                history_all = get_user_mood_history(user["id"], limit=500)
                latest = history_all[0] if history_all else None
                today_count = sum(1 for h in history_all if h["mood_date"] == date.today())
                streak = 0
                day_ptr = date.today()
                day_set = {h["mood_date"] for h in history_all}
                while day_ptr in day_set:
                    streak += 1
                    day_ptr = date.fromordinal(day_ptr.toordinal() - 1)

                positive_count = sum(1 for h in history_all if h["sentiment"] in ("Amazing", "Happy"))
                overall_score = int(100 * positive_count / len(history_all)) if history_all else 0

                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    if latest:
                        s = style_for(latest["sentiment"])
                        metric_tile("Current Mood", f"{s['emoji']} {latest['sentiment']}")
                    else:
                        metric_tile("Current Mood", "—")
                with m2:
                    metric_tile("Overall Score", f"{overall_score}%", "Positive" if overall_score >= 50 else "Needs care")
                with m3:
                    metric_tile("Entries Today", today_count)
                with m4:
                    metric_tile("Current Streak", f"{streak} Days")

                st.write("")
                st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                st.subheader("How Do You Feel?")
                now = datetime.now()
                st.caption(f"📅 {now.strftime('%Y-%m-%d')}  🕒 {now.strftime('%H:%M')}")

                cols = st.columns(len(MOOD_LABELS))
                picked = st.session_state.get("picked_mood")
                for col, label in zip(cols, MOOD_LABELS):
                    s = style_for(label)
                    with col:
                        st.markdown(
                            f"<div style='text-align:center;font-size:36px'>{s['emoji']}</div>"
                            f"<div style='text-align:center;color:{s['color']};font-weight:600'>{label}</div>",
                            unsafe_allow_html=True,
                        )
                        if st.button("Select", key=f"pick_{label}", use_container_width=True):
                            st.session_state.picked_mood = label

                st.write("")
                confirm_col = st.columns([3, 1, 3])[1]
                with confirm_col:
                    disabled = picked is None
                    if st.button("Save mood", type="primary", disabled=disabled,
                                 use_container_width=True):
                        save_manual_mood(user["id"], st.session_state.picked_mood)
                        st.session_state.today_mood_saved = True
                        st.session_state.picked_mood = None
                        st.rerun()

                if st.session_state.today_mood_saved:
                    st.success("Today's mood saved!")
                    st.session_state.today_mood_saved = False
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                st.subheader("Your Mood Calendar")

                nav_l, nav_mid, nav_r = st.columns([1, 3, 1])
                if nav_l.button("← Prev"):
                    m, y = st.session_state.cal_month - 1, st.session_state.cal_year
                    if m == 0: m, y = 12, y - 1
                    st.session_state.cal_month, st.session_state.cal_year = m, y
                    st.rerun()
                if nav_r.button("Next →"):
                    m, y = st.session_state.cal_month + 1, st.session_state.cal_year
                    if m == 13: m, y = 1, y + 1
                    st.session_state.cal_month, st.session_state.cal_year = m, y
                    st.rerun()
                nav_mid.markdown(
                    f"<h4 style='text-align:center'>{calendar.month_name[st.session_state.cal_month]} "
                    f"{st.session_state.cal_year}</h4>", unsafe_allow_html=True,
                )

                logs = get_mood_logs_for_month(user["id"], st.session_state.cal_year,
                                                st.session_state.cal_month)
                by_day = {row["mood_date"].day: row for row in logs}

                weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(
                    st.session_state.cal_year, st.session_state.cal_month
                )
                day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
                header_cols = st.columns(7)
                for c, name in zip(header_cols, day_names):
                    c.markdown(f"**{name}**")

                for week in weeks:
                    cols = st.columns(7)
                    for col, day_num in zip(cols, week):
                        if day_num == 0:
                            col.write("")
                            continue
                        entry = by_day.get(day_num)
                        s = style_for(entry["sentiment"] if entry else None)
                        time_label = entry["created_at"].strftime("%H:%M") if entry else ""
                        col.markdown(
                            f"<div title='{time_label}' style='text-align:center;padding:6px;border-radius:8px;"
                            f"background:{s['color']}22;border:1px solid {s['color']}'>"
                            f"<div style='font-size:11px'>{day_num}</div>"
                            f"<div style='font-size:20px'>{s['emoji']}</div>"
                            f"<div style='font-size:9px;color:#888'>{time_label}</div></div>",
                            unsafe_allow_html=True,
                        )

                legend = " · ".join(f"{style_for(l)['emoji']} {l}" for l in MOOD_LABELS)
                st.caption(f"{legend} · ⬜ No entry logged  (hover/see time under each day)")
                st.markdown("</div>", unsafe_allow_html=True)

            elif section == "Analyze Text":
                st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                st.subheader(" Analyze Text")
                st.caption("Enter your text below and let AI analyze your emotions.")
                text_in = st.text_area("Type or paste your text here…", height=160,
                                        label_visibility="collapsed",
                                        placeholder="Type or paste your text here…")
                st.caption(f"{len(text_in)}/5000 characters")
                if st.button("Analyze Now", type="primary", use_container_width=True):
                    if not text_in.strip():
                        st.warning("Write something first.")
                    else:
                        with st.spinner("Running NLP analysis…"):
                            try:
                                resp = requests.post(
                                    f"{BACKEND_URL}/analyze-text",
                                    json={"text": text_in},
                                    headers=headers, timeout=120,
                                )
                            except requests.exceptions.RequestException as e:
                                st.error(f"Could not reach backend: {e}"); resp = None
                        if resp is not None:
                            if resp.status_code != 200:
                                st.error("Analysis failed.")
                            else:
                                r = resp.json()
                                confidence = r.get("emotion_confidence")
                                save_mood_log(
                                    user["id"], r["final_sentiment"], r["final_emotion"],
                                    r["sentiment_scores"]["compound"], text_in,
                                    confidence=confidence,
                                )
                                st.markdown("</div>", unsafe_allow_html=True)
                                st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                                st.subheader("Analysis Results")

                                lang = r.get("detected_language") or r.get("language")
                                meta_bits = []
                                if lang: meta_bits.append(f"🌐 Detected Language: **{lang}**")
                                if confidence is not None: meta_bits.append(f"🎯 Confidence: **{confidence:.0%}**")
                                if meta_bits:
                                    st.caption(" &nbsp;·&nbsp; ".join(meta_bits))

                                rc1, rc2 = st.columns(2)
                                with rc1:
                                    st.write("**Overall Emotion**")
                                    mood_label = NLP_TO_MOOD_LABEL.get(r["final_sentiment"], "Normal")
                                    s = style_for(mood_label)
                                    st.markdown(f"### {s['emoji']} {r['final_emotion']}", unsafe_allow_html=True)
                                    badge = "mm-badge-positive"
                                    st.markdown(
                                        f"<span class='{badge}'>{r['final_sentiment']}</span>"
                                        f"&nbsp;&nbsp;Compound Score: **{r['sentiment_scores']['compound']:.2f}**",
                                        unsafe_allow_html=True,
                                    )
                                with rc2:
                                    st.write("**Emotion Distribution**")
                                    fig = donut_chart(r["emotion_scores"])
                                    if fig: st.pyplot(fig, use_container_width=False)
                                    else:
                                        bfig = colored_bar_chart(r["emotion_scores"])
                                        if bfig: st.pyplot(bfig, use_container_width=False)

                                st.write("**Sentiment Breakdown (VADER)**")
                                sfig = sentiment_bar_chart(r["sentiment_scores"])
                                if sfig: st.pyplot(sfig, use_container_width=False)

                                recommendation = r.get("wellness_recommendation") or r.get("recommendation")
                                if recommendation:
                                    st.write("**Wellness Recommendation**")
                                    st.markdown(
                                        f"<div style='background:#EAEEFE;border:1px solid rgba(76,110,245,0.25);"
                                        f"border-radius:12px;padding:12px 16px;color:{INK}'>💡 {recommendation}</div>",
                                        unsafe_allow_html=True,
                                    )
                st.markdown("</div>", unsafe_allow_html=True)

            elif section == "Journal":
                st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                st.subheader(" Journal")
                journal_text = st.text_area(
                    "Write about how you're feeling today", height=150,
                    placeholder="Your note here...",
                )
                if st.button("Analyze my entry"):
                    if not journal_text.strip():
                        st.warning("Write something first.")
                    else:
                        with st.spinner("Running NLP analysis…"):
                            try:
                                resp = requests.post(
                                    f"{BACKEND_URL}/analyze-text",
                                    json={"text": journal_text},
                                    headers=headers, timeout=120,
                                )
                            except requests.exceptions.RequestException as e:
                                st.error(f"Could not reach backend: {e}"); resp = None
                        if resp is not None:
                            if resp.status_code != 200:
                                st.error("Analysis failed.")
                            else:
                                r = resp.json()
                                confidence = r.get("emotion_confidence")
                                save_mood_log(
                                    user["id"], r["final_sentiment"], r["final_emotion"],
                                    r["sentiment_scores"]["compound"], journal_text,
                                    confidence=confidence,
                                )
                                conf_str = f", Confidence: **{confidence:.0%}**" if confidence is not None else ""
                                lang = r.get("detected_language") or r.get("language")
                                lang_str = f", Language: **{lang}**" if lang else ""
                                st.success(f"Saved! Sentiment: **{r['final_sentiment']}**, "
                                           f"Emotion: **{r['final_emotion']}**{conf_str}{lang_str}")
                                jc1, jc2 = st.columns(2)
                                with jc1:
                                    st.write("**Emotion Distribution**")
                                    bfig = colored_bar_chart(r["emotion_scores"])
                                    if bfig: st.pyplot(bfig, use_container_width=False)
                                with jc2:
                                    st.write("**Sentiment Breakdown**")
                                    sfig = sentiment_bar_chart(r["sentiment_scores"])
                                    if sfig: st.pyplot(sfig, use_container_width=False)
                                recommendation = r.get("wellness_recommendation") or r.get("recommendation")
                                if recommendation:
                                    st.markdown(
                                        f"<div style='background:#EAEEFE;border:1px solid rgba(76,110,245,0.25);"
                                        f"border-radius:12px;padding:12px 16px;color:{INK};margin-top:8px'>💡 {recommendation}</div>",
                                        unsafe_allow_html=True,
                                    )
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                st.subheader(" Or upload a file")
                uploaded = st.file_uploader("Choose a CSV or TXT file", type=["csv", "txt"])
                if uploaded is not None and st.button("Run NLP Analysis on file"):
                    files = {"file": (uploaded.name, uploaded.getvalue())}
                    with st.spinner("Running multilingual NLP pipeline…"):
                        try:
                            resp = requests.post(f"{BACKEND_URL}/analyze", files=files,
                                                  headers=headers, timeout=120)
                        except requests.exceptions.RequestException as e:
                            st.error(f"Could not reach backend: {e}"); resp = None
                    if resp is not None:
                        if resp.status_code != 200:
                            st.error("Analysis failed.")
                        else:
                            r = resp.json()
                            confidence = r.get("emotion_confidence")
                            save_mood_log(
                                user["id"], r["final_sentiment"], r["final_emotion"],
                                r["sentiment_scores"]["compound"], r.get("cleaned_text", ""),
                                confidence=confidence,
                            )
                            conf_str = f", Confidence: **{confidence:.0%}**" if confidence is not None else ""
                            st.success(f"Saved! Sentiment: **{r['final_sentiment']}**, "
                                       f"Emotion: **{r['final_emotion']}**{conf_str}")
                            bfig = colored_bar_chart(r["emotion_scores"])
                            if bfig: st.pyplot(bfig, use_container_width=False)
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                st.subheader(" Past entries")
                history = [h for h in get_user_mood_history(user["id"], limit=20)
                           if h["journal_text"]]
                if not history:
                    st.caption("No journal entries yet.")
                for h in history:
                    s = style_for(h["sentiment"])
                    conf_str = f" · Confidence: {h['confidence']:.0%}" if h.get("confidence") is not None else ""
                    with st.expander(
                        f"{s['emoji']} {h['sentiment']} — {h['created_at'].strftime('%Y-%m-%d %H:%M')}{conf_str}"
                    ):
                        st.write(h["journal_text"])
                st.markdown("</div>", unsafe_allow_html=True)

            elif section == "Wellness Chat":
                st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                st.subheader("Wellness Chat")
                st.caption("A supportive space to talk about how you're feeling. "
                           "Not a substitute for professional care.")
                chat_box = st.container(height=450)
                with chat_box:
                    for turn in st.session_state.chat_history:
                        with st.chat_message(turn["role"]):
                            st.write(turn["content"])

                user_msg = st.chat_input("How are you feeling today?")
                if user_msg:
                    st.session_state.chat_history.append({"role": "user", "content": user_msg})
                    recent_history = st.session_state.chat_history[-10:-1]
                    try:
                        resp = requests.post(
                            f"{BACKEND_URL}/chat",
                            json={"message": user_msg, "history": recent_history},
                            headers=headers, timeout=60,
                        )
                        reply = resp.json()["reply"] if resp.status_code == 200 else \
                            "Sorry, I couldn't reach the wellness assistant right now."
                    except requests.exceptions.RequestException:
                        reply = "Sorry, I couldn't reach the wellness assistant right now."
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                    st.rerun()

                if st.session_state.chat_history and st.button("Clear chat"):
                    st.session_state.chat_history = []
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            elif section == "Dashboard":
                history = get_user_mood_history(user["id"], limit=200)
                if not history:
                    st.info("No entries yet — pick a mood on Home or write a journal entry to see your dashboard.")
                else:
                    counts = {label: 0 for label in MOOD_LABELS}
                    for h in history:
                        if h["sentiment"] in counts:
                            counts[h["sentiment"]] += 1

                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                        st.write("**Mood distribution**")
                        fig = donut_chart(counts)
                        if fig: st.pyplot(fig, use_container_width=False)
                        else:
                            bfig = colored_bar_chart(counts)
                            if bfig: st.pyplot(bfig, use_container_width=False)
                        st.markdown("</div>", unsafe_allow_html=True)
                    with c2:
                        st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                        st.write("**Mood trend over time**")
                        by_date = {}
                        for h in history:
                            d = h["mood_date"]
                            by_date.setdefault(d, []).append(MOOD_TO_NUM.get(h["sentiment"], 0))
                        trend = {str(d): sum(v) / len(v) for d, v in sorted(by_date.items())}
                        st.line_chart(trend, color="#4C6EF5")
                        st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                    st.write("**Emotions detected from journal entries**")
                    emo_counts = {}
                    for h in history:
                        if h["source"] == "nlp" and h["emotion"]:
                            emo_counts[h["emotion"]] = emo_counts.get(h["emotion"], 0) + 1
                    if emo_counts:
                        bfig = colored_bar_chart(emo_counts)
                        if bfig: st.pyplot(bfig, use_container_width=False)
                    else:
                        st.caption("No journal-based emotion data yet.")
                    st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
                    st.write("**Recent activity**")
                    table_rows = [{
                        "Date": h["mood_date"], "Time": h["created_at"].strftime("%H:%M"),
                        "Mood": f"{style_for(h['sentiment'])['emoji']} {h['sentiment']}",
                        "Confidence": f"{h['confidence']:.0%}" if h.get("confidence") is not None else "—",
                        "Source": h["source"],
                    } for h in history[:15]]
                    styled_table(table_rows)
                    st.markdown("</div>", unsafe_allow_html=True)

        else:
            st.subheader("Employee Wellness Report")

            st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
            latest = get_latest_mood_per_employee()
            if not latest:
                st.info("No employee entries yet.")
            else:
                st.write("**Latest mood per employee**")
                table_rows = [{
                    "Employee": row["username"],
                    "Email": row["email"],
                    "Date": row["mood_date"],
                    "Time": row["created_at"].strftime("%H:%M"),
                    "Mood": f"{style_for(row['sentiment'])['emoji']} {row['sentiment']}",
                    "Emotion": row["emotion"],
                } for row in latest]
                styled_table(table_rows)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div class='mm-card'>", unsafe_allow_html=True)
            st.write("**Team mood trend (last 30 days)**")
            history = get_all_employee_mood_logs(limit_days=30)
            if not history:
                st.info("Not enough data yet to draw a trend chart.")
            else:
                by_date = {}
                for row in history:
                    d = row["mood_date"]
                    by_date.setdefault(d, []).append(MOOD_TO_NUM.get(row["sentiment"], 0))
                trend = {str(d): sum(v) / len(v) for d, v in sorted(by_date.items())}
                st.line_chart(trend, color="#4C6EF5")
                st.caption("Average mood score per day across all employees "
                           "(2 = Amazing, 1 = Happy, 0 = Normal, -1 = Sad, -2 = Angry)")
            st.markdown("</div>", unsafe_allow_html=True)

        st.stop()
    st.session_state.token = None


if st.session_state.page == "welcome":

    if not st.session_state.show_auth_panel:
        st.markdown('<div class="welcome-box">', unsafe_allow_html=True)
        st.markdown("## Mood<span class='mm-brand-dark'>Mentor</span>", unsafe_allow_html=True)
        st.markdown("#### AI-Powered Emotional Wellness Assistant")
        st.write(
            "Understand your emotions. Improve your well-being. Live your best life. "
            "Journey into your inner world through emojis, text, voice recordings, "
            "and notes — and watch your emotional landscape unfold through beautiful "
            "charts and insights."
        )
        st.markdown(
            "<div style='text-align:center;font-size:36px;padding:24px 0'>"
            "😊&nbsp;&nbsp;😐&nbsp;&nbsp;😔&nbsp;&nbsp;😠</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.write("")
        if st.button("Get Started →", type="primary", use_container_width=True):
            st.session_state.show_auth_panel = True
            st.rerun()
        st.stop()

    left, right = st.columns([3, 2])

    with left:
        st.markdown('<div class="welcome-box">', unsafe_allow_html=True)
        st.markdown("## Mood<span class='mm-brand-dark'>Mentor</span>", unsafe_allow_html=True)
        st.markdown("#### AI-Powered Emotional Wellness Assistant")
        st.write(
            "Understand your emotions. Improve your well-being. Live your best life. "
            "Journey into your inner world through emojis, text, voice recordings, "
            "and notes — and watch your emotional landscape unfold through beautiful "
            "charts and insights."
        )
        st.markdown(
            "<div style='text-align:center;font-size:36px;padding:24px 0'>"
            "😊&nbsp;&nbsp;😐&nbsp;&nbsp;😔&nbsp;&nbsp;😠</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        mode = st.session_state.auth_mode

        if mode == "login":
            st.markdown("### Welcome Back!")
            st.caption("Login to your account")
            with st.form("login"):
                email = st.text_input("Email", placeholder="Enter your email")
                pw = st.text_input("Password", type="password", placeholder="Enter your password")
                go = st.form_submit_button("Login", type="primary", use_container_width=True)
            if go:
                u = get_user(email.strip().lower())
                if not u or not check_pw(pw, u["password_hash"]):
                    st.error("Invalid email or password.")
                elif not u["is_verified"]:
                    st.warning("Verify your email first.")
                    st.session_state.email = u["email"]; goto_auth("verify")
                else:
                    st.session_state.token = make_token(u)
                    st.rerun()
            c1, c2 = st.columns(2)
            if c1.button("Sign up", use_container_width=True): goto_auth("signup")
            if c2.button("Forgot password?", use_container_width=True): goto_auth("forgot")

        elif mode == "signup":
            st.markdown("### Create Account")
            st.caption("Let's get you started")
            with st.form("signup"):
                username = st.text_input("Full Name", placeholder="Enter your full name")
                email = st.text_input("Email", placeholder="Enter your email")
                pw = st.text_input("Password", type="password", placeholder="Create password")
                role_label = st.radio("I am signing up as a:", ["Employee", "Manager"], horizontal=True)
                go = st.form_submit_button("Send OTP", type="primary", use_container_width=True)
            if go:
                email = email.strip().lower()
                role = "manager" if role_label == "Manager" else "employee"
                if len(username) < 3:
                    st.error("Username too short.")
                elif not valid_pw(pw):
                    st.error("Password needs 8+ chars, letters and numbers.")
                elif username_taken(username) or get_user(email):
                    st.error("Username or email already in use.")
                else:
                    create_user(username, email, pw, role=role)
                    code = new_otp(); save_otp(email, code, "signup")
                    ok, msg = send_otp(email, code, "signup")
                    if ok:
                        st.session_state.email = email
                        st.success("Check your email for the code.")
                        goto_auth("verify")
                    else:
                        st.error(f"Email failed: {msg}")
            if st.button("Already have an account? Login"): goto_auth("login")

        elif mode == "verify":
            email = st.session_state.email
            st.markdown("### Verify OTP")
            st.caption(f"We have sent a 6-digit code to {email}")
            with st.form("verify"):
                code = st.text_input("Code", max_chars=6, placeholder="Enter 6-digit code")
                go = st.form_submit_button("Verify OTP", type="primary", use_container_width=True)
            if go:
                if check_otp(email, code.strip(), "signup"):
                    verify_user(email)
                    st.success("Verified! Please log in.")
                    goto_auth("login")
                else:
                    st.error("Invalid or expired code.")
            if st.button("← Back to login"): goto_auth("login")

        elif mode == "forgot":
            st.markdown("### 🔑 Forgot password")
            with st.form("forgot"):
                email = st.text_input("Your account email")
                go = st.form_submit_button("Send reset code", type="primary", use_container_width=True)
            if go:
                email = email.strip().lower()
                if get_user(email):
                    code = new_otp(); save_otp(email, code, "password_reset")
                    send_otp(email, code, "password_reset")
                st.session_state.email = email
                st.info("If that email exists, a code was sent.")
                goto_auth("reset")
            if st.button("← Back to login"): goto_auth("login")

        elif mode == "reset":
            email = st.session_state.email
            st.markdown("### 🔄 Reset password")
            with st.form("reset"):
                code = st.text_input("Reset code", max_chars=6)
                pw = st.text_input("New password", type="password")
                go = st.form_submit_button("Reset", type="primary", use_container_width=True)
            if go:
                if not valid_pw(pw):
                    st.error("Password needs 8+ chars, letters and numbers.")
                elif not check_otp(email, code.strip(), "password_reset"):
                    st.error("Invalid or expired code.")
                else:
                    set_password(email, pw)
                    st.success("Password reset. Please log in.")
                    goto_auth("login")
            if st.button("← Back to login"): goto_auth("login")

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()
