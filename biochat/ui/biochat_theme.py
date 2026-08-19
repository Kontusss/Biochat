"""
Biochat Theme — ProtChat-inspired Gradio styling.

Production-grade CSS that transforms the default Gradio look into
a polished, modern biomedical AI interface matching the ProtChat
reference design from /Users/walker/Desktop/Core.

Design system:
  - Background: #f7f8fb (soft gray)
  - Cards: #ffffff with subtle shadows
  - Accent: #4f46e5 (indigo)
  - Radius: 14px (cards), 20px (quick-action pills)
  - Font: system-ui stack with Noto Sans SC
  - Status: green (#16a34a), amber (#f59e0b), red (#dc2626)
"""

from __future__ import annotations


class BiochatTheme:
    """Design tokens and CSS for the ProtChat-inspired Biochat UI."""

    # ── Color Palette ──────────────────────────────────────────
    BG_PRIMARY = "#f7f8fb"
    BG_SIDEBAR = "#fbfcfd"
    BG_CARD = "#ffffff"
    TEXT_PRIMARY = "#20242c"
    TEXT_SECONDARY = "#5a616d"
    TEXT_MUTED = "#8b919e"
    BORDER = "rgba(32, 36, 44, 0.08)"
    BORDER_SOLID = "#e5e7eb"
    ACCENT = "#4f46e5"
    ACCENT_HOVER = "#4338ca"
    ACCENT_SOFT = "rgba(79, 70, 229, 0.06)"
    GREEN = "#16a34a"
    GREEN_SOFT = "rgba(22, 163, 74, 0.10)"
    AMBER = "#f59e0b"
    AMBER_SOFT = "rgba(245, 158, 11, 0.10)"
    RED = "#dc2626"
    RED_SOFT = "rgba(220, 38, 38, 0.10)"
    RADIUS = "14px"
    RADIUS_SM = "8px"
    RADIUS_PILL = "20px"
    SHADOW_CARD = "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)"
    SHADOW_ELEVATED = "0 4px 12px rgba(0,0,0,0.06)"

    # ── Master CSS ─────────────────────────────────────────────
    CUSTOM_CSS = r"""
    /* ══════════════════════════════════════════════════════════════
       BIOCHAT — ProtChat-Inspired Design System
       Built on the Biochat scientific engine
       ══════════════════════════════════════════════════════════════ */

    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700;800&display=swap');

    /* ── CSS Variables ─────────────────────────────────────── */
    :root {
      --bc-bg: #f7f8fb;
      --bc-sidebar: #fbfcfd;
      --bc-card: #ffffff;
      --bc-text: #20242c;
      --bc-text-2: #5a616d;
      --bc-text-3: #8b919e;
      --bc-border: rgba(32, 36, 44, 0.08);
      --bc-border-solid: #e5e7eb;
      --bc-accent: #4f46e5;
      --bc-accent-hover: #4338ca;
      --bc-accent-soft: rgba(79, 70, 229, 0.06);
      --bc-green: #16a34a;
      --bc-green-soft: rgba(22, 163, 74, 0.10);
      --bc-amber: #f59e0b;
      --bc-amber-soft: rgba(245, 158, 11, 0.10);
      --bc-red: #dc2626;
      --bc-red-soft: rgba(220, 38, 38, 0.10);
      --bc-radius: 14px;
      --bc-radius-sm: 8px;
      --bc-radius-pill: 20px;
      --bc-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03);
      --bc-shadow-lg: 0 4px 12px rgba(0,0,0,0.06);
      --bc-font: 'Noto Sans SC', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      --bc-mono: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Monaco, Consolas, monospace;
    }

    /* ── Global Reset ──────────────────────────────────────── */
    body, .gradio-container {
      font-family: var(--bc-font) !important;
      background: var(--bc-bg) !important;
      color: var(--bc-text) !important;
    }
    .gradio-container { max-width: 100% !important; }
    .contain { max-width: 100% !important; padding: 0 !important; }

    /* Hide Gradio footer / branding */
    footer { display: none !important; }

    /* ── Biochat Shell ─────────────────────────────────────── */
    .biochat-shell {
      display: flex;
      flex-direction: column;
      height: 100vh;
      background: var(--bc-bg);
      overflow: hidden;
    }

    /* ── Header ────────────────────────────────────────────── */
    .biochat-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 24px;
      background: var(--bc-card);
      border-bottom: 1px solid var(--bc-border);
      flex-shrink: 0;
      z-index: 10;
    }
    .biochat-header .bc-logo {
      font-size: 22px;
      font-weight: 800;
      color: var(--bc-text);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .biochat-header .bc-version {
      font-size: 12px;
      font-weight: 600;
      color: var(--bc-text-3);
      background: var(--bc-accent-soft);
      padding: 3px 10px;
      border-radius: 10px;
    }
    .biochat-header .bc-engine-badge {
      font-size: 11px;
      font-weight: 500;
      color: var(--bc-text-3);
      background: rgba(139, 145, 158, 0.10);
      padding: 3px 10px;
      border-radius: 10px;
      margin-left: auto;
    }
    .biochat-header .bc-header-status {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 500;
      color: var(--bc-green);
      background: var(--bc-green-soft);
      padding: 4px 12px;
      border-radius: 10px;
      margin-left: 8px;
    }
    .biochat-header .bc-header-status .bc-dot {
      width: 7px; height: 7px; border-radius: 50%; background: var(--bc-green);
      animation: bc-pulse 2s ease-in-out infinite;
    }
    @keyframes bc-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }

    /* ── Main Layout (Sidebar + Content) ──────────────────── */
    .biochat-main {
      display: flex;
      flex: 1;
      overflow: hidden;
    }

    /* ── Sidebar ───────────────────────────────────────────── */
    .biochat-sidebar {
      width: 272px;
      min-width: 272px;
      background: var(--bc-sidebar);
      border-right: 1px solid var(--bc-border);
      display: flex;
      flex-direction: column;
      padding: 16px;
      gap: 14px;
      overflow-y: auto;
      flex-shrink: 0;
    }
    .biochat-sidebar .bc-section-title {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--bc-text-3);
      margin-bottom: 2px;
    }
    .biochat-sidebar .bc-cap-list {
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .biochat-sidebar .bc-cap-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12.5px;
      color: var(--bc-text-2);
      padding: 5px 8px;
      border-radius: 6px;
      cursor: default;
      transition: background 0.12s;
    }
    .biochat-sidebar .bc-cap-item:hover {
      background: var(--bc-accent-soft);
    }
    .biochat-sidebar .bc-cap-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: var(--bc-accent);
      flex-shrink: 0;
      opacity: 0.5;
    }
    .biochat-sidebar .bc-divider {
      height: 1px;
      background: var(--bc-border);
      margin: 2px 0;
    }

    /* ── Sidebar Status Badges ─────────────────────────────── */
    .biochat-sidebar .bc-status-list {
      display: flex;
      flex-direction: column;
      gap: 5px;
    }
    .biochat-status-badge {
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 12px;
      font-weight: 500;
      padding: 6px 10px;
      border-radius: 7px;
    }
    .biochat-status-badge.bc-ok {
      background: var(--bc-green-soft);
      color: var(--bc-green);
    }
    .biochat-status-badge.bc-warn {
      background: var(--bc-amber-soft);
      color: var(--bc-amber);
    }
    .biochat-status-badge.bc-off {
      background: rgba(139, 145, 158, 0.08);
      color: var(--bc-text-3);
    }
    .biochat-status-badge .bc-sb-dot {
      width: 7px; height: 7px; border-radius: 50%;
      flex-shrink: 0;
    }
    .biochat-status-badge.bc-ok .bc-sb-dot { background: var(--bc-green); }
    .biochat-status-badge.bc-warn .bc-sb-dot { background: var(--bc-amber); }
    .biochat-status-badge.bc-off .bc-sb-dot { background: #c0c5cc; }

    /* ── Sidebar Attribution ───────────────────────────────── */
    .biochat-sidebar .bc-sidebar-footer {
      margin-top: auto;
      padding-top: 10px;
      border-top: 1px solid var(--bc-border);
      font-size: 11px;
      color: var(--bc-text-3);
      line-height: 1.5;
    }
    .biochat-sidebar .bc-sidebar-footer a {
      color: var(--bc-accent);
      text-decoration: none;
    }

    /* ── Content Area ──────────────────────────────────────── */
    .biochat-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      min-width: 0;
    }

    /* ── Chat Panel ────────────────────────────────────────── */
    .biochat-chat-panel {
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    /* ── Welcome Card ──────────────────────────────────────── */
    .biochat-welcome {
      text-align: center;
      padding: 48px 24px 32px;
    }
    .biochat-welcome .bc-welcome-icon {
      font-size: 48px;
      margin-bottom: 16px;
    }
    .biochat-welcome h2 {
      font-size: 26px;
      font-weight: 800;
      color: var(--bc-text);
      margin: 0 0 6px;
    }
    .biochat-welcome .bc-welcome-sub {
      font-size: 15px;
      font-weight: 600;
      color: var(--bc-text-2);
      margin-bottom: 6px;
    }
    .biochat-welcome .bc-welcome-desc {
      font-size: 13.5px;
      line-height: 1.7;
      color: var(--bc-text-3);
      max-width: 500px;
      margin: 0 auto 24px;
    }

    /* ── Quick-Action / Example Prompt Pills ───────────────── */
    .biochat-examples {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: center;
      max-width: 620px;
      margin: 0 auto;
    }
    .biochat-example-btn {
      padding: 10px 18px;
      border: 1px solid var(--bc-border-solid);
      border-radius: var(--bc-radius-pill);
      background: var(--bc-card);
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      color: var(--bc-text);
      font-family: var(--bc-font);
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .biochat-example-btn:hover {
      border-color: var(--bc-accent);
      color: var(--bc-accent);
      background: var(--bc-accent-soft);
      transform: translateY(-1px);
    }

    /* ── Override Gradio Chatbot ───────────────────────────── */
    .biochat-chatbot {
      border-radius: var(--bc-radius) !important;
      border: 1px solid var(--bc-border) !important;
      background: var(--bc-card) !important;
      box-shadow: var(--bc-shadow) !important;
      overflow: hidden !important;
    }
    .biochat-chatbot .bubble-wrap {
      padding: 8px 0 !important;
    }
    /* User message bubble — indigo accent */
    .biochat-chatbot .bubble-wrap .user .message {
      background: var(--bc-accent) !important;
      color: #ffffff !important;
      border-radius: var(--bc-radius) var(--bc-radius) 4px var(--bc-radius) !important;
      padding: 12px 16px !important;
      font-size: 14px !important;
      line-height: 1.6 !important;
      max-width: 80% !important;
    }
    /* Assistant message bubble — white card */
    .biochat-chatbot .bubble-wrap .bot .message {
      background: var(--bc-card) !important;
      color: var(--bc-text) !important;
      border: 1px solid var(--bc-border) !important;
      border-radius: var(--bc-radius) var(--bc-radius) var(--bc-radius) 4px !important;
      padding: 14px 18px !important;
      font-size: 14px !important;
      line-height: 1.65 !important;
      max-width: 85% !important;
      box-shadow: var(--bc-shadow) !important;
    }
    /* Code blocks inside assistant messages */
    .biochat-chatbot .bot .message pre {
      background: #1e1e2e !important;
      color: #cdd6f4 !important;
      border-radius: var(--bc-radius-sm) !important;
      padding: 14px !important;
      font-family: var(--bc-mono) !important;
      font-size: 13px !important;
      overflow-x: auto !important;
    }
    .biochat-chatbot .bot .message code {
      font-family: var(--bc-mono) !important;
      font-size: 13px !important;
      background: rgba(0,0,0,0.05) !important;
      padding: 2px 6px !important;
      border-radius: 4px !important;
    }
    .biochat-chatbot .bot .message pre code {
      background: transparent !important;
      padding: 0 !important;
    }

    /* ── Input Area ────────────────────────────────────────── */
    .biochat-input-row {
      display: flex;
      gap: 10px;
      padding: 16px 24px;
      background: var(--bc-bg);
      border-top: 1px solid var(--bc-border);
      flex-shrink: 0;
      align-items: flex-end;
    }
    .biochat-input-row textarea,
    .biochat-input-row input[type="text"] {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid var(--bc-border-solid) !important;
      border-radius: var(--bc-radius) !important;
      font-family: var(--bc-font) !important;
      font-size: 14px !important;
      background: var(--bc-card) !important;
      color: var(--bc-text) !important;
      resize: none !important;
      outline: none !important;
      min-height: 48px !important;
      max-height: 150px !important;
      transition: border-color 0.15s, box-shadow 0.15s !important;
    }
    .biochat-input-row textarea:focus,
    .biochat-input-row input[type="text"]:focus {
      border-color: var(--bc-accent) !important;
      box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.10) !important;
    }
    .biochat-input-row textarea::placeholder {
      color: var(--bc-text-3) !important;
    }

    /* Send button */
    .biochat-send-btn {
      width: 48px;
      height: 48px;
      border-radius: var(--bc-radius) !important;
      border: none !important;
      background: var(--bc-accent) !important;
      color: #ffffff !important;
      font-size: 20px !important;
      cursor: pointer !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      flex-shrink: 0 !important;
      transition: background 0.15s, transform 0.1s !important;
      padding: 0 !important;
      min-width: 48px !important;
    }
    .biochat-send-btn:hover {
      background: var(--bc-accent-hover) !important;
      transform: scale(1.04) !important;
    }
    .biochat-send-btn:active {
      transform: scale(0.96) !important;
    }

    /* Clear button */
    .biochat-clear-btn {
      padding: 12px 16px !important;
      border-radius: var(--bc-radius) !important;
      border: 1px solid var(--bc-border-solid) !important;
      background: var(--bc-card) !important;
      color: var(--bc-text-2) !important;
      font-size: 13px !important;
      font-weight: 500 !important;
      cursor: pointer !important;
      transition: all 0.15s !important;
      font-family: var(--bc-font) !important;
    }
    .biochat-clear-btn:hover {
      border-color: var(--bc-red) !important;
      color: var(--bc-red) !important;
      background: var(--bc-red-soft) !important;
    }

    /* ── Status Footer Bar ─────────────────────────────────── */
    .biochat-footer-bar {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 24px;
      background: var(--bc-card);
      border-top: 1px solid var(--bc-border);
      flex-shrink: 0;
      font-size: 12px;
      color: var(--bc-text-2);
      flex-wrap: wrap;
    }
    .biochat-footer-bar .bc-footer-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--bc-green);
      flex-shrink: 0;
    }
    .biochat-footer-bar .bc-footer-sep {
      width: 1px; height: 14px; background: var(--bc-border-solid); margin: 0 2px;
    }
    .biochat-footer-bar .bc-footer-badge {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 8px;
    }
    .biochat-footer-bar .bc-footer-badge.good {
      background: var(--bc-green-soft); color: var(--bc-green);
    }
    .biochat-footer-bar .bc-footer-badge.warn {
      background: var(--bc-amber-soft); color: var(--bc-amber);
    }
    .biochat-footer-bar .bc-footer-badge.off {
      background: rgba(139,145,158,0.08); color: var(--bc-text-3);
    }

    /* ── Attribution ───────────────────────────────────────── */
    .biochat-attribution {
      text-align: center;
      padding: 8px;
      font-size: 11px;
      color: var(--bc-text-3);
      background: var(--bc-bg);
      flex-shrink: 0;
    }
    .biochat-attribution a {
      color: var(--bc-accent);
      text-decoration: none;
      font-weight: 500;
    }

    /* ── Tabs (override Gradio) ────────────────────────────── */
    .tabs {
      border: none !important;
      background: transparent !important;
    }
    .tab-nav {
      background: var(--bc-card) !important;
      border: 1px solid var(--bc-border) !important;
      border-radius: var(--bc-radius) !important;
      padding: 3px !important;
      gap: 2px !important;
      display: inline-flex !important;
    }
    .tab-nav button {
      padding: 7px 16px !important;
      border-radius: 11px !important;
      font-size: 13px !important;
      font-weight: 600 !important;
      font-family: var(--bc-font) !important;
      border: none !important;
      background: transparent !important;
      color: var(--bc-text-2) !important;
      cursor: pointer !important;
      transition: all 0.15s !important;
    }
    .tab-nav button.selected {
      background: var(--bc-accent) !important;
      color: #ffffff !important;
    }
    .tabitem {
      border: none !important;
      padding: 0 !important;
    }

    /* ── Scrollbar ─────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.10); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.18); }

    /* ── Responsive ────────────────────────────────────────── */
    @media (max-width: 768px) {
      .biochat-sidebar { display: none !important; }
      .biochat-header { padding: 10px 16px; }
      .biochat-chat-panel { padding: 12px; }
      .biochat-input-row { padding: 10px 12px; }
      .biochat-examples { gap: 6px; }
      .biochat-example-btn { font-size: 12px; padding: 8px 14px; }
    }
    """


