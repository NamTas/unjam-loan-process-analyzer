"""Look and feel only: CSS and the page header. Change colours/spacing here, nothing else needs to change."""
from __future__ import annotations

import html

import streamlit as st

from . import TAGLINE

ACCENT = "#6C5CE7"  # main colour (violet). Try "#0984E3" for blue or "#00B894" for green.

_CSS = """
<style>
/* 1. Streamlit's top bar is ~3.75rem tall; the default gap below it is far too big */
.block-container, [data-testid="stMainBlockContainer"] {
    padding-top: 4rem !important; padding-bottom: 2.5rem; max-width: 1280px;
}
[data-testid="stSidebarHeader"] { display: none; }
[data-testid="stSidebarUserContent"] { padding-top: 1.4rem; }
#MainMenu, footer { visibility: hidden; }

/* 2. header card */
.uj-header { display: flex; align-items: center; gap: 14px; padding: 14px 20px; margin: 0 0 18px 0;
    border-radius: 14px; border: 1px solid rgba(ACCENT_RGB, .28);
    background: linear-gradient(120deg, rgba(ACCENT_RGB, .16), rgba(0, 184, 148, .10)); }
.uj-logo { font-size: 32px; line-height: 1; }
.uj-title { font-size: 1.7rem; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; }
.uj-tag { font-size: .9rem; opacity: .75; margin-top: 3px; }
.uj-chip { margin-left: auto; font-size: .8rem; padding: 5px 12px; border-radius: 999px; white-space: nowrap;
    background: rgba(ACCENT_RGB, .14); border: 1px solid rgba(ACCENT_RGB, .32); }

/* 3. metric cards, tabs, tables */
[data-testid="stMetric"] { background: rgba(ACCENT_RGB, .06); border: 1px solid rgba(ACCENT_RGB, .20);
    border-radius: 12px; padding: 12px 16px; }
[data-testid="stMetricLabel"] p { font-size: .8rem; opacity: .75; }
[data-testid="stMetricValue"] { font-size: 1.55rem; font-weight: 700; }
[data-baseweb="tab-list"] { gap: 4px; overflow-x: auto; }
button[data-baseweb="tab"] { font-weight: 600; padding: 8px 14px; }
[data-testid="stDataFrame"] { border: 1px solid rgba(128, 128, 128, .25); border-radius: 10px; overflow: hidden; }
h2, h3 { letter-spacing: -.01em; }

/* 4. sidebar section titles: small and quiet */
[data-testid="stSidebar"] h2 { font-size: .85rem; text-transform: uppercase; letter-spacing: .07em; opacity: .7; }
</style>
"""


def _rgb(hex_colour: str) -> str:
    h = hex_colour.lstrip("#")
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def apply_style() -> None:
    st.markdown(_CSS.replace("ACCENT_RGB", _rgb(ACCENT)), unsafe_allow_html=True)


def page_header(dataset: str | None = None) -> None:
    chip = f'<div class="uj-chip">Dataset: <b>{html.escape(dataset)}</b></div>' if dataset else ""
    st.markdown(
        f'<div class="uj-header"><div class="uj-logo">🧶</div>'
        f'<div><div class="uj-title">UnJam</div><div class="uj-tag">{html.escape(TAGLINE)}</div></div>{chip}</div>',
        unsafe_allow_html=True,
    )
