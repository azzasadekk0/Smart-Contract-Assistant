import os
import uuid
from html import escape
from typing import Any

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def upload_documents(uploaded_files: list[Any] | None) -> str:
    if not uploaded_files:
        return "Select one or more PDF/DOCX files."

    files = []
    try:
        for uploaded in uploaded_files:
            files.append(("files", (uploaded.name, uploaded.getvalue(), "application/octet-stream")))

        response = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=240)
        response.raise_for_status()
        payload = response.json()
        return (
            f"{payload['message']}\n"
            f"Indexed files: {', '.join(payload['indexed_files'])}"
        )
    except Exception as exc:
        return f"Upload failed: {exc}"


def chat_with_assistant(message: str, chat_history: list[dict[str, str]], session_id: str):
    if not message.strip():
        return "", chat_history, chat_history, session_id

    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={"session_id": session_id, "question": message},
            timeout=240,
        )
        response.raise_for_status()
        payload = response.json()

        answer_text = payload["answer"]
        if payload.get("citations"):
            unique_citations: list[str] = []
            seen = set()
            for item in payload["citations"]:
                citation = f"{item['source']}#chunk{item.get('chunk_id', '?')}"
                if citation in seen:
                    continue
                seen.add(citation)
                unique_citations.append(citation)
            source_text = ", ".join(unique_citations[:3])
            answer_text += f"\n\nSources: {source_text}"

        updated = chat_history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer_text},
        ]
        return "", updated, updated, session_id
    except Exception as exc:
        updated = chat_history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": f"Chat request failed: {exc}"},
        ]
        return "", updated, updated, session_id


def summarize_source(source: str) -> str:
    try:
        payload = {"source": source.strip() or None}
        response = requests.post(f"{BACKEND_URL}/summarize", json=payload, timeout=240)
        response.raise_for_status()
        data = response.json()
        return f"Summary ({data['source']}):\n\n{data['summary']}"
    except Exception as exc:
        return f"Summarization failed: {exc}"


def run_evaluation(cases_path: str) -> str:
    try:
        payload = {"cases_path": cases_path.strip() or "data/eval_cases.json"}
        response = requests.post(f"{BACKEND_URL}/evaluate", json=payload, timeout=240)
        response.raise_for_status()
        data = response.json()
        metrics = data.get("metrics", {})
        lines = [
            f"Cases file: {data.get('cases_path')}",
            f"Cases count: {data.get('cases_count', 0)}",
            "",
            "Metrics:",
        ]
        for key, value in metrics.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Evaluation failed: {exc}"


def clear_chat() -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    return [], [], str(uuid.uuid4())


def parse_summary_output(summary_output: str) -> tuple[str, str]:
    text = summary_output.strip()
    if not text:
        return "", ""

    lines = text.splitlines()
    if lines and lines[0].startswith("Summary (") and lines[0].endswith("):"):
        source = lines[0][len("Summary (") : -2].strip()
        body = "\n".join(lines[1:]).strip()
        return source, body

    return "", text


def parse_evaluation_output(eval_output: str) -> tuple[str, str, list[tuple[str, str]], str]:
    text = eval_output.strip()
    if not text:
        return "", "", [], ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", "", [], ""

    if lines[0].startswith("Evaluation failed:"):
        return "", "", [], text

    cases_file = ""
    cases_count = ""
    metrics: list[tuple[str, str]] = []
    for line in lines:
        if line.startswith("Cases file:"):
            cases_file = line.split(":", 1)[1].strip()
        elif line.startswith("Cases count:"):
            cases_count = line.split(":", 1)[1].strip()
        elif line.startswith("- ") and ":" in line:
            key_value = line[2:].split(":", 1)
            metrics.append((key_value[0].strip(), key_value[1].strip()))

    return cases_file, cases_count, metrics, text


def build_css() -> str:
    vars_block = """
    --bg: #f3f8f4;
    --panel: #8EB69B;
    --panel-soft: #8EB69B;
    --input: #e9f3ec;
    --border: #235347;
    --text: #051F20;
    --muted: #235347;
    --accent: #235347;
    --accent-strong: #2F6B5D;
    --accent-soft: #b7d0bf;
    --assistant-bubble: #e9f3ec;
    --user-bubble: #e9f3ec;
    --shadow-sm: 0 8px 20px rgba(2, 8, 23, 0.05);
    --shadow-md: 0 14px 35px rgba(2, 8, 23, 0.08);
    --radius-lg: 12px;
    --radius-md: 12px;
    """

    css_template = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@700;800&display=swap');