def get_biochat_theme():
    """Return a Gradio Soft theme pre-configured with Biochat colors.

    Returns None if Gradio is not installed.
    """
    try:
        import gradio as gr

        return gr.themes.Soft(
            primary_hue="indigo",
            neutral_hue="slate",
        ).set(
            body_background_fill=BiochatTheme.BG_PRIMARY,
            body_background_fill_dark="#1a1b2e",
            button_primary_background_fill=BiochatTheme.ACCENT,
            button_primary_background_fill_hover=BiochatTheme.ACCENT_HOVER,
            button_primary_text_color="#ffffff",
            button_primary_border_color=BiochatTheme.ACCENT,
            button_secondary_background_fill=BiochatTheme.BG_CARD,
            button_secondary_border_color=BiochatTheme.BORDER_SOLID,
            button_secondary_text_color=BiochatTheme.TEXT_PRIMARY,
            block_background_fill=BiochatTheme.BG_CARD,
            block_border_color=BiochatTheme.BORDER,
            block_border_width="1px",
            block_radius=BiochatTheme.RADIUS,
            input_background_fill=BiochatTheme.BG_CARD,
            input_border_color=BiochatTheme.BORDER_SOLID,
            input_radius=BiochatTheme.RADIUS_SM,
            border_color_primary=BiochatTheme.BORDER,
            color_accent_soft=BiochatTheme.ACCENT_SOFT,
            panel_background_fill=BiochatTheme.BG_CARD,
            background_fill_primary=BiochatTheme.BG_PRIMARY,
            background_fill_secondary=BiochatTheme.BG_SIDEBAR,
        )
    except ImportError:
        return None
