"""Jinja2 + WeasyPrint. Returns bytes; nothing touches disk, per the
ephemeral filesystem rule in CLAUDE.md.

Chosen over a headless-browser renderer because it is pure Python, adds no
Chromium download to the image, and does not need a browser process on a
512 MB instance.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)


def render_report_pdf(report: dict) -> bytes:
    # Imported lazily: WeasyPrint needs Pango/GDK-Pixbuf/Cairo native
    # libraries that ship via the Dockerfile's apt-get layer on Render, but
    # are not present on a bare Windows dev machine. A module-level import
    # would break `import app.main` for anyone who never touches PDF export.
    from weasyprint import HTML

    css = (TEMPLATE_DIR / "report.css").read_text(encoding="utf-8")
    template = _env.get_template("report.html.j2")
    html = template.render(css=css, **report)
    return HTML(string=html).write_pdf()
