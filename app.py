import os
import sqlite3
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import streamlit as st

# ---------------- CONFIG ----------------
APP_TITLE = "Balloons le Grá — DPD Collection Portal"
STAFF = ["Kevin", "Christina", "Priscilla", "Megan"]
IRELAND = ZoneInfo("Europe/Dublin")

# Confirm these before live use.
DEPOT_EMAIL = os.getenv("DPD_DEPOT_EMAIL", "CHANGE_ME@dpd.ie")
KEVIN_EMAIL = os.getenv("KEVIN_EMAIL", "CHANGE_ME@balloonslegra.ie")
ACCOUNT_REF = os.getenv("DPD_ACCOUNT_REF", "7104 L3")

COLLECTION_ADDRESS = "Balloons le Grá, Manor West Shopping Centre, Tralee, Co. Kerry, V92 KAN8"

# SMTP settings are deliberately kept outside the source code.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USERNAME)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-this-password")
DB_PATH = os.getenv("DB_PATH", "collection_log.db")
# ----------------------------------------

st.set_page_config(page_title=APP_TITLE, page_icon="📦", layout="centered")

st.markdown("""
<style>
.block-container {max-width: 850px; padding-top: 2rem;}
div.stButton > button {width:100%; min-height:3.2rem; font-size:1.05rem; font-weight:700;}
.success-box {padding:1rem; border:1px solid #ddd; border-radius:12px;}
.small {font-size:.9rem; opacity:.75;}
</style>
""", unsafe_allow_html=True)

def now():
    return datetime.now(IRELAND)

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            business_date TEXT NOT NULL,
            staff_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            initial_boxes INTEGER,
            added_boxes INTEGER,
            total_boxes INTEGER NOT NULL,
            recipient TEXT NOT NULL,
            cc TEXT,
            subject TEXT NOT NULL,
            email_status TEXT NOT NULL,
            error TEXT
        )
    """)
    conn.commit()
    return conn

def events_today():
    day = now().date().isoformat()
    with db() as conn:
        return conn.execute("""
            SELECT id, created_at, staff_name, event_type, initial_boxes,
                   added_boxes, total_boxes, email_status
            FROM events
            WHERE business_date = ?
            ORDER BY id ASC
        """, (day,)).fetchall()

def current_total():
    rows = events_today()
    if not rows:
        return 0
    # latest collection-changing event; escalation does not alter total
    for row in reversed(rows):
        if row[3] in ("INITIAL", "ADDITIONAL"):
            return int(row[6])
    return 0

def initial_exists():
    return any(r[3] == "INITIAL" for r in events_today())

def send_email(subject, body, cc=None):
    if "CHANGE_ME" in DEPOT_EMAIL or not SMTP_HOST or not FROM_EMAIL:
        raise RuntimeError("Email settings have not been configured yet.")

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = DEPOT_EMAIL
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg.set_content(body)

    recipients = [DEPOT_EMAIL] + ([cc] if cc else [])
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.starttls(context=context)
        if SMTP_USERNAME:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg, to_addrs=recipients)

def log_event(staff, event_type, initial, added, total, subject, status, cc=None, error=None):
    t = now()
    with db() as conn:
        conn.execute("""
            INSERT INTO events
            (created_at, business_date, staff_name, event_type, initial_boxes,
             added_boxes, total_boxes, recipient, cc, subject, email_status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t.isoformat(timespec="seconds"), t.date().isoformat(), staff, event_type,
            initial, added, total, DEPOT_EMAIL, cc, subject, status, error
        ))
        conn.commit()

def dispatch(staff, event_type, initial, added, total, subject, body, cc=None):
    try:
        send_email(subject, body, cc)
        log_event(staff, event_type, initial, added, total, subject, "SENT", cc)
        return True, None
    except Exception as exc:
        # Failed attempts are also retained in the audit log.
        log_event(staff, event_type, initial, added, total, subject, "FAILED", cc, str(exc))
        return False, str(exc)

def subject_for(kind):
    if kind == "initial":
        return f"{ACCOUNT_REF} — Collection from Manor West Shopping Centre today — V92 KAN8"
    if kind == "additional":
        return f"{ACCOUNT_REF} — Update to today's collection — V92 KAN8"
    return f"{ACCOUNT_REF} — Collection still outstanding after 3pm — V92 KAN8"

st.title("📦 Balloons le Grá")
st.subheader("DPD Collection Portal")

staff = st.selectbox("Who is submitting this?", ["Select your name…"] + STAFF)

if staff == "Select your name…":
    st.info("Select your name above to continue.")
    st.stop()

today_total = current_total()
if initial_exists():
    st.caption(f"Today's current collection total: **{today_total} boxes**")

tab1, tab2, tab3, tab4 = st.tabs(
    ["New day", "Additional boxes", "3PM not collected", "Admin log"]
)