:root {
  __VARS_BLOCK__
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

[data-testid="stHeader"] {
  background: transparent !important;
}

section.main > div {
  background: var(--bg) !important;
  padding-top: 1.15rem !important;
}

h1, h2, h3, h4, h5, h6, p, label, span, div {
  color: var(--text);
}

h1, h2, h3, h4 {
  font-family: "Manrope", "Inter", sans-serif !important;
  letter-spacing: -0.015em;
}

h1 {
  font-size: clamp(2rem, 4vw, 2.8rem) !important;
  font-weight: 800 !important;
  margin-bottom: 0.4rem !important;
}

[data-testid="stCaptionContainer"] p {
  color: var(--muted) !important;
  font-size: 0.98rem !important;
  font-weight: 500 !important;
}

[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--border) !important;
  background: var(--panel) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-lg) !important;
  background: var(--panel) !important;
  box-shadow: var(--shadow-sm) !important;
  padding: 2px !important;
}

[data-testid="stChatMessage"] {
  background: transparent !important;
}

[data-testid="stChatMessageContent"] {
  background: var(--panel) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
}

[data-testid="stChatMessageContent"] * {
  color: var(--text) !important;
}

[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
  background: var(--accent-soft) !important;
  border: 1px solid var(--border) !important;
  border-radius: 999px !important;
  color: var(--accent-strong) !important;
}

[data-testid^="stChatMessageAvatar"] {
  background: var(--accent-soft) !important;
  border: 1px solid var(--border) !important;
  border-radius: 999px !important;
  color: var(--accent-strong) !important;
  font-weight: 700 !important;
}

[data-testid="stChatMessageAvatarUser"] *,
[data-testid="stChatMessageAvatarAssistant"] * {
  color: var(--accent-strong) !important;
  fill: var(--accent-strong) !important;
  stroke: var(--accent-strong) !important;
}

[data-testid^="stChatMessageAvatar"] * {
  color: var(--accent-strong) !important;
  fill: var(--accent-strong) !important;
  stroke: var(--accent-strong) !important;
}

[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
  background: var(--input) !important;
  color: var(--text) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  -webkit-text-fill-color: var(--text) !important;
  padding: 0.72rem 0.88rem !important;
  min-height: 46px !important;
}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
  color: var(--muted) !important;
  opacity: 1 !important;
}

[data-testid="stTextArea"] textarea:disabled {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  opacity: 1 !important;
}

textarea[disabled],
input[disabled] {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  opacity: 1 !important;
}

[data-testid="stTextArea"] [data-baseweb="textarea"],
[data-testid="stTextArea"] [data-baseweb="textarea"] * {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
  background: var(--input) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  box-shadow: none !important;
}

div[data-baseweb="input"] *,
div[data-baseweb="select"] * {
  color: var(--text) !important;
  fill: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
}

div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within {
  border: 1.5px solid var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(248, 187, 208, 0.35) !important;
}

[data-baseweb="textarea"] {
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
}

[data-testid="stFileUploaderDropzone"] {
  background: var(--input) !important;
  border: 1.5px dashed var(--border) !important;
  border-radius: var(--radius-lg) !important;
  padding: 0.45rem !important;
}

[data-testid="stFileUploaderDropzone"] > div {
  background: var(--input) !important;
}

[data-testid="stFileUploaderDropzone"] * {
  color: var(--text) !important;
  fill: var(--text) !important;
}

[data-testid="stFileUploaderDropzone"] svg {
  display: none !important;
}

[data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"] > div:first-child {
  display: none !important;
}

[data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"] {
  padding-left: 0 !important;
}

[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploaderDropzone"] [data-baseweb="button"] {
  background: var(--accent) !important;
  border: 1px solid var(--accent) !important;
  color: #f4fffa !important;
  border-radius: 12px !important;
  font-weight: 600 !important;
  box-shadow: 0 6px 16px rgba(229, 115, 115, 0.18) !important;
}

