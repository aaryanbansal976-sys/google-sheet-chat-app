from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from support_insights.access import JobGuard, password_matches, run_authorized
from support_insights.config import Settings
from support_insights.llm import LLMExtractor
from support_insights.models import AppError, SheetRecord, effective_status
from support_insights.pipeline import Pipeline
from support_insights.sheets import SheetsRepository

DISPLAY_COLUMNS = ["Message ID", "Category", "Priority", "Sentiment", "Status"]
FRAME_COLUMNS = DISPLAY_COLUMNS + ["Message", "Suggested action"]


@st.cache_data(ttl=60, show_spinner=False)
def load_records(sheet_id: str, worksheet: str, _account: dict):
    repository = SheetsRepository.connect(
        Settings(
            sheet_id=sheet_id,
            worksheet=worksheet,
            service_account=_account,
        )
    )
    return repository.read_records(), datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


@st.cache_resource
def processing_guard() -> JobGuard:
    return JobGuard()


def make_pipeline(settings: Settings) -> Pipeline:
    return Pipeline(SheetsRepository.connect(settings), LLMExtractor(settings), settings.model)


def build_frame(records: list[SheetRecord], model: str) -> pd.DataFrame:
    rows = []
    for record in records:
        status = effective_status(record, model)
        insight = record.insight() if status == "processed" else None
        rows.append(
            {
                "Message ID": record.message_id,
                "Message": record.raw_message,
                "Category": insight.category if insight else "",
                "Priority": insight.priority if insight else "",
                "Sentiment": insight.sentiment if insight else "",
                "Suggested action": insight.suggested_action if insight else "",
                "Status": status,
            }
        )
    return pd.DataFrame(rows, columns=FRAME_COLUMNS)


def check_password(expected: str):
    supplied = st.session_state.pop("operator_password", "")
    st.session_state.authenticated = password_matches(supplied, expected)
    st.session_state.login_failed = not st.session_state.authenticated


def show_access(settings: Settings):
    st.sidebar.subheader("Operator")
    if st.session_state.get("authenticated", False):
        if st.sidebar.button("Lock processing", icon=":material/lock:"):
            st.session_state.authenticated = False
            st.session_state.login_failed = False
            st.rerun()
    else:
        with st.sidebar.form("operator_login"):
            st.text_input("Processing password", type="password", key="operator_password")
            st.form_submit_button(
                "Unlock processing", on_click=check_password, args=(settings.password,)
            )
        if st.session_state.get("login_failed", False):
            st.sidebar.error("Processing access denied.")


def show_summary():
    summary = st.session_state.get("last_run")
    if summary is None:
        return
    if summary.processed:
        st.success(f"Saved {summary.processed} processed messages.")
    if summary.errors or summary.invalid:
        st.warning(f"Saved {summary.errors} errors and {summary.invalid} invalid messages.")
    if summary.conflicts:
        st.warning("Changed rows left untouched: " + ", ".join(summary.conflicts))
    if summary.unpersisted:
        st.error("Save not confirmed: " + ", ".join(summary.unpersisted))
    if summary.abort_code:
        st.error("Processing stopped: " + summary.abort_code)
    if not (
        summary.processed
        or summary.errors
        or summary.invalid
        or summary.abort_code
        or summary.conflicts
    ):
        st.info("No eligible messages.")


