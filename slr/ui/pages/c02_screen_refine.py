# slr/ui/pages/c02_screen_refine.py
import sys, os, io, csv, json, re
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Union

# allow absolute imports from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import streamlit as st

st.set_page_config(page_title="Conducting → Step 3: Selection & Refinement", layout="wide")

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def normalize_title(t: str) -> str:
    if not t:
        return ""
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def parse_year(dt_str: str) -> Optional[int]:
    if not dt_str:
        return None
    # arXiv: "2024-01-05T00:00:00Z"
    m = re.match(r"(\d{4})", dt_str)
    return int(m.group(1)) if m else None

def load_rows_from_csv(file) -> List[Dict]:
    text = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict] = []
    for r in reader:
        authors_str = r.get("authors", "") or ""
        authors = [a.strip() for a in authors_str.split(",") if a.strip()]
        rows.append({
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "summary": r.get("summary", ""),
            "published": r.get("published", ""),
            "updated": r.get("updated", ""),
            "authors": authors,
            "category": r.get("category", ""),
            "link": r.get("link", ""),
        })
    return rows

def rows_to_csv(rows: List[Dict], extra_cols: Optional[List[str]] = None) -> str:
    extra_cols = extra_cols or []
    cols = ["id", "title", "summary", "published", "updated", "authors", "category", "link"] + extra_cols
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols)
    for r in rows:
        authors = ", ".join(r.get("authors", []))
        base = [
            r.get("id", ""),
            (r.get("title", "") or "").replace("\n", " ").strip(),
            (r.get("summary", "") or "").replace("\n", " ").strip(),
            r.get("published", ""),
            r.get("updated", ""),
            authors,
            r.get("category", ""),
            r.get("link", ""),
        ]
        for c in extra_cols:
            base.append(r.get(c, ""))
        w.writerow(base)
    return out.getvalue()

# -------------------------------------------------------------------
# Planning artifacts (used automatically when available)
# -------------------------------------------------------------------
topic     = st.session_state.get("topic", "")
criteria  = st.session_state.get("criteria", {})           # from Planning Step 4
sources   = st.session_state.get("sources", {})            # from Planning Step 3
qcheck    = st.session_state.get("quality_checklist", {})  # from Planning Step 5 (optional)

if topic:
    st.caption("Current topic: **{}**".format(topic))

st.markdown("<h2 style='margin-top:20px;'>🧹 Conducting • Step 3: Study selection & refinement</h2>", unsafe_allow_html=True)
st.write("This step de-duplicates and applies basic automatic filters based on your planning artifacts. "
         "You can then download the **included** and **excluded (with reason)** sets and proceed to quality scoring & extraction.")

# -------------------------------------------------------------------
# Load raw studies (from session or upload)
# -------------------------------------------------------------------
rows: List[Dict] = st.session_state.get("gathered_rows", [])
st.markdown("### Load raw studies")
if rows:
    st.success("Loaded {} studies from session (Step 2).".format(len(rows)))
else:
    up = st.file_uploader("Upload raw studies (CSV or JSON) exported from Step 2", type=["csv", "json"])
    if up:
        try:
            if (getattr(up, "type", "") or "").endswith("/json") or up.name.lower().endswith(".json"):
                rows = json.loads(up.read().decode("utf-8"))
            else:
                rows = load_rows_from_csv(up)
            st.success("Loaded {} studies from upload.".format(len(rows)))
        except Exception as e:
            st.error("Failed to parse file: {}".format(e))

if not rows:
    st.info("No raw studies found. Go to **Conducting → Build & Gather (arXiv)** and fetch studies first.")
    st.stop()

# -------------------------------------------------------------------
# Deduplication options
# -------------------------------------------------------------------
st.markdown("### Deduplication")
dedup_key = st.selectbox("Choose deduplication key", ["normalized title", "id", "title + year"], index=0)
keep_rule = st.selectbox("When duplicates found, keep …", ["first occurrence", "latest by year"], index=0)

def perform_dedup(items: List[Dict]) -> Tuple[List[Dict], int]:
    seen: Dict[str, Dict] = {}
    drops = 0
    for r in items:
        if dedup_key == "id":
            k = (r.get("id", "") or "").strip().lower()
        elif dedup_key == "title + year":
            yr = parse_year(r.get("published", "")) or 0
            k = "{}::{}".format(normalize_title(r.get("title", "")), yr)
        else:
            k = normalize_title(r.get("title", ""))

        if k not in seen:
            seen[k] = r
        else:
            # decide replacement if "latest by year"
            if keep_rule == "latest by year":
                y_old = parse_year(seen[k].get("published", "")) or 0
                y_new = parse_year(r.get("published", "")) or 0
                if y_new > y_old:
                    seen[k] = r
            drops += 1
    return list(seen.values()), drops

deduped, dropped = perform_dedup(rows)
st.write("Deduped to **{}** (removed {}).".format(len(deduped), dropped))

