"""
PDF generation with cross-platform timeout support.

Provides ``_convert_markdown_to_pdf_in_subprocess`` (module-level,
required for ProcessPoolExecutor pickle) and ``execute_with_timeout``
with Unix SIGALRM + Windows ProcessPoolExecutor fallback.

See the design discussion in the refactoring plan for the rationale
behind the timeout mechanism choices.
"""

from __future__ import annotations

import os
import platform
import signal
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════
# Module-level worker (must be picklable for ProcessPoolExecutor)
# ═══════════════════════════════════════════════════════════════

def _convert_markdown_to_pdf_in_subprocess(markdown_path: str, pdf_path: str) -> str | None:
    """Convert a Markdown file to PDF using the best available library.

    Tries WeasyPrint → markdown2pdf → pandoc (same three-layer fallback
    as the original ``convert_markdown_to_pdf``).

    Defined at module scope so Python's ``pickle`` can serialise it
    for ``ProcessPoolExecutor`` under Windows ``spawn`` mode.

    Returns the output PDF path on success, or ``None`` on failure.
    """
    # Layer 1: WeasyPrint
    try:
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        with open(markdown_path, encoding="utf-8") as fh:
            markdown_content = fh.read()

        import markdown as _markdown
        html_content = _markdown.markdown(markdown_content, extensions=["fenced_code"])

        from biochat.utils.pdf_css import get_pdf_css_content
        css = get_pdf_css_content()

        html_doc = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>{css}</style></head><body>{html_content}</body></html>"
        )

        font_config = FontConfiguration()
        HTML(string=html_doc).write_pdf(pdf_path, font_config=font_config, optimize_images=True)
        return pdf_path
    except ImportError:
        pass

    # Layer 2: markdown2pdf
    try:
        from markdown2pdf import markdown2pdf as _m2p
        _m2p(markdown_path, pdf_path)
        return pdf_path
    except ImportError:
        pass

    # Layer 3: pandoc (subprocess)
    import subprocess
    try:
        subprocess.run(["pandoc", markdown_path, "-o", pdf_path], check=True, timeout=120)
        return pdf_path
    except (subprocess.CalledProcessError, FileNotFoundError, ImportError):
        pass

    # All layers failed
    return None


# ═══════════════════════════════════════════════════════════════
# Timeout: Unix (SIGALRM)
# ═══════════════════════════════════════════════════════════════

def _execute_with_unix_timeout(func: Callable, args: tuple, timeout: int) -> Any:
    """Run *func* with a SIGALRM timeout (Unix only).

    SIGALRM can interrupt in-process blocking system calls, making it
    suitable for PDF generation where WeasyPrint may block on I/O.
    """

    def _handler(signum: int, frame: object) -> None:
        raise TimeoutError(f"Operation timed out after {timeout}s")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout)
    try:
        return func(*args)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


# ═══════════════════════════════════════════════════════════════
# Timeout: Cross-platform (ProcessPoolExecutor)
# ═══════════════════════════════════════════════════════════════

def _execute_with_subprocess_timeout(func: Callable, args: tuple, timeout: int) -> Any:
    """Cross-platform timeout via ProcessPoolExecutor.

    .. warning::

       On timeout we access the private ``executor._processes`` dict
       to ``terminate()`` stuck workers.  This is a workaround for the
       absence of a public API in Python 3.11 to kill running workers.
       Replace with ``shutdown(force=True)`` or equivalent if a future
       Python version provides it.

    Lifecycle guarantee: the executor is always shut down — no leaks.
    """
    executor = ProcessPoolExecutor(max_workers=1)
    result: Any = None

    try:
        future = executor.submit(func, *args)
        # Assign, don't return — so the else branch is always reachable
        result = future.result(timeout=timeout)
    except TimeoutError:
        # Kill the stuck worker
        executor.shutdown(wait=False, cancel_futures=True)
        _terminate_stuck_workers(executor)
        raise
    except Exception:
        executor.shutdown(wait=False)
        raise
    else:
        executor.shutdown(wait=False)
        return result


def _terminate_stuck_workers(executor: ProcessPoolExecutor) -> None:
    """Best-effort SIGTERM to all workers via private ``_processes`` dict."""
    processes: dict[int, object] = getattr(executor, "_processes", {})
    for _pid, proc in list(processes.items()):
        try:
            if proc.is_alive():
                proc.terminate()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def convert_markdown_to_pdf(markdown_path: str, pdf_path: str) -> None:
    """Convert a Markdown file to PDF using the best available library.

    Tries WeasyPrint → markdown2pdf → pandoc, in that order.
    This is the original function preserved for backward compatibility.

    Raises:
        ImportError: If no PDF conversion library is available.
    """
    try:
        _convert_via_weasyprint(markdown_path, pdf_path)
    except ImportError:
        try:
            from markdown2pdf import markdown2pdf as _m2p
            _m2p(markdown_path, pdf_path)
        except ImportError:
            import subprocess
            try:
                subprocess.run(["pandoc", markdown_path, "-o", pdf_path], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                raise ImportError(
                    "No PDF conversion library available. "
                    "Install weasyprint, markdown2pdf, or pandoc."
                ) from exc


def _convert_via_weasyprint(markdown_path: str, pdf_path: str) -> None:
    """Internal: convert Markdown → PDF using WeasyPrint."""
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration

    with open(markdown_path, encoding="utf-8") as fh:
        markdown_content = fh.read()

    import markdown as _markdown
    html_content = _markdown.markdown(markdown_content, extensions=["fenced_code"])

    from biochat.utils.pdf_css import get_pdf_css_content
    css = get_pdf_css_content()

    html_doc = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{css}</style></head><body>{html_content}</body></html>"
    )

    font_config = FontConfiguration()
    HTML(string=html_doc).write_pdf(pdf_path, font_config=font_config, optimize_images=True)


def execute_with_timeout(
    func: Callable,
    args: tuple = (),
    *,
    timeout: int = 60,
) -> Any:
    """Run *func(*args)* with a wall-clock timeout.

    Strategy:
    - **Unix:** ``signal.SIGALRM`` — can interrupt in-process blocking I/O.
    - **Windows / fallback:** ``ProcessPoolExecutor`` with manual lifecycle.

    *func* MUST be a module-level function for pickle serialisation.

    Returns:
        The return value of ``func(*args)``.

    Raises:
        TimeoutError: if the operation exceeds *timeout* seconds.
    """
    unix_ok = platform.system() != "Windows" and hasattr(signal, "SIGALRM")

    if unix_ok:
        return _execute_with_unix_timeout(func, args, timeout)
    else:
        return _execute_with_subprocess_timeout(func, args, timeout)