def show_processing(settings: Settings, records: list[SheetRecord]):
    if not st.session_state.get("authenticated", False):
        return
    st.sidebar.divider()
    labels = {"Pending": "pending", "Retry errors": "retry_errors", "Selected": "selected"}
    choice = st.sidebar.radio("Processing scope", list(labels))
    selected = []
    if choice == "Selected":
        selected = st.sidebar.multiselect(
            "Message IDs", [record.message_id for record in records], max_selections=5
        )
    limit = st.sidebar.number_input("Batch size", min_value=1, max_value=5, value=5)
    if not settings.processing_ready():
        if settings.llm_configuration_error:
            st.sidebar.warning("LLM configuration unavailable: " + settings.llm_configuration_error)
        else:
            st.sidebar.warning("Processing is disabled or not configured.")
    pressed = st.sidebar.button(
        "Process",
        icon=":material/play_arrow:",
        type="primary",
        disabled=not settings.processing_ready() or (choice == "Selected" and not selected),
    )
    if pressed:
        progress = st.progress(0, text="Reading messages")
        try:
            summary = run_authorized(
                settings,
                st.session_state.get("authenticated", False),
                processing_guard(),
                lambda: make_pipeline(settings),
                mode=labels[choice],
                selected_ids=selected,
                limit=limit,
                on_progress=lambda done, total: progress.progress(
                    done / total, text=f"Analyzed {done} of {total}"
                ),
            )
            st.session_state.last_run = summary
            load_records.clear()
            st.rerun()
        except AppError as error:
            st.error("Processing unavailable: " + error.code)
        finally:
            progress.empty()


def render(settings: Settings):
    st.set_page_config(
        page_title="Support Insights", page_icon=":material/support_agent:", layout="wide"
    )
    st.title("Support Insights")
    st.caption("Synthetic customer support messages")
    show_access(settings)
    if not settings.read_ready():
        st.warning("Google Sheet connection is not configured.")
        return
    if st.sidebar.button("Refresh", icon=":material/refresh:"):
        if st.session_state.get("authenticated", False):
            load_records.clear()
    try:
        records, loaded_at = load_records(
            settings.sheet_id, settings.worksheet, settings.service_account
        )
        frame = build_frame(records, settings.model)
    except AppError as error:
        st.error("Google Sheet unavailable: " + error.code)
        return
    st.caption("Last read: " + loaded_at)
    show_summary()
    show_processing(settings, records)
    search = st.text_input("Search messages", placeholder="Message text or ID")
    if search:
        frame = frame[
            frame["Message"].str.contains(search, case=False, regex=False)
            | frame["Message ID"].str.contains(search, case=False, regex=False)
        ]
    columns = st.columns(4)
    for column, field in zip(columns, ["Category", "Priority", "Sentiment", "Status"], strict=True):
        options = sorted(value for value in frame[field].unique() if value)
        selected = column.multiselect(field, options, key="filter_" + field)
        if selected:
            frame = frame[frame[field].isin(selected)]
    counts = frame["Status"].value_counts()
    metrics = st.columns(4)
    metrics[0].metric("Messages", len(frame))
    metrics[1].metric("Processed", int(counts.get("processed", 0)))
    metrics[2].metric("Pending", int(counts.get("pending", 0)))
    metrics[3].metric("Needs review", int(counts.get("error", 0) + counts.get("invalid", 0)))
    insights = frame[frame["Status"] == "processed"]
    if not insights.empty:
        chart_columns = st.columns(2)
        with chart_columns[0]:
            st.subheader("Categories")
            st.bar_chart(insights["Category"].value_counts(), color="#178578", horizontal=True)
        with chart_columns[1]:
            st.subheader("Priorities")
            priorities = (
                insights["Priority"]
                .value_counts()
                .reindex(["Low", "Medium", "High", "Critical"], fill_value=0)
            )
            st.bar_chart(priorities, color="#c18a19", horizontal=True)
    st.subheader("Messages")
    if frame.empty:
        st.info("No messages match the current view." if records else "No messages in the sheet.")
        return
    st.dataframe(frame[DISPLAY_COLUMNS], hide_index=True, width="stretch")
    identifier = st.selectbox("Inspect message", frame["Message ID"].tolist())
    detail = frame[frame["Message ID"] == identifier].iloc[0]
    st.text_area("Original message", detail["Message"], height=150, disabled=True)
    st.text_area("Suggested action", detail["Suggested action"], height=90, disabled=True)
    record = next(record for record in records if record.message_id == identifier)
    if detail["Status"] in {"error", "invalid"}:
        st.warning("Record issue: " + record.outputs[7])
