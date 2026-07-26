"""PDF CSS stylesheet — extracted from the original 345-line
``get_pdf_css_content()`` in ``utils.py``.

Pure data module — no logic, no imports beyond Python stdlib.
"""

from __future__ import annotations


def get_pdf_css_content() -> str:
    """Return the comprehensive CSS stylesheet used for PDF generation.

    Includes styling for: headings, code blocks, tables, lists,
    tool-call highlights, observations, plans, solutions, and
    parsing-error boxes.
    """
    return """
    body {
        font-family: sans-serif;
        font-size: 9pt;
        line-height: 1.4;
        max-width: 800px;
        margin: 0 auto;
        padding: 15px;
        color: #333;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: sans-serif;
        color: #2c3e50;
        margin-top: 1em;
        margin-bottom: 0.5em;
    }
    h1 {
        border-bottom: 2px solid #3498db;
        padding-bottom: 8px;
        font-size: 16pt;
    }
    h2 {
        border-bottom: 1px solid #bdc3c7;
        padding-bottom: 3px;
        font-size: 14pt;
    }
    h3 { font-size: 12pt; }
    h4 { font-size: 10pt; margin-top: 0.8em; margin-bottom: 0.3em; }
    h5, h6 { font-size: 9pt; margin-top: 0.6em; margin-bottom: 0.2em; }
    code {
        background-color: #f8f9fa;
        padding: 1px 3px;
        border-radius: 2px;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 8pt;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    pre {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 3px;
        overflow-x: auto;
        border-left: 3px solid #3498db;
        white-space: pre-wrap;
        word-wrap: break-word;
        font-size: 8pt;
        margin: 0.5em 0;
    }
    pre code {
        background-color: transparent;
        padding: 0;
        border-radius: 0;
        font-size: 8pt;
    }
    strong {
        font-size: 9pt;
        font-weight: normal;
        color: #6c757d;
        font-style: italic;
    }
    blockquote {
        border-left: 3px solid #bdc3c7;
        margin: 0.5em 0;
        padding-left: 15px;
        color: #7f8c8d;
        font-size: 8pt;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 0.5em 0;
        font-size: 8pt;
    }
    th, td {
        border: 1px solid #bdc3c7;
        padding: 4px 8px;
        text-align: left;
    }
    th { background-color: #ecf0f1; font-weight: bold; }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 10px auto;
        border: 1px solid #ddd;
        border-radius: 3px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    p {
        font-family: sans-serif;
        margin: 0.3em 0;
    }
    .tool-call-highlight {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 3px;
        padding: 0;
        margin: 10px 0;
        overflow: hidden;
    }
    .tool-call-header {
        background-color: #e9ecef;
        color: #495057;
        padding: 8px 12px;
        margin: 0;
        font-weight: normal;
        font-size: 9pt;
        font-style: italic;
        border-bottom: 1px solid #dee2e6;
    }
    .tool-call-input {
        background-color: #f8f9fa;
        border: none;
        border-radius: 0;
        padding: 10px 12px;
        margin: 0;
        color: #333;
        font-size: 8pt;
        line-height: 1.4;
    }
    .tool-call-input strong { color: #495057; font-weight: normal; font-size: 8pt; font-style: italic; }
    .tool-call-input pre {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 3px;
        padding: 10px;
        margin: 0;
        font-size: 8pt;
        line-height: 1.4;
        overflow-x: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    .tool-call-input code { background-color: transparent; padding: 0; border-radius: 0; font-size: 8pt; color: #2c3e50; }
    .tools-used {
        background-color: #f8f9fa;
        border-top: 1px solid #dee2e6;
        padding: 8px 12px;
        margin: 0;
        font-size: 8pt;
        color: #6c757d;
    }
    .tools-used strong { color: #6c757d; font-weight: normal; font-size: 8pt; font-style: italic; }
    .title-text {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 3px;
        padding: 0;
        margin: 10px 0;
        overflow: hidden;
    }
    .title-text-header {
        background-color: #e9ecef;
        color: #495057;
        padding: 8px 12px;
        margin: 0;
        font-weight: normal;
        font-size: 9pt;
        font-style: italic;
        border-bottom: 1px solid #dee2e6;
    }
    .title-text-header strong { color: #495057; font-weight: normal; font-size: 9pt; font-style: italic; }
    .title-text-content {
        background-color: #f8f9fa;
        border: none;
        border-radius: 0;
        padding: 10px 12px;
        margin: 0;
        color: #333;
        font-size: 8pt;
        line-height: 1.4;
    }
    .title-text.plan { background-color: #e3f2fd; border-color: #bbdefb; }
    .title-text.plan .title-text-header { background-color: #bbdefb; color: #1976d2; }
    .title-text.plan .title-text-content { background-color: #e3f2fd; }
    .plan-title { font-style: italic; font-weight: normal; color: #1565c0; text-shadow: 0 1px 2px rgba(0,0,0,0.1); }
    .plan-title strong { font-weight: normal; }
    .title-text.observation { background-color: #f3e5f5; border-color: #e1bee7; }
    .title-text.observation .title-text-header { background-color: #e1bee7; color: #7b1fa2; }
    .title-text.observation .title-text-content { background-color: #f3e5f5; }
    .title-text.summary { background-color: #fff3e0; border-color: #ffcc02; }
    .title-text.summary .title-text-header { background-color: #ffcc02; color: #f57c00; }
    .title-text.summary .title-text-content { background-color: #fff3e0; }
    .title-text-content ul {
        background-color: transparent; border: none; border-radius: 0;
        padding: 0; margin: 0; color: #333; font-size: 8pt; line-height: 1.4;
    }
    .title-text-content li { margin: 3px 0; color: #333; }
    .title-text-content li strong { color: #495057; font-weight: normal; font-size: 8pt; font-style: italic; }
    .title-text-content li code {
        background-color: #e9ecef; color: #333;
        padding: 1px 3px; border-radius: 2px;
        font-family: 'Monaco','Menlo','Ubuntu Mono',monospace; font-size: 7pt;
    }
    .title-text-content pre {
        background-color: #f8f9fa; border: 1px solid #e9ecef;
        border-radius: 3px; padding: 10px; margin: 0;
        font-size: 8pt; line-height: 1.4; overflow-x: auto;
        white-space: pre-wrap; word-wrap: break-word;
    }
    .title-text-content code { background-color: transparent; padding: 0; border-radius: 0; font-size: 8pt; color: #2c3e50; }
    .parsing-error-box {
        background-color: #ffebee; border: 1px solid #f44336;
        border-radius: 4px; padding: 8px 12px; margin: 8px 0;
        font-size: 9pt; color: #c62828; box-shadow: 0 2px 4px rgba(244,67,54,0.1);
    }
    .parsing-error-header { font-weight: bold; margin-bottom: 4px; color: #d32f2f; }
    .parsing-error-content {
        font-family: 'Courier New',monospace; background-color: #ffcdd2;
        padding: 4px 6px; border-radius: 2px; margin-top: 4px;
        font-size: 8pt; white-space: pre-wrap; word-wrap: break-word;
    }
    """
