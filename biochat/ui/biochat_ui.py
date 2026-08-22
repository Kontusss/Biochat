"""
Biochat UI — ProtChat-inspired Gradio interface.

Delivers a polished, modern biomedical AI chat experience modeled on
the ProtChat reference design.  All core agent logic is delegated to
the Biochat A1 engine unchanged.

Layout
──────
┌──────────────────────────────────────────────────────────┐
│ 🧬 Biochat          v2.0   Biochat Engine   ● Safe Mode   │
├─────────────┬────────────────────────────────────────────┤
│ Sidebar     │  Welcome Card                              │
│             │  ┌──────────────────────────────────────┐  │
│ Tools &     │  │  Example prompt pills                │  │
│ Capabilities│  └──────────────────────────────────────┘  │
│             │  ┌──────────────────────────────────────┐  │
│ Status      │  │  Chatbot messages                    │  │
│ Badges      │  │                                      │  │
│             │  └──────────────────────────────────────┘  │
│ Attribution │  ┌──────────────────────────────────────┐  │
│             │  │  Input area  [Send] [Clear]          │  │
│             │  └──────────────────────────────────────┘  │
├─────────────┴────────────────────────────────────────────┤
│ ● Structure:verified · Tools:32 loaded · Apache 2.0      │
└──────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import re
import os
from time import time


# ═══════════════════════════════════════════════════════════════
# HTML SNIPPETS
# ═══════════════════════════════════════════════════════════════

def _header_html() -> str:
    """Header bar with the canonical project version."""
    from biochat.core.settings import PROJECT_VERSION

    return f"""
<div class="biochat-header">
    <span class="bc-logo">🧬 Biochat</span>
    <span class="bc-version">v{PROJECT_VERSION}</span>
    <span class="bc-engine-badge">Biochat Engine</span>
    <span class="bc-header-status">
        <span class="bc-dot"></span> Safe Mode
    </span>
</div>
"""

_SIDEBAR_HTML = """
<div class="biochat-sidebar">
    <div>
        <div class="bc-section-title">🧰 Tools &amp; Capabilities</div>
        <div class="bc-cap-list">
            <div class="bc-cap-item"><span class="bc-cap-dot"></span>Genomics &amp; GWAS</div>
            <div class="bc-cap-item"><span class="bc-cap-dot"></span>Biochemistry &amp; Proteins</div>
            <div class="bc-cap-item"><span class="bc-cap-dot"></span>Pharmacology &amp; ADMET</div>
            <div class="bc-cap-item"><span class="bc-cap-dot"></span>Cell Biology &amp; scRNA-seq</div>
            <div class="bc-cap-item"><span class="bc-cap-dot"></span>Microbiology &amp; Pathogens</div>
            <div class="bc-cap-item"><span class="bc-cap-dot"></span>Immunology &amp; Epitopes</div>
            <div class="bc-cap-item"><span class="bc-cap-dot"></span>Literature Mining</div>
            <div class="bc-cap-item"><span class="bc-cap-dot"></span>30+ Biomedical Databases</div>
        </div>
    </div>
    <div class="bc-divider"></div>
    <div>
        <div class="bc-section-title">📊 System Status</div>
        <div class="bc-status-list">
            <div class="biochat-status-badge bc-ok">
                <span class="bc-sb-dot"></span> Structure Tools — Verified
            </div>
            <div class="biochat-status-badge bc-ok">
                <span class="bc-sb-dot"></span> 32 Database Schemas — Loaded
            </div>
            <div class="biochat-status-badge bc-ok">
                <span class="bc-sb-dot"></span> Safety Filter — Enabled
            </div>
            <div class="biochat-status-badge bc-warn">
                <span class="bc-sb-dot"></span> Humanization — Not Installed
            </div>
            <div class="biochat-status-badge bc-off">
                <span class="bc-sb-dot"></span> Generation — Disabled
            </div>
        </div>
    </div>
    <div class="bc-sidebar-footer">
        <strong>Biochat</strong> UI built on the<br>
        Biochat scientific engine<br>
        <span style="opacity:0.7">Apache 2.0 License</span>
    </div>
