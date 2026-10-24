"""Run this once after installing: python check_setup.py"""
import importlib
import sys

print(f"Python {sys.version.split()[0]}")
ok = sys.version_info >= (3, 10)
if not ok:
    print("  -> Please use Python 3.10 or newer (python.org/downloads)")

for pkg in ("pandas", "numpy", "streamlit", "plotly"):
    try:
        mod = importlib.import_module(pkg)
        print(f"  [ok] {pkg} {getattr(mod, '__version__', '')}")
    except ImportError:
        ok = False
        print(f"  [missing] {pkg}  -> run: pip install -r requirements.txt")

try:
    from unjam.config import DATA_DIR, gemini_key, list_local_logs
    logs = list_local_logs()
    if logs:
        print(f"  [ok] event log found: {logs[0].name}")
    else:
        print(f"  [todo] no event log yet. Put BPI_Challenge_2012.xes.gz in: {DATA_DIR}")
    print("  [ok] Gemini key found (optional)" if gemini_key() else "  [info] no Gemini key (optional: findings are then written by rules)")
except Exception as exc:  # noqa: BLE001
    ok = False
    print(f"  [error] could not import unjam: {exc}")

print("\nSetup looks good. Start the app with:  python -m streamlit run app.py" if ok else "\nFix the items above, then run this file again.")