with tab1:
    st.header("New day — request collection")
    if initial_exists():
        st.warning(
            "Today's initial collection request has already been submitted. "
            "Use “Additional boxes” if the quantity has changed."
        )
    else:
        boxes = st.number_input("How many DPD boxes are going out today?", min_value=1, step=1)
        if st.button("Request collection", key="initial"):
            boxes = int(boxes)
            subject = subject_for("initial")
            body = f"""Hi there,

We have {boxes} box{"es" if boxes != 1 else ""} for collection today from:

{COLLECTION_ADDRESS}

Any questions, please let us know.

Thanks a million,
Balloons le Grá
"""
            ok, err = dispatch(staff, "INITIAL", boxes, 0, boxes, subject, body)
            if ok:
                st.success(f"Collection requested — {boxes} boxes. Submitted by {staff} at {now():%H:%M}.")
                st.rerun()
            else:
                st.error(f"The request was recorded, but the email was not sent: {err}")

with tab2:
    st.header("Additional boxes")
    if not initial_exists():
        st.warning("There is no initial collection request recorded for today yet.")
    else:
        existing = current_total()
        st.metric("Currently booked", f"{existing} boxes")
        extra = st.number_input("How many extra boxes have you got now?", min_value=1, step=1, key="extra")
        new_total = existing + int(extra)
        st.metric("New total", f"{new_total} boxes")
        if st.button("Send collection update", key="additional"):
            extra = int(extra)
            new_total = existing + extra
            subject = subject_for("additional")
            body = f"""Hi there,

Just an update on today's collection from Balloons le Grá.

We previously had {existing} box{"es" if existing != 1 else ""} booked for collection. We now have an additional {extra} box{"es" if extra != 1 else ""}, bringing today's total to {new_total} boxes.

Collection is from:
{COLLECTION_ADDRESS}

Any questions, please let us know.

Thanks a million,
Balloons le Grá
"""
            ok, err = dispatch(staff, "ADDITIONAL", existing, extra, new_total, subject, body)
            if ok:
                st.success(f"Update sent — {extra} additional; {new_total} boxes in total.")
                st.rerun()
            else:
                st.error(f"The update was recorded, but the email was not sent: {err}")

with tab3:
    st.header("3PM — collection still outstanding")
    if not initial_exists():
        st.warning("There is no collection request recorded for today.")
    elif now().hour < 15:
        st.info(f"This option becomes available at 3:00pm. Current time: {now():%H:%M}.")
    else:
        total = current_total()
        st.warning(f"Use this only if DPD has not collected today's {total} boxes.")
        if st.button("Email DPD — collection still outstanding", key="escalate"):
            subject = subject_for("escalation")
            body = f"""Hi there,

Just checking in regarding today's collection from Balloons le Grá.

As it is now after 3:00pm, under our shop protocol we contact the depot when our collection is still outstanding to confirm that the collection is scheduled and that a driver is still on the way.

We currently have {total} box{"es" if total != 1 else ""} awaiting collection from:
{COLLECTION_ADDRESS}

These contain inflated, personalised balloons for occasions taking place across the country tomorrow, so they need to enter the DPD network today.

If there is any issue with today's collection, could you please let us know as soon as possible so that we can make alternative arrangements.

Thanks a million,
Balloons le Grá
"""
            cc = KEVIN_EMAIL if "CHANGE_ME" not in KEVIN_EMAIL else None
            ok, err = dispatch(staff, "3PM_ESCALATION", total, 0, total, subject, body, cc)
            if ok:
                st.success(f"3PM escalation sent. {staff} — {now():%H:%M}.")
            else:
                st.error(f"The escalation was recorded, but the email was not sent: {err}")

with tab4:
    st.header("Admin — audit log")
    password = st.text_input("Admin password", type="password")
    if password:
        if password != ADMIN_PASSWORD:
            st.error("Incorrect password.")
        else:
            with db() as conn:
                rows = conn.execute("""
                    SELECT id, created_at, business_date, staff_name, event_type,
                           initial_boxes, added_boxes, total_boxes, recipient,
                           cc, subject, email_status, error
                    FROM events ORDER BY id DESC
                """).fetchall()
            columns = [
                "ID", "Timestamp", "Date", "Staff", "Event", "Previous/Initial",
                "Added", "Total", "Recipient", "CC", "Subject", "Email status", "Error"
            ]
            if rows:
                import pandas as pd
                frame = pd.DataFrame(rows, columns=columns)
                st.dataframe(frame, use_container_width=True, hide_index=True)
                st.caption("The staff interface contains no edit or delete controls. Every send attempt is appended to this log.")
            else:
                st.info("No collection events have been recorded yet.")

st.divider()
st.caption("Balloons le Grá • Internal collection system")