</div>
"""

_WELCOME_HTML = """
<div class="biochat-welcome" id="bc-welcome">
    <div class="bc-welcome-icon">🧬</div>
    <h2>Welcome to Biochat</h2>
    <p class="bc-welcome-sub">Your Biomedical AI Research Copilot</p>
    <p class="bc-welcome-desc">
        Powered by the Biochat scientific engine with 200+ verified
        bioinformatics tools, 30+ curated databases, and an 11GB biomedical data lake.
        Ask any biomedical research question to get started.
    </p>
</div>
"""

_EXAMPLES_HTML = """
<div class="biochat-examples">
    <button class="biochat-sample-btn" data-query="Query the EGFR protein structure from PDB and identify key functional domains">🔬 Query EGFR structure</button>
    <button class="biochat-sample-btn" data-query="Explain the biological function of the BRCA1 protein and its role in DNA repair">🧬 Explain protein function</button>
    <button class="biochat-sample-btn" data-query="List all available Biochat tools for genomics analysis">🛠️ Check available tools</button>
    <button class="biochat-sample-btn" data-query="Plan an antibody humanization strategy for a murine anti-PD-L1 antibody">💊 Plan antibody humanization</button>
</div>
"""

_FOOTER_HTML = """
<div class="biochat-footer-bar">
    <span class="bc-footer-dot"></span>
    <span>Biochat Engine — Ready</span>
    <span class="bc-footer-sep"></span>
    <span class="bc-footer-badge good">Structure: Verified</span>
    <span class="bc-footer-badge good">32 Tools Loaded</span>
    <span class="bc-footer-badge off">Generation: Disabled</span>
    <span class="bc-footer-sep"></span>
    <span style="margin-left:auto;opacity:0.7">Biochat Engine · Apache 2.0</span>
</div>
"""

_ATTRIBUTION_HTML = """
<div class="biochat-attribution">
    <strong>Biochat</strong> — Built on the
    Biochat
    scientific engine. Licensed under
    <a href="https://www.apache.org/licenses/LICENSE-2.0" target="_blank">Apache 2.0</a>.
    Review <code>license_info.md</code> for third-party data terms.
