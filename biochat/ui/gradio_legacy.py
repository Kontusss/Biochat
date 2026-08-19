"""
Legacy Gradio demo UI — extracted from ``A1.launch_gradio_demo()``.

Preserved for backward compatibility with the original ~375-line
inlined Gradio interface.  New code should use the Biochat UI
(``biochat_ui.py``) or Streamlit (``biochat_streamlit.py``).
"""

from __future__ import annotations

import os
import re
from time import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from biochat.agent.a1 import A1


_SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".pdf")


def launch_legacy_gradio_ui(
    agent: "A1",
    thread_id: int = 42,
    share: bool = False,
    server_name: str = "0.0.0.0",
    require_verification: bool = False,
) -> None:
    """Launch the original Biochat Gradio demo interface."""
    try:
        import gradio as gr
        from gradio import ChatMessage
    except ImportError:
        raise ImportError(
            "Gradio is not installed. Please install with: pip install gradio"
        ) from None

    from langchain_core.messages import AIMessage, HumanMessage

    available_access_codes = ["Biochat2025"]
    agent.main_history_copy: list[dict] = []

    def _verify(code: str):
        if code in available_access_codes:
            return (gr.update(visible=False), gr.update(visible=True),
                    gr.update(visible=False))
        return (gr.update(visible=True), gr.update(visible=False),
                gr.update(value="Incorrect access code.", visible=True))

    def _generate(prompt_input, inner_history, main_history):
        if main_history is None:
            main_history = []
        if inner_history is None:
            inner_history = []

        text_input = prompt_input.get("text", "")
        files = prompt_input.get("files", [])

        main_history.append(ChatMessage(role="user", content=text_input or "[Uploaded file]"))
        main_history.append(ChatMessage(role="assistant", content="Executor is working on it 👉"))
        yield inner_history, main_history

        for file_info in files:
            text_input += f"\n\nUser uploaded this file: {file_info}\nPlease use it."

        # Only pass the NEW message — let checkpointer handle history accumulation.
        # (No more manual main_history_copy rebuild — add_messages reducer
        #  in AgentState handles multi-turn state correctly.)
        inputs = {"messages": [HumanMessage(content=text_input)], "next_step": None}
        config = {"recursion_limit": 500, "configurable": {"thread_id": thread_id}}

        t = time()
        solution_found = False
        code_msgs: list[ChatMessage] = []

        if agent.use_tool_retriever:
            inner_history.append(ChatMessage(
                role="assistant",
                content="Retrieving relevant tools, data lake items, and libraries...",
            ))
            yield inner_history, main_history
            try:
                selected = agent._prepare_resources_for_retrieval(text_input)
                if selected:
                    agent.update_system_prompt_with_selected_resources(selected)
            except Exception as e:
                inner_history.append(ChatMessage(
                    role="assistant",
                    content=f"Tool retrieval unavailable: {e}",
                ))
                yield inner_history, main_history

        for s in agent.app.stream(inputs, stream_mode="values", config=config):
            t_step = time() - t
            message = s["messages"][-1]
            if message.content == text_input:
                t = time()
                continue
            if not isinstance(message.content, str):
                t = time()
                continue

            content = message.content

            # Thinking
            tag_positions = []
            for tag_name in ("<execute>", "<solution>", "<observation>"):
                p = content.find(tag_name)
                if p != -1:
                    tag_positions.append(p)
            if tag_positions:
                thinking = content[:min(tag_positions)].strip()
                if thinking and len(thinking) > 20:
                    inner_history.append(ChatMessage(
                        role="assistant", content=thinking,
                        metadata={"title": "🤔 Reasoning"},
                    ))
                    yield inner_history, main_history

            # Solution
            sm = re.search(r"<solution>(.*?)</solution>", content, re.DOTALL)
            if sm and not solution_found:
                solution = sm.group(1).strip()
                main_history.append(ChatMessage(
                    role="assistant", content=solution,
                    metadata={"title": "✅ Answer"},
                ))
                pass  # state accumulated by checkpointer; no manual copy needed
                solution_found = True
                yield inner_history, main_history

            # Execute
            em = re.search(r"<execute>(.*?)</execute>", content, re.DOTALL)
            if em:
                code = em.group(1).strip()
                language = "python"
                if code.strip().startswith("#!R"):
                    language = "r"
                    code = re.sub(r"^#!R", "", code, count=1).strip()
                elif code.strip().startswith(("#!BASH", "#!CLI")):
                    language = "bash"
                    code = re.sub(r"^#!BASH|^#!CLI", "", code, count=1).strip()
                cm = ChatMessage(
                    role="assistant",
                    content=f"##### 💻 Code:\n```{language}\n{code}\n```",
                    metadata={"title": "🛠️ Executing code…", "status": "pending"},
                )
                inner_history.append(cm)
                code_msgs.append(cm)
                yield inner_history, main_history

            # Observation
            om = re.search(r"<observation>(.*?)</observation>", content, re.DOTALL)
            if om:
                observation = om.group(1).strip()
                if code_msgs:
                    code_msgs[-1].metadata.update({"status": "done", "duration": t_step})
                inner_history.append(ChatMessage(
                    role="assistant",
                    content=f"##### 📋 Observation:\n```\n{observation}\n```",
                    metadata={"status": "done", "duration": t_step,
                              "collapsed": True, "collapsible": True},
                ))
                yield inner_history, main_history

                # File previews
                if any(ext in observation for ext in _SUPPORTED_EXTENSIONS):
                    matches = re.findall(
                        r"(\S+?(?:\.png|\.jpg|\.jpeg|\.gif|\.bmp|\.webp|\.pdf))",
                        observation,
                    )
                    valid = [m for m in matches
                             if not m.startswith(("Warning:", "Error:", "'", "."))]
                    if valid:
                        inner_history.append(ChatMessage(
                            role="assistant", content="",
                            metadata={"title": "📁 Files"},
                        ))
                        for fp in valid:
                            fp = fp.strip("\"'").strip()
                            abs_path = None
                            if os.path.isabs(fp) and os.path.exists(fp):
                                abs_path = fp
                            elif os.path.exists(os.path.join(os.getcwd(), fp)):
                                abs_path = os.path.join(os.getcwd(), fp)
                            elif (hasattr(agent, "path") and agent.path
                                  and os.path.exists(os.path.join(agent.path, fp))):
                                abs_path = os.path.join(agent.path, fp)
                            if abs_path:
                                inner_history.append(ChatMessage(
                                    role="assistant",
                                    content=(gr.Image(abs_path)
                                             if not fp.lower().endswith(".pdf")
                                             else f"PDF: {abs_path}"),
                                    metadata={"title": "📎 File"},
                                ))
                        yield inner_history, main_history

            t = time()

        if not solution_found:
            final_text = s.get("messages", [{}])[-1].content if s.get("messages") else ""
            sm2 = re.search(r"<solution>(.*?)</solution>", final_text, re.DOTALL)
            if sm2:
                sol = sm2.group(1).strip()
                main_history.append(ChatMessage(role="assistant", content=sol,
                                                metadata={"title": "✅ Solution"}))
                pass  # state via checkpointer
            else:
                cleaned = re.sub(r"<execute>.*?</execute>", "", final_text, flags=re.DOTALL)
                cleaned = re.sub(r"<observation>.*?</observation>", "", cleaned, flags=re.DOTALL)
                cleaned = re.sub(r"\n\s*\n", "\n\n", cleaned).strip()
                if cleaned:
                    main_history.append(ChatMessage(
                        role="assistant", content=cleaned,
                        metadata={"title": "📝 Summary"},
                    ))
                    pass  # state via checkpointer
                else:
                    main_history.append(ChatMessage(
                        role="assistant",
                        content="Task completed — check the execution log.",
                        metadata={"title": "📝 Summary"},
                    ))
                    pass  # state via checkpointer

        inner_history.append(ChatMessage(
            role="assistant",
            content="👈 Returning result to main interface…",
            metadata={"title": "🔄 Complete"},
        ))
        yield inner_history, main_history

    def _like(data):
        print(f"User liked response (index {data.index})")

    def _clear():
        agent.main_history_copy = []
        return [], []

    with gr.Blocks(title="Biochat A1 Agent") as demo:
        verification_container = gr.Group(visible=require_verification)
        main_container = gr.Group(visible=not require_verification)

        with verification_container:
            gr.Markdown("# Biochat A1 Agent — Access Verification")
            access_input = gr.Textbox(label="Access Code", type="password")
            access_error = gr.Markdown(visible=False)
            gr.Button("Verify Access").click(
                fn=_verify, inputs=[access_input],
                outputs=[verification_container, main_container, access_error],
            )

        with main_container:
            with gr.Row():
                main_chatbot = gr.Chatbot(
                    label="Biochat A1 Agent", type="messages",
                    height=800, show_copy_button=True,
                )
                inner_chatbot = gr.Chatbot(
                    label="Biochat Executor", type="messages",
                    height=800, show_copy_button=True,
                )

            with gr.Row():
                prompt_input = gr.MultimodalTextbox(
                    interactive=True, file_count="multiple",
                    placeholder="Ask something or upload a file...",
                    show_label=False,
                )

            prompt_input.submit(
                _generate, [prompt_input, inner_chatbot, main_chatbot],
                [inner_chatbot, main_chatbot],
            ).then(lambda: gr.MultimodalTextbox(value=None), None, [prompt_input])
            main_chatbot.like(_like)

    print(f"Launching Biochat Gradio demo (Biochat engine) on {server_name}:7860")
    demo.launch(share=share, server_name=server_name)