[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploaderDropzone"] [data-baseweb="button"]:hover {
  background: var(--accent-strong) !important;
  border-color: var(--accent-strong) !important;
}

[data-testid="stFileUploaderDropzone"] button *,
[data-testid="stFileUploaderDropzone"] [data-baseweb="button"] * {
  color: #f4fffa !important;
  -webkit-text-fill-color: #f4fffa !important;
  fill: #f4fffa !important;
}

[data-testid="stFileUploaderFileData"] * {
  color: var(--text) !important;
}

input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
textarea:-webkit-autofill {
  -webkit-text-fill-color: var(--text) !important;
  box-shadow: 0 0 0px 1000px var(--input) inset !important;
}

.chat-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
}

.chat-row.user-row {
  flex-direction: row-reverse;
  justify-content: flex-start;
}

.chat-row.assistant-row {
  justify-content: flex-start;
}

.chat-avatar {
  width: 36px;
  min-width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--accent-soft);
  color: var(--accent-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
}

.chat-avatar svg {
  width: 18px;
  height: 18px;
  stroke: var(--accent-strong);
  fill: none;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chat-bubble {
  max-width: 84%;
  border: 1px solid var(--border);
  border-radius: 16px;
  color: var(--text) !important;
  padding: 12px 16px;
  box-shadow: var(--shadow-sm);
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  transition: transform 0.18s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.chat-row.user-row .chat-bubble {
  background: var(--user-bubble);
}

.chat-row.assistant-row .chat-bubble {
  background: var(--assistant-bubble);
}

.chat-bubble:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.chat-bubble * {
  color: var(--text) !important;
}

.chat-text {
  color: var(--text) !important;
  font-size: 0.98rem;
  line-height: 1.58;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

[data-testid="stMarkdownContainer"] .chat-bubble,
[data-testid="stMarkdownContainer"] .chat-bubble *,
[data-testid="stMarkdownContainer"] .chat-bubble .chat-text {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
}

.chat-sources {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.source-tag {
  display: inline-flex;
  align-items: center;
  background: #dbe9df;
  color: #235347 !important;
  border: 1px solid #8EB69B;
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 0.74rem;
  line-height: 1.1;
  font-weight: 500;
}

.vertical-divider {
  border-left: 2px solid var(--border);
  height: clamp(1320px, 175vh, 1850px);
  margin: 6px auto 0 auto;
  opacity: 0.8;
}

.stButton > button {
  background: var(--accent) !important;
  color: #f4fffa !important;
  border: 1px solid var(--accent) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  padding: 0.62rem 1rem !important;
  box-shadow: 0 8px 20px rgba(229, 115, 115, 0.16) !important;
  transition: background 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease !important;
  opacity: 1 !important;
}

.stButton > button span,
.stButton > button p,
.stButton > button div {
  color: #f4fffa !important;
  -webkit-text-fill-color: #f4fffa !important;
}

.stButton > button:hover {
  background: var(--accent-strong) !important;
  border-color: var(--accent-strong) !important;
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(229, 115, 115, 0.24) !important;
}

div[data-testid="stFormSubmitButton"] > button {
  background: var(--accent) !important;
  color: #f4fffa !important;
  border: 1px solid var(--accent) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  min-height: 42px !important;
  margin-top: 0 !important;
  padding: 0.62rem 1rem !important;
  box-shadow: 0 8px 20px rgba(229, 115, 115, 0.16) !important;
  transition: background 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease !important;
  opacity: 1 !important;
}

div[data-testid="stFormSubmitButton"] > button span,
div[data-testid="stFormSubmitButton"] > button p,
div[data-testid="stFormSubmitButton"] > button div {
  color: #f4fffa !important;
  -webkit-text-fill-color: #f4fffa !important;
}

div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
  align-items: flex-end !important;
}

.stButton > button:disabled {
  background: #7fa795 !important;
  color: #e8f1ec !important;
  border: 1px solid #6f9988 !important;
  box-shadow: none !important;
  opacity: 1 !important;
}

.stButton > button:disabled span,
.stButton > button:disabled p,
.stButton > button:disabled div {
  color: #e8f1ec !important;
  -webkit-text-fill-color: #e8f1ec !important;
}

.panel-title {
  font-weight: 800 !important;
  font-size: clamp(1.3rem, 2.1vw, 1.8rem) !important;
  margin-bottom: 10px;
  line-height: 1.2;
  color: var(--text) !important;
  letter-spacing: -0.01em;
}

.subsection-title {
  font-weight: 800 !important;
  font-size: clamp(1.2rem, 2vw, 1.65rem) !important;
  margin: 16px 0 10px 0;
  line-height: 1.25;
  color: var(--text) !important;
}

.muted-text {
  color: var(--muted) !important;
  font-style: italic;
  font-size: 0.96rem !important;
}

[data-testid="stAlert"] {
  border: 1px solid var(--border) !important;
  background: #dce9e0 !important;
  color: var(--text) !important;
}

[data-testid="stAlert"] * {
  color: var(--text) !important;
}

[data-testid="stMarkdownContainer"] code {
  background: var(--assistant-bubble) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  padding: 3px 8px !important;
  font-size: 0.82rem !important;
  -webkit-text-fill-color: var(--text) !important;
}

[data-testid="stMarkdownContainer"] pre {
  background: var(--assistant-bubble) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  padding: 10px 12px !important;
}

[data-testid="stMarkdownContainer"] pre code {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  border-radius: 0 !important;
}

a {
  color: var(--accent) !important;
  text-underline-offset: 2px;
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-track {
  background: #dce9e0;
  border-radius: 999px;
}

::-webkit-scrollbar-thumb {
  background: #8EB69B;
  border-radius: 999px;
}

::-webkit-scrollbar-thumb:hover {
  background: #7fa795;
}
</style>
"""
    return css_template.replace("__VARS_BLOCK__", vars_block.strip())


def init_state() -> None:
    st.session_state.setdefault("chat_state", [])
    st.session_state.setdefault("session_state", str(uuid.uuid4()))
    st.session_state.setdefault("upload_status", "")
    st.session_state.setdefault("summary_output", "")
    st.session_state.setdefault("eval_output", "")
    st.session_state.setdefault("source_name", "")
    st.session_state.setdefault("eval_cases_path", "data/eval_cases.json")


def render_chat_history(chat_history: list[dict[str, str]]) -> None:
    if not chat_history:
        st.markdown("<div class='muted-text'>No messages yet.</div>", unsafe_allow_html=True)
        return

    for msg in chat_history:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        message_body = content
        source_tags_html = ""
        if "\n\nSources:" in content:
            message_body, raw_sources = content.split("\n\nSources:", maxsplit=1)
            sources = [item.strip() for item in raw_sources.split(",") if item.strip()]
            if sources:
                badges = "".join(f'<span class="source-tag">{escape(source)}</span>' for source in sources)
                source_tags_html = f'<div class="chat-sources">{badges}</div>'

        avatar_svg = (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<circle cx="12" cy="8" r="4"></circle>'
            '<path d="M5 20c1.6-3.3 4.1-5 7-5s5.4 1.7 7 5"></path>'
            "</svg>"
            if role == "user"
            else '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<rect x="6" y="7" width="12" height="10" rx="2"></rect>'
            '<circle cx="10" cy="12" r="1"></circle>'
            '<circle cx="14" cy="12" r="1"></circle>'
            '<path d="M9 15h6"></path>'
            '<path d="M12 4v3"></path>'
            "</svg>"
        )
        safe_content = escape(message_body.rstrip())
        row_class = "user-row" if role == "user" else "assistant-row"
        st.markdown(
            f"""
<div class="chat-row {row_class}">
  <div class="chat-avatar">{avatar_svg}</div>
  <div class="chat-bubble">
    <p class="chat-text">{safe_content}</p>
    {source_tags_html}
  </div>
</div>
""",
            unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(page_title="Smart Contract Assistant", layout="wide")
    init_state()

    st.title("Smart Contract Assistant")

    st.markdown(build_css(), unsafe_allow_html=True)

    left_col, divider_col, right_col = st.columns([7, 0.08, 4], gap="small")

    with left_col:
        with st.container(border=True):
            st.markdown("<div class='panel-title'>Contract Chatbot</div>", unsafe_allow_html=True)
            with st.container(height=560, border=True):
                render_chat_history(st.session_state.chat_state)

            with st.form("chat_form", clear_on_submit=True):
                st.markdown("Ask a question")
                input_col, send_col = st.columns([8, 2], gap="small")
                with input_col:
                    message_input = st.text_input(
                        "Ask a question",
                        placeholder="Ask about obligations, payment terms, duration, termination...",
                        label_visibility="collapsed",
                    )
                with send_col:
                    send_clicked = st.form_submit_button("Send", use_container_width=True)

            clear_clicked = st.button("Clear Chat", use_container_width=True)

            if send_clicked and message_input.strip():
                with st.spinner("Generating response..."):
                    _, updated_chat, _, new_session_id = chat_with_assistant(
                        message_input,
                        st.session_state.chat_state,
                        st.session_state.session_state,
                    )
                    st.session_state.chat_state = updated_chat
                    st.session_state.session_state = new_session_id
                st.rerun()

            if clear_clicked:
                cleared_chat, _, new_session_id = clear_chat()
                st.session_state.chat_state = cleared_chat
                st.session_state.session_state = new_session_id
                st.rerun()

    with divider_col:
        st.markdown("<div class='vertical-divider'></div>", unsafe_allow_html=True)

    with right_col:
        with st.container(border=True):
            st.markdown("<div class='panel-title'>Document Workspace</div>", unsafe_allow_html=True)

            with st.container(border=True):
                uploaded_files = st.file_uploader(
                    "Upload Contract Files",
                    type=["pdf", "docx"],
                    accept_multiple_files=True,
                )
                if st.button("Index Documents", use_container_width=True):
                    with st.spinner("Indexing documents..."):
                        st.session_state.upload_status = upload_documents(uploaded_files)

            with st.container(border=True):
                st.text_area(
                    "Indexing Status",
                    value=st.session_state.upload_status,
                    height=140,
                    disabled=True,
                )

            st.markdown("<div class='subsection-title'>Summarization</div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.text_input(
                    "Source file name (optional)",
                    placeholder="e.g. GentechHoldingsInc.pdf (leave blank for all)",
                    key="source_name",
                )
                if st.button("Generate Summary", use_container_width=True):
                    with st.spinner("Generating summary..."):
                        st.session_state.summary_output = summarize_source(st.session_state.source_name)

            with st.container(border=True):
                st.markdown("Summary")
                source_name, summary_body = parse_summary_output(st.session_state.summary_output)
                with st.container(height=260, border=False):
                    if summary_body:
                        if source_name:
                            st.markdown(f"**Source:** `{source_name}`")
                        st.markdown(summary_body)
                    else:
                        st.markdown("<div class='muted-text'>No summary yet.</div>", unsafe_allow_html=True)

            st.markdown("<div class='subsection-title'>Evaluation</div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.text_input("Evaluation cases path", key="eval_cases_path")
                if st.button("Run Evaluation", use_container_width=True):
                    with st.spinner("Running evaluation..."):
                        st.session_state.eval_output = run_evaluation(st.session_state.eval_cases_path)

            with st.container(border=True):
                st.markdown("Evaluation Results")
                cases_file, cases_count, metrics, raw_eval = parse_evaluation_output(st.session_state.eval_output)
                with st.container(height=220, border=False):
                    if raw_eval:
                        if raw_eval.startswith("Evaluation failed:"):
                            st.markdown(raw_eval)
                        else:
                            if cases_file:
                                st.markdown(f"**Cases file:** `{cases_file}`")
                            if cases_count:
                                st.markdown(f"**Cases count:** `{cases_count}`")
                            if metrics:
                                st.markdown("**Metrics**")
                                for key, value in metrics:
                                    st.markdown(f"- **{key}**: `{value}`")
                            elif st.session_state.eval_output:
                                st.markdown(st.session_state.eval_output)
                    else:
                        st.markdown("<div class='muted-text'>No evaluation results yet.</div>", unsafe_allow_html=True)
if __name__ == "__main__":
    main()
