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
            source_text = ", ".join(unique_citations[:10])
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
    --bg: #000000;
    --panel: #111111;
    --input: #111111;
    --border: #ffffff;
    --text: #ffffff;
    --muted: #cfcfcf;
    """

    css_template = """
<style>
:root {
  __VARS_BLOCK__
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
  background: var(--bg) !important;
  color: var(--text) !important;
}

[data-testid="stHeader"] {
  background: transparent !important;
}

section.main > div {
  background: var(--bg) !important;
}

h1, h2, h3, h4, h5, h6, p, label, span, div {
  color: var(--text);
}

[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--border) !important;
  background: var(--panel) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  background: var(--panel) !important;
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
  background: #ffffff !important;
  border: 1px solid #000000 !important;
  border-radius: 8px !important;
  color: #000000 !important;
}

[data-testid^="stChatMessageAvatar"] {
  background: #ffffff !important;
  border: 1px solid #000000 !important;
  border-radius: 8px !important;
  color: #000000 !important;
  font-weight: 700 !important;
}

[data-testid="stChatMessageAvatarUser"] *,
[data-testid="stChatMessageAvatarAssistant"] * {
  color: #000000 !important;
  fill: #000000 !important;
  stroke: #000000 !important;
}

[data-testid^="stChatMessageAvatar"] * {
  color: #000000 !important;
  fill: #000000 !important;
  stroke: #000000 !important;
}

[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
  background: var(--input) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  -webkit-text-fill-color: var(--text) !important;
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
  border: 1px solid var(--border) !important;
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
  border: 1px solid var(--border) !important;
  box-shadow: 0 0 0 1px var(--border) !important;
}

[data-baseweb="textarea"] {
  border: 1px solid var(--border) !important;
}

[data-testid="stFileUploaderDropzone"] {
  background: var(--input) !important;
  border: 1px solid var(--border) !important;
}

[data-testid="stFileUploaderDropzone"] * {
  color: var(--text) !important;
  fill: var(--text) !important;
}

[data-testid="stFileUploaderFileData"] * {
  color: var(--text) !important;
}

.chat-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 12px;
}

.chat-avatar {
  width: 34px;
  min-width: 34px;
  height: 34px;
  border-radius: 999px;
  border: 2px solid #000000;
  background: #ffffff;
  color: #000000;
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
  stroke: #000000;
  fill: none;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chat-bubble {
  flex: 1;
  background: #ffffff;
  border: 1px solid #000000;
  border-radius: 12px;
  color: #000000 !important;
  padding: 10px 12px;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.chat-bubble * {
  color: #000000 !important;
}

.chat-text {
  color: #000000 !important;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

[data-testid="stMarkdownContainer"] .chat-bubble,
[data-testid="stMarkdownContainer"] .chat-bubble *,
[data-testid="stMarkdownContainer"] .chat-bubble .chat-text {
  color: #000000 !important;
  -webkit-text-fill-color: #000000 !important;
}

.vertical-divider {
  border-left: 2px solid var(--border);
  min-height: 1400px;
  margin: 0 auto;
}

.stButton > button {
  background: #ffffff !important;
  color: #000000 !important;
  border: 1px solid #000000 !important;
  border-radius: 8px !important;
  opacity: 1 !important;
}

.stButton > button span,
.stButton > button p,
.stButton > button div {
  color: #000000 !important;
  -webkit-text-fill-color: #000000 !important;
}

.stButton > button:hover {
  background: #e8e8e8 !important;
}

div[data-testid="stFormSubmitButton"] > button {
  background: #ffffff !important;
  color: #000000 !important;
  border: 1px solid #000000 !important;
  border-radius: 8px !important;
  min-height: 42px !important;
  margin-top: 0 !important;
  opacity: 1 !important;
}

div[data-testid="stFormSubmitButton"] > button span,
div[data-testid="stFormSubmitButton"] > button p,
div[data-testid="stFormSubmitButton"] > button div {
  color: #000000 !important;
  -webkit-text-fill-color: #000000 !important;
}

div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
  align-items: flex-end !important;
}

.stButton > button:disabled {
  background: #f0f0f0 !important;
  color: #4a4a4a !important;
  border: 1px solid #b5b5b5 !important;
  opacity: 1 !important;
}

.stButton > button:disabled span,
.stButton > button:disabled p,
.stButton > button:disabled div {
  color: #4a4a4a !important;
  -webkit-text-fill-color: #4a4a4a !important;
}

.panel-title {
  font-weight: 800 !important;
  font-size: 1.9rem !important;
  margin-bottom: 8px;
  line-height: 1.2;
}

.subsection-title {
  font-weight: 800 !important;
  font-size: 1.9rem !important;
  margin: 14px 0 10px 0;
}

.muted-text {
  color: var(--muted) !important;
  font-style: italic;
}

a {
  color: var(--text) !important;
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
        safe_content = escape(content.rstrip())
        st.markdown(
            f"""
<div class="chat-row">
  <div class="chat-avatar">{avatar_svg}</div>
  <div class="chat-bubble"><p class="chat-text">{safe_content}</p></div>
</div>
""",
            unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(page_title="Smart Contract Assistant", layout="wide")
    init_state()

    st.title("Smart Contract Assistant")
    st.caption("Chat on the left. Upload, summarize, and evaluate on the right.")

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