</div>
"""


# ═══════════════════════════════════════════════════════════════
# UI CONSTRUCTION (builds Gradio Blocks, does NOT launch)
# ═══════════════════════════════════════════════════════════════

def create_biochat_ui(
    agent,
    thread_id: int = 42,
    require_verification: bool = False,
):
    """Build and return the Biochat Gradio Blocks object WITHOUT launching.

    This is the pure construction function — it returns a ``gr.Blocks``
    instance ready for ``.launch()``.  Tests can call this directly to
    verify the UI builds without starting a server.

    Args:
        agent: An initialized A1 agent instance.
        thread_id: Thread ID for conversation state.
        require_verification: Require access-code verification before use.

    Returns:
        gradio.Blocks: The constructed (but not launched) UI object.
    """
    try:
        import gradio as gr
        from gradio import ChatMessage
    except ImportError:
        raise ImportError("Gradio is not installed.  pip install 'gradio>=5.0,<6.0'")

    from .biochat_theme import BiochatTheme

    SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".pdf")
    agent.main_history_copy = []
    from biochat.core.settings import biochat_settings as _settings
    from biochat.ui.auth import verify_access_code as _verify_access_code
    available_access_codes = list(_settings.access_codes)

    # ── Helper: footer status bar ─────────────────────────────

    def _footer(status_msgs: list[str] | None = None) -> str:
        if not status_msgs:
            return _FOOTER_HTML
        latest = status_msgs[-3:]
        badges = []
        for m in latest:
            m = m[:64]
            if any(w in m for w in ("✅", "Complete", "Solution", "completed")):
                badges.append(f'<span class="bc-footer-badge good">{m}</span>')
            elif any(w in m for w in ("Executing", "Retrieving", "working")):
                badges.append(f'<span class="bc-footer-badge warn">{m}</span>')
            elif any(w in m for w in ("❌", "Error", "failed")):
                badges.append(f'<span style="font-size:11px;color:var(--bc-red)">{m}</span>')
            else:
                badges.append(f'<span style="font-size:11px;color:var(--bc-text-3)">{m}</span>')
        return f"""<div class="biochat-footer-bar">
            <span class="bc-footer-dot" style="animation:bc-pulse 2s ease-in-out infinite"></span>
            <span>Processing…</span>
            <span class="bc-footer-sep"></span>
            {''.join(badges)}
            <span style="margin-left:auto;opacity:0.7">Biochat Engine · Apache 2.0</span>
        </div>"""

    # ── Verification ──────────────────────────────────────────

    def verify_access_code(code):
        if _verify_access_code(code, available_access_codes):
            return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
        return gr.update(visible=True), gr.update(visible=False), gr.update(value="Incorrect access code.", visible=True)

    # ── Example-prompt click handler ──────────────────────────

    def fill_example(query: str):
        return query

    # ── Chat response generator ───────────────────────────────

    def generate_response(user_text, inner_history, main_history):
        if main_history is None:
            main_history = []
        if inner_history is None:
            inner_history = []

        agent.main_history_copy += [{"role": "user", "content": user_text}]
        main_history.append(ChatMessage(role="user", content=user_text))
        main_history.append(ChatMessage(role="assistant", content="🧬 *Analyzing your query with the Biochat engine…*"))
        yield inner_history, main_history, _FOOTER_HTML, ""

        from langchain_core.messages import HumanMessage, AIMessage

        agent_messages = []
        for msg in agent.main_history_copy:
            if msg["role"] == "user":
                agent_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                skip_markers = [
                    "Executor is working on it", "🧬 Executor is working",
                    "🧬 *Analyzing your query",
                ]
                if not any(m in msg["content"] for m in skip_markers):
                    agent_messages.append(AIMessage(content=msg["content"]))
        agent_messages.append(HumanMessage(content=user_text))

        inputs = {"messages": agent_messages, "next_step": None}
        config = {"recursion_limit": 500, "configurable": {"thread_id": thread_id}}

        t = time()
        solution_found = False
        code_msgs = []
        status_msgs = []

        # Optional tool retrieval
        if agent.use_tool_retriever:
            inner_history.append(ChatMessage(role="assistant", content="🔍 Retrieving relevant tools, data lake items, and libraries…", metadata={"title": "🛠️ Tool Retrieval"}))
            yield inner_history, main_history, _footer(["🔍 Retrieving tools…"]), ""
            try:
                selected = agent._prepare_resources_for_retrieval(user_text)
                if selected:
                    agent.update_system_prompt_with_selected_resources(selected)
                    status_msgs.append(f"✅ {len(selected)} tools selected")
            except Exception:
                inner_history.append(ChatMessage(role="assistant", content="⚠️ Tool retrieval unavailable — proceeding with all tools."))
                status_msgs.append("⚠️ Tool retrieval skipped")
                yield inner_history, main_history, _footer(status_msgs), ""

        for s in agent.app.stream(inputs, stream_mode="values", config=config):
            t_step = time() - t
            message = s["messages"][-1]
            if message.content == user_text:
                t = time()
                continue
            if not isinstance(message.content, str):
                t = time()
                continue

            content = message.content

            # Thinking before first tag
            tag_positions = []
            for tag_name in ("<execute>", "<solution>", "<observation>"):
                p = content.find(tag_name)
                if p != -1:
                    tag_positions.append(p)
            if tag_positions:
                thinking = content[:min(tag_positions)].strip()
                if thinking and len(thinking) > 20:
                    inner_history.append(ChatMessage(role="assistant", content=thinking, metadata={"title": "🤔 Reasoning"}))
                    yield inner_history, main_history, _footer(status_msgs), ""

            # Solution
            sm = re.search(r"<solution>(.*?)</solution>", content, re.DOTALL)
            if sm and not solution_found:
                solution = sm.group(1).strip()
                main_history.append(ChatMessage(role="assistant", content=solution, metadata={"title": "✅ Answer"}))
                agent.main_history_copy += [{"role": "assistant", "content": solution}]
                solution_found = True
                status_msgs.append("✅ Solution found")
                yield inner_history, main_history, _footer(status_msgs), ""

            # Execute
            em = re.search(r"<execute>(.*?)</execute>", content, re.DOTALL)
            if em:
                code = em.group(1).strip()
                language = "python"
                if code.strip().startswith("#!R"):
                    language = "r"; code = re.sub(r"^#!R", "", code, count=1).strip()
                elif code.strip().startswith("#!BASH") or code.strip().startswith("#!CLI"):
                    language = "bash"; code = re.sub(r"^#!BASH|^#!CLI", "", code, count=1).strip()
                cm = ChatMessage(role="assistant", content=f"##### 💻 Code:\n```{language}\n{code}\n```", metadata={"title": "🛠️ Executing code…", "status": "pending"})
                inner_history.append(cm)
                code_msgs.append(cm)
                status_msgs.append(f"🛠️ Executing {language}…")
                yield inner_history, main_history, _footer(status_msgs), ""

            # Observation
            om = re.search(r"<observation>(.*?)</observation>", content, re.DOTALL)
            if om:
                observation = om.group(1).strip()
                if code_msgs:
                    code_msgs[-1].metadata.update({"status": "done", "duration": t_step})
                inner_history.append(ChatMessage(role="assistant", content=f"##### 📋 Observation:\n```\n{observation}\n```", metadata={"status": "done", "duration": t_step, "collapsed": True, "collapsible": True}))
                status_msgs.append(f"✅ Done in {t_step:.1f}s")
                yield inner_history, main_history, _footer(status_msgs), ""

                # File previews in observation text
                if any(ext in observation for ext in SUPPORTED_EXTENSIONS):
                    matches = re.findall(r"(\S+?(?:\.png|\.jpg|\.jpeg|\.gif|\.bmp|\.webp|\.pdf))", observation)
                    valid = [m for m in matches if not (m.startswith(("Warning:", "Error:", "'"))) and not m.startswith(".")]
                    if valid:
                        inner_history.append(ChatMessage(role="assistant", content="", metadata={"title": "📁 Files"}))
                        for fp in valid:
                            fp = fp.strip("\"'").strip()
                            abs_path = None
                            if os.path.isabs(fp) and os.path.exists(fp):
                                abs_path = fp
                            elif os.path.exists(os.path.join(os.getcwd(), fp)):
                                abs_path = os.path.join(os.getcwd(), fp)
                            elif hasattr(agent, "path") and agent.path and os.path.exists(os.path.join(agent.path, fp)):
                                abs_path = os.path.join(agent.path, fp)
                            if abs_path:
                                inner_history.append(ChatMessage(role="assistant", content=gr.Image(abs_path) if not fp.lower().endswith(".pdf") else f"PDF: {abs_path}", metadata={"title": "📎 File"}))
                        yield inner_history, main_history, _footer(status_msgs), ""

            t = time()

        # Fallback if no explicit <solution>
        if not solution_found:
            final = s.get("messages", [])
            final_text = final[-1].content if final else ""
            sm2 = re.search(r"<solution>(.*?)</solution>", final_text, re.DOTALL)
            if sm2:
                sol = sm2.group(1).strip()
                main_history.append(ChatMessage(role="assistant", content=sol, metadata={"title": "✅ Solution"}))
                agent.main_history_copy += [{"role": "assistant", "content": sol}]
            else:
                cleaned = re.sub(r"<execute>.*?</execute>", "", final_text, flags=re.DOTALL)
                cleaned = re.sub(r"<observation>.*?</observation>", "", cleaned, flags=re.DOTALL)
                cleaned = re.sub(r"\n\s*\n", "\n\n", cleaned).strip()
                if cleaned:
                    main_history.append(ChatMessage(role="assistant", content=cleaned, metadata={"title": "📝 Summary"}))
                    agent.main_history_copy += [{"role": "assistant", "content": cleaned}]
                else:
                    main_history.append(ChatMessage(role="assistant", content="Task completed — check the execution log for details.", metadata={"title": "📝 Summary"}))
                    agent.main_history_copy += [{"role": "assistant", "content": "Task completed."}]

        inner_history.append(ChatMessage(role="assistant", content="👈 Returning result to main interface…", metadata={"title": "🔄 Complete"}))
        status_msgs.append("✅ All tasks complete")
        yield inner_history, main_history, _FOOTER_HTML, ""

    def like(data):  # no type annotation — avoids closure-scoped gr.LikeData eval issue
        print(f"👍 User liked response (index {data.index})")

    def clear_chat():
        agent.main_history_copy = []
        return [], []

    # ═════════════════════════════════════════════════════════
    # BUILD GRADIO INTERFACE
    # ═════════════════════════════════════════════════════════

    with gr.Blocks(
        css=BiochatTheme.CUSTOM_CSS,
        title="Biochat — Biomedical AI Agent",
        theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate").set(
            body_background_fill="#f7f8fb",
            button_primary_background_fill="#4f46e5",
            button_primary_background_fill_hover="#4338ca",
            button_primary_text_color="#ffffff",
            button_secondary_background_fill="#ffffff",
            button_secondary_border_color="#e5e7eb",
            block_background_fill="#ffffff",
            block_border_color="rgba(32, 36, 44, 0.08)",
            block_border_width="1px",
            block_radius="14px",
            input_background_fill="#ffffff",
            input_border_color="#e5e7eb",
            border_color_primary="rgba(32, 36, 44, 0.08)",
            panel_background_fill="#ffffff",
            background_fill_primary="#f7f8fb",
            background_fill_secondary="#fbfcfd",
        ),
    ) as demo:
        # Hidden state for example-prompt relay
        example_query = gr.State("")

        # ── Verification ──────────────────────────────────────
        verification_container = gr.Group(visible=require_verification)
        main_container = gr.Group(visible=not require_verification)

        with verification_container:
            gr.Markdown("# 🧬 Biochat — Access Verification")
            gr.Markdown("Please enter your access code to continue.")
            access_input = gr.Textbox(label="Access Code", type="password")
            access_error = gr.Markdown(visible=False)
            verify_btn = gr.Button("Verify Access")
            verify_btn.click(fn=verify_access_code, inputs=[access_input], outputs=[verification_container, main_container, access_error])

        # ── Main Interface ────────────────────────────────────
        with main_container:
            # Wrap everything in a shell div so our CSS can target it
            gr.HTML('<div class="biochat-shell">')

            # Header
            gr.HTML(_HEADER_HTML)

            # Main layout row
            gr.HTML('<div class="biochat-main">')

            # ── Sidebar ─────────────────────────────────────
            gr.HTML(_SIDEBAR_HTML)

            # ── Content area ────────────────────────────────
            gr.HTML('<div class="biochat-content">')

            # Chat panel
            gr.HTML('<div class="biochat-chat-panel" id="bc-chat-panel">')

            # Welcome + examples (shown initially)
            gr.HTML(_WELCOME_HTML + _EXAMPLES_HTML)

            # Chatbot
            with gr.Column(visible=True) as chat_col:
                main_chatbot = gr.Chatbot(
                    label="Conversation",
                    type="messages",
                    height=420,
                    show_copy_button=True,
                    elem_classes=["biochat-chatbot"],
                )

            gr.HTML('</div>')  # close chat panel

            # Input row
            gr.HTML('<div class="biochat-input-row">')
            with gr.Row():
                user_input = gr.Textbox(
                    placeholder="Ask a biomedical research question…",
                    show_label=False,
                    scale=10,
                    elem_classes=["biochat-input-box"],
                    container=False,
                )
            gr.HTML('</div>')  # close input row

            # Action buttons row
            with gr.Row():
                send_btn = gr.Button("➤ Send", scale=1, min_width=80, elem_classes=["biochat-send-btn"])
                clear_btn = gr.Button("Clear", scale=1, min_width=70, elem_classes=["biochat-clear-btn"])

            # Footer
            footer_html = gr.HTML(_FOOTER_HTML)

            # Attribution
            gr.HTML(_ATTRIBUTION_HTML)

            gr.HTML('</div>')  # close content
            gr.HTML('</div>')  # close main
            gr.HTML('</div>')  # close shell

        # Hidden execution log (not shown in main layout but used by generator)
        inner_chatbot = gr.Chatbot(
            label="Executor Log",
            type="messages",
            height=200,
            visible=False,
        )

        # ── EXAMPLE PROMPT BUTTONS ─────────────────────────
        # We use clickable HTML buttons with JS to set a hidden textbox,
        # then the textbox submit triggers the real handler.
        # This is the cleanest Gradio-compatible pattern.

        example_text = gr.Textbox(visible=False)

        example_text.submit(
            fn=generate_response,
            inputs=[example_text, inner_chatbot, main_chatbot],
            outputs=[inner_chatbot, main_chatbot, footer_html, example_text],
        ).then(lambda: gr.update(visible=True), None, [chat_col])

        # ── MAIN INPUT HANDLERS ────────────────────────────

        user_input.submit(
            fn=generate_response,
            inputs=[user_input, inner_chatbot, main_chatbot],
            outputs=[inner_chatbot, main_chatbot, footer_html, user_input],
        ).then(lambda: "", None, [user_input])

        send_btn.click(
            fn=generate_response,
            inputs=[user_input, inner_chatbot, main_chatbot],
            outputs=[inner_chatbot, main_chatbot, footer_html, user_input],
        ).then(lambda: "", None, [user_input])

        clear_btn.click(
            fn=clear_chat,
            inputs=[],
            outputs=[main_chatbot, inner_chatbot],
        )

        main_chatbot.like(like)

        # Inject JS to wire example-prompt buttons to the hidden textbox
        gr.HTML("""
        <script>
        (function() {
            // Wait for Gradio to finish mounting, then wire up example buttons
            const wire = function() {
                const buttons = document.querySelectorAll('.biochat-sample-btn');
                if (buttons.length === 0) { setTimeout(wire, 200); return; }
                buttons.forEach(function(btn) {
                    if (btn.dataset.wired) return;
                    btn.dataset.wired = '1';
                    btn.addEventListener('click', function() {
                        const query = btn.dataset.query || '';
                        // Find the hidden example_text textbox and fill it
                        const allInputs = document.querySelectorAll('textarea, input[type="text"]');
                        // Look for the hidden Gradio textbox for example_text — it's the one
                        // whose parent is hidden. We use the gradio data-testid pattern:
                        // Find visible user input and fill it directly instead.
                        const visibleInput = document.querySelector('.biochat-input-row textarea, .biochat-input-row input');
                        if (visibleInput) {
                            // Use native setter so React/Gradio picks it up
                            const nativeSetter = Object.getOwnPropertyDescriptor(
                                window.HTMLTextAreaElement.prototype, 'value'
                            ) || Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value'
                            );
                            if (nativeSetter && nativeSetter.set) {
                                nativeSetter.set.call(visibleInput, query);
                            } else {
                                visibleInput.value = query;
                            }
                            visibleInput.dispatchEvent(new Event('input', { bubbles: true }));
                            visibleInput.dispatchEvent(new Event('change', { bubbles: true }));
                            // Find and click the send button
                            setTimeout(function() {
                                const sendBtn = document.querySelector('.biochat-send-btn button, button.biochat-send-btn');
                                if (!sendBtn) {
                                    // Fallback: find any primary button near the input
                                    const inputRow = visibleInput.closest('.biochat-input-row');
                                    if (inputRow) {
                                        const btn = inputRow.parentElement.querySelector('button');
                                        if (btn) btn.click();
                                    }
                                } else {
                                    sendBtn.click();
                                }
                            }, 100);
                        }
                    });
                });
            };
            setTimeout(wire, 400);
        })();
        </script>
        """)

    return demo


def launch_biochat_ui(
    agent,
    thread_id: int = 42,
    share: bool = False,
    server_name: str = "127.0.0.1",
    require_verification: bool = False,
):
    from biochat.core.settings import biochat_settings as _settings
    from biochat.ui.auth import validate_remote_exposure

    # Reject unsafe non-loopback binds before launching.
    validate_remote_exposure(server_name, _settings)

    """Launch the polished ProtChat-inspired Biochat Gradio UI.

    Convenience wrapper that builds the UI via ``create_biochat_ui()``
    and then calls ``demo.launch()``.

    Args:
        agent: An initialized A1 agent instance.
        thread_id: Thread ID for conversation state.
        share: Whether to create a public shareable link.
        server_name: Server host to bind to.
        require_verification: Require access-code verification before use.
    """
    demo = create_biochat_ui(
        agent=agent,
        thread_id=thread_id,
        require_verification=require_verification,
    )
    print(f"🧬 Launching Biochat UI (Biochat engine) on http://{server_name}:7860")
    demo.launch(share=share, server_name=server_name)