# -------------------------------------------------------------------
# Automatic filters (basic, reproducible)
# -------------------------------------------------------------------
st.markdown("### Automatic filters (from planning)")

# Years window (from Step 4, but editable here)
years = criteria.get("years") or {}
try:
    y_from_default = int(years.get("from", 1900))
except Exception:
    y_from_default = 1900
try:
    y_to_default = int(years.get("to", datetime.now().year))
except Exception:
    y_to_default = datetime.now().year

# arXiv CS categories (from Step 3)
sel_cats: List[str] = []
if isinstance(sources, dict):
    # we used arxiv_categories in Step 3; fallbacks for naming variations
    raw = sources.get("arxiv_categories") or sources.get("categories") or []
    if isinstance(raw, list):
        sel_cats = [str(c).strip() for c in raw if str(c).strip()]

colf1, colf2 = st.columns(2)
with colf1:
    y_from = st.number_input("From year", min_value=1900, max_value=2100, value=y_from_default, step=1)
with colf2:
    y_to   = st.number_input("To year", min_value=1900, max_value=2100, value=y_to_default, step=1)

cat_explain = ", ".join(sel_cats) if sel_cats else "any cs.*"
st.caption("Category filter: **{}**".format(cat_explain))

def auto_screen(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    included: List[Dict] = []
    excluded: List[Dict] = []
    cat_allow: Optional[set] = set(sel_cats) if sel_cats else None

    for r in items:
        yr = parse_year(r.get("published", ""))
        cat = (r.get("category", "") or "").strip()

        # Year filter
        if yr is not None and (yr < int(y_from) or yr > int(y_to)):
            rr = dict(r)
            rr["reason"] = "year {} outside [{}-{}]".format(yr, y_from, y_to)
            excluded.append(rr)
            continue

        # Computer Science only
        if not cat.startswith("cs."):
            rr = dict(r)
            rr["reason"] = "non-CS category: {}".format(cat or "N/A")
            excluded.append(rr)
            continue

        # Enforce selected categories if provided
        if cat_allow and cat not in cat_allow:
            rr = dict(r)
            rr["reason"] = "category not in selected sources: {}".format(cat)
            excluded.append(rr)
            continue

        included.append(r)

    return included, excluded

inc, exc = auto_screen(deduped)
st.success("Auto-include: **{}**  |  Auto-exclude: **{}**".format(len(inc), len(exc)))

# -------------------------------------------------------------------
# Downloads
# -------------------------------------------------------------------
st.markdown("### Downloads")

# Save in session for next steps
st.session_state["screened_rows"] = inc
st.session_state["screened_excluded"] = exc

csv_inc = rows_to_csv(inc)
json_inc = json.dumps(inc, ensure_ascii=False, indent=2)

csv_exc = rows_to_csv(exc, extra_cols=["reason"])
json_exc = json.dumps(exc, ensure_ascii=False, indent=2)

c_d1, c_d2 = st.columns(2)
with c_d1:
    st.download_button("⬇️ Download INCLUDED (CSV)", data=csv_inc,
                       file_name="included_studies.csv", mime="text/csv", use_container_width=True)
    st.download_button("⬇️ Download INCLUDED (JSON)", data=json_inc,
                       file_name="included_studies.json", mime="application/json", use_container_width=True)
with c_d2:
    st.download_button("⬇️ Download EXCLUDED + reason (CSV)", data=csv_exc,
                       file_name="excluded_studies.csv", mime="text/csv", use_container_width=True)
    st.download_button("⬇️ Download EXCLUDED + reason (JSON)", data=json_exc,
                       file_name="excluded_studies.json", mime="application/json", use_container_width=True)

# -------------------------------------------------------------------
# Quality checklist template (optional)
# -------------------------------------------------------------------
st.markdown("---")
st.subheader("Quality scoring template (optional)")

if isinstance(qcheck, dict) and qcheck.get("questions"):
    qs = qcheck.get("questions", [])
    scheme = qcheck.get("scheme", "Y/N")  # "Y/N" or "Y/P/N"
    out = io.StringIO()
    w = csv.writer(out)
    hdr = ["id", "title"] + ["Q{}".format(i + 1) for i in range(len(qs))] + ["total_score"]
    w.writerow(hdr)
    for r in inc:
        w.writerow([r.get("id", ""), r.get("title", "")] + ["" for _ in qs] + [""])
    tmpl = out.getvalue()
    st.download_button(
        "⬇️ Download Quality Checklist Template (scheme: {})".format(scheme),
        data=tmpl,
        file_name="quality_scoring_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption("Fill the per-paper answers offline or in the next UI, then compute total_score. "
               "You can also integrate this with your Step-5 page.")
else:
    st.info("No quality checklist found from planning. You can still proceed, or go back to **Planning → Step 5** to define one.")
