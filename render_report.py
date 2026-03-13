#!/usr/bin/env python3
"""
render_report.py — Generate a self-contained HTML report from a summary.json file.

Usage:
    python3 render_report.py --summary-json <path/to/summary.json> --output-dir <dest/>
"""

import argparse
import csv
import json
import os
from pathlib import Path


VERDICT_COLOR = {"PASS": "#198754", "WARN": "#fd7e14", "FAIL": "#dc3545"}
VERDICT_BG = {"PASS": "#d1e7dd", "WARN": "#fff3cd", "FAIL": "#f8d7da"}


def render_base_indicators(bi: dict) -> str:
    rows = [
        ("Trip Coverage", f"{bi['trip_coverage_pct']}%"),
        ("Total Trips in Collection", bi["total_trips_in_collection"]),
        ("Excluded — no end_time (in-progress)", bi.get("trips_without_end_time", 0)),
        ("trip_agg — Total Rows", bi.get("trip_agg_total_rows", "—")),
        ("trip_agg — Unique Trips", bi.get("total_trips_in_trip_agg", "—")),
        ("trip_agg — Fragmented Trips (>1 segment)", bi.get("fragmented_trips_in_trip_agg", "—")),
        ("Missing from trip_agg", bi["missing_trip_count"]),
        ("Complete Trips (compared)", bi["complete_trips"]),
        ("Unbroken Unmatched", bi["unbroken_unmatched_count"]),
        ("Broken Unmatched", bi["broken_unmatched_count"]),
        ("Excluded — distance < 1 km", bi.get("short_trips_excluded", 0)),
        ("Excluded — partial after refetch", bi.get("partial_trips_after_refetch", 0)),
    ]
    rows_html = "".join(
        f"<tr><td style='padding:6px 12px;color:#555;border-bottom:1px solid #f0f0f0;'>{k}</td>"
        f"<td style='padding:6px 12px;font-weight:600;border-bottom:1px solid #f0f0f0;'>{v}</td></tr>"
        for k, v in rows
    )
    return f"""
<section>
  <h2 style="font-size:1.05rem;color:#333;border-bottom:2px solid #dee2e6;padding-bottom:6px;margin-top:32px;">Base Indicators</h2>
  <table style="border-collapse:collapse;width:100%;max-width:480px;">
    <tbody>{rows_html}</tbody>
  </table>
</section>"""


def render_api_health(ah: dict) -> str:
    rows = [
        ("Vehicles Fetched", ah.get("vehicles_fetched", 0)),
        ("Vehicle Pagination Aborted", "Yes ⚠" if ah.get("vehicle_pagination_aborted") else "No"),
        ("Vehicle Trip Fetch Failures", ah.get("vehicle_trip_fetch_failures", 0)),
        ("Trip Agg Pagination Aborted", "Yes ⚠" if ah.get("trip_agg_pagination_aborted") else "No"),
        ("Partial Trip Refetch Failures", ah.get("partial_trip_refetch_failures", 0)),
        (f"Alert Fetch Failures", f"{ah.get('alert_fetch_failures', 0)} / {ah.get('alert_fetch_total', 0)}"),
    ]
    rows_html = "".join(
        f"<tr><td style='padding:6px 12px;color:#555;border-bottom:1px solid #f0f0f0;'>{k}</td>"
        f"<td style='padding:6px 12px;font-weight:600;border-bottom:1px solid #f0f0f0;'>{v}</td></tr>"
        for k, v in rows
    )
    return f"""
<section>
  <h2 style="font-size:1.05rem;color:#333;border-bottom:2px solid #dee2e6;padding-bottom:6px;margin-top:32px;">API Health</h2>
  <table style="border-collapse:collapse;width:100%;max-width:480px;">
    <tbody>{rows_html}</tbody>
  </table>
</section>"""


def render_alerts(ds: dict) -> str:
    mismatched = ds.get("mismatched_alerts", [])
    passed = ds.get("passed_alerts", [])
    total_joined = ds.get("total_joined_trips_for_alert_comparison", 0)

    if mismatched:
        header = (
            "<tr style='background:#f8f9fa;'>"
            "<th style='text-align:left;padding:6px 12px;border-bottom:2px solid #dee2e6;color:#555;'>Alert</th>"
            "<th style='padding:6px 12px;border-bottom:2px solid #dee2e6;color:#555;text-align:center;'>Mismatches</th>"
            "<th style='padding:6px 12px;border-bottom:2px solid #dee2e6;color:#555;text-align:center;'>Mismatch %</th>"
            "</tr>"
        )
        rows_html = "".join(
            f"<tr>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #f0f0f0;'>{r['alert_name']}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #f0f0f0;text-align:center;'>{r['mismatch_count']}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #f0f0f0;text-align:center;'>{r['mismatch_pct']}%</td>"
            f"</tr>"
            for r in mismatched
        )
        table = f"""
  <p style="color:#555;font-size:0.9rem;margin-bottom:8px;">Compared across {total_joined} trips</p>
  <table style="border-collapse:collapse;width:100%;max-width:560px;">
    <thead>{header}</thead>
    <tbody>{rows_html}</tbody>
  </table>"""
    else:
        table = "<p style='color:#198754;'>&#x2713; No alert mismatches found.</p>"

    passed_section = ""
    if passed:
        passed_str = ", ".join(passed)
        passed_section = f"""
  <details style="margin-top:16px;">
    <summary style="cursor:pointer;color:#555;">Passed alerts ({len(passed)})</summary>
    <p style="margin-top:8px;color:#555;font-size:0.9rem;">{passed_str}</p>
  </details>"""

    return f"""
<section>
  <h2 style="font-size:1.05rem;color:#333;border-bottom:2px solid #dee2e6;padding-bottom:6px;margin-top:32px;">Alert Mismatches</h2>
  {table}
  {passed_section}
</section>"""


def _read_csv(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _trip_table(rows: list, columns: list, col_labels: list) -> str:
    if not rows:
        return ""
    th = "".join(
        f"<th style='padding:5px 10px;border-bottom:2px solid #dee2e6;color:#555;white-space:nowrap;'>{lbl}</th>"
        for lbl in col_labels
    )
    tr_rows = ""
    for i, row in enumerate(rows):
        bg = "#f8f9fa" if i % 2 == 0 else "#fff"
        cells = "".join(
            f"<td style='padding:5px 10px;border-bottom:1px solid #f0f0f0;font-size:0.85rem;'>{row.get(col, '') if row.get(col, '') != '' else '—'}</td>"
            for col in columns
        )
        tr_rows += f"<tr style='background:{bg};'>{cells}</tr>"
    return (
        f"<div style='overflow-x:auto;'>"
        f"<table style='border-collapse:collapse;width:100%;font-size:0.9rem;'>"
        f"<thead><tr style='background:#f8f9fa;'>{th}</tr></thead>"
        f"<tbody>{tr_rows}</tbody>"
        f"</table></div>"
    )


def render_step_timings(st: dict) -> str:
    if not st:
        return ""
    total = sum(st.values())
    rows_html = "".join(
        f"<tr>"
        f"<td style='padding:5px 12px;color:#555;border-bottom:1px solid #f0f0f0;font-family:monospace;'>{step}</td>"
        f"<td style='padding:5px 12px;border-bottom:1px solid #f0f0f0;text-align:right;'>{secs:.2f}s</td>"
        f"<td style='padding:5px 12px;border-bottom:1px solid #f0f0f0;'>"
        f"<div style='background:#e9ecef;border-radius:3px;height:10px;width:160px;display:inline-block;vertical-align:middle;'>"
        f"<div style='background:#0d6efd;border-radius:3px;height:10px;width:{min(secs/total*160, 160):.1f}px;'></div>"
        f"</div></td>"
        f"</tr>"
        for step, secs in st.items()
    )
    rows_html += (
        f"<tr style='font-weight:600;background:#f8f9fa;'>"
        f"<td style='padding:5px 12px;border-top:2px solid #dee2e6;'>total</td>"
        f"<td style='padding:5px 12px;border-top:2px solid #dee2e6;text-align:right;'>{total:.2f}s</td>"
        f"<td style='padding:5px 12px;border-top:2px solid #dee2e6;'></td>"
        f"</tr>"
    )
    return f"""
<section>
  <h2 style="font-size:1.05rem;color:#333;border-bottom:2px solid #dee2e6;padding-bottom:6px;margin-top:32px;">Step Timings</h2>
  <table style="border-collapse:collapse;width:100%;max-width:560px;">
    <tbody>{rows_html}</tbody>
  </table>
</section>"""


def render_unmatched_trips(report_dir: Path) -> str:
    unbroken = _read_csv(report_dir / "unbroken_unmatched_complete_trips_df.csv")
    broken = _read_csv(report_dir / "broken_unmatched_complete_trips_df.csv")
    missing = _read_csv(report_dir / "missing_trips_df.csv")

    if not unbroken and not broken and not missing:
        return ""

    UNMATCHED_COLS = ["trip_id", "vehicle_id", "counts", "total_distance", "distance", "total_fuel_consumed", "fuel_consumed"]
    UNMATCHED_LABELS = ["Trip ID", "Vehicle ID", "Segments", "Dist (agg) km", "Dist (trips) km", "Fuel (agg) L", "Fuel (trips) L"]
    MISSING_COLS = ["id", "vehicle_id", "start_time", "end_time", "distance"]
    MISSING_LABELS = ["Trip ID", "Vehicle ID", "Start Time", "End Time", "Distance (km)"]

    sections = ""

    if unbroken:
        table = _trip_table(unbroken, UNMATCHED_COLS, UNMATCHED_LABELS)
        sections += f"""
  <details style="margin-top:12px;">
    <summary style="cursor:pointer;font-weight:600;color:#333;padding:6px 0;">
      Unbroken Unmatched ({len(unbroken)})
      <span style="font-weight:400;font-size:0.85rem;color:#888;margin-left:8px;">single-segment trips with metric mismatch</span>
    </summary>
    <div style="margin-top:8px;">{table}</div>
  </details>"""

    if broken:
        table = _trip_table(broken, UNMATCHED_COLS, UNMATCHED_LABELS)
        sections += f"""
  <details style="margin-top:12px;">
    <summary style="cursor:pointer;font-weight:600;color:#333;padding:6px 0;">
      Broken Unmatched ({len(broken)})
      <span style="font-weight:400;font-size:0.85rem;color:#888;margin-left:8px;">multi-segment trips with metric mismatch</span>
    </summary>
    <div style="margin-top:8px;">{table}</div>
  </details>"""

    if missing:
        table = _trip_table(missing, MISSING_COLS, MISSING_LABELS)
        sections += f"""
  <details style="margin-top:12px;">
    <summary style="cursor:pointer;font-weight:600;color:#333;padding:6px 0;">
      Missing Trips ({len(missing)})
      <span style="font-weight:400;font-size:0.85rem;color:#888;margin-left:8px;">in trips collection but absent from trip_agg</span>
    </summary>
    <div style="margin-top:8px;">{table}</div>
  </details>"""

    return f"""
<section>
  <h2 style="font-size:1.05rem;color:#333;border-bottom:2px solid #dee2e6;padding-bottom:6px;margin-top:32px;">Unmatched Trip Details</h2>
  {sections}
</section>"""


def render_csv_previews(report_dir: Path) -> str:
    sections = ""

    if (report_dir / "run.log").exists():
        sections += """
  <details style="margin-bottom:16px;" id="log-details">
    <summary style="cursor:pointer;font-size:0.9rem;font-weight:600;color:#333;padding:4px 0;">&#x1F4CB; Execution Log</summary>
    <div style="margin-top:8px;">
      <pre id="log-content" style="background:#1e1e1e;color:#d4d4d4;padding:14px 16px;border-radius:6px;font-size:0.73rem;line-height:1.5;max-height:520px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;">Loading\u2026</pre>
    </div>
  </details>
  <script>
    (function() {
      var det = document.getElementById('log-details');
      var pre = document.getElementById('log-content');
      var loaded = false;
      det.addEventListener('toggle', function() {
        if (det.open && !loaded) {
          loaded = true;
          fetch('run.log').then(function(r) { return r.text(); }).then(function(t) {
            pre.textContent = t;
          }).catch(function() {
            pre.textContent = 'Failed to load log.';
          });
        }
      });
    })();
  </script>"""

    csvs = sorted(report_dir.glob("*.csv"))
    for csv_path in csvs:
        rows = _read_csv(csv_path)
        if not rows:
            sections += f"""
  <details style="margin-top:8px;">
    <summary style="cursor:pointer;font-weight:600;color:#333;padding:4px 0;font-size:0.95rem;">
      {csv_path.stem}
      <span style="font-weight:400;font-size:0.82rem;color:#aaa;margin-left:8px;">(empty)</span>
    </summary>
  </details>"""
            continue
        cols = list(rows[0].keys())
        th = "".join(
            f"<th style='padding:4px 8px;border-bottom:2px solid #dee2e6;color:#555;white-space:nowrap;font-size:0.8rem;'>{c}</th>"
            for c in cols
        )
        tr_rows = ""
        for i, row in enumerate(rows[:200]):
            bg = "#f8f9fa" if i % 2 == 0 else "#fff"
            cells = "".join(
                f"<td style='padding:4px 8px;border-bottom:1px solid #f0f0f0;font-size:0.8rem;white-space:nowrap;'>{row.get(c, '') if row.get(c, '') != '' else '—'}</td>"
                for c in cols
            )
            tr_rows += f"<tr style='background:{bg};'>{cells}</tr>"
        truncation = f"<p style='color:#888;font-size:0.8rem;margin-top:4px;'>Showing 200 of {len(rows)} rows</p>" if len(rows) > 200 else ""
        table = (
            f"<div style='overflow-x:auto;margin-top:6px;'>"
            f"<table style='border-collapse:collapse;width:100%;font-size:0.85rem;'>"
            f"<thead><tr style='background:#f8f9fa;'>{th}</tr></thead>"
            f"<tbody>{tr_rows}</tbody>"
            f"</table></div>{truncation}"
        )
        sections += f"""
  <details style="margin-top:8px;">
    <summary style="cursor:pointer;font-weight:600;color:#333;padding:4px 0;font-size:0.95rem;">
      {csv_path.stem}
      <span style="font-weight:400;font-size:0.82rem;color:#888;margin-left:8px;">{len(rows)} rows</span>
      &nbsp;<a href="{csv_path.name}" style="font-size:0.8rem;font-weight:400;" onclick="event.stopPropagation();">download</a>
    </summary>
    {table}
  </details>"""

    if not sections:
        return ""

    return f"""
<section style="margin-top:32px;border-top:1px solid #dee2e6;padding-top:16px;">
  <h2 style="font-size:1.05rem;color:#333;border-bottom:2px solid #dee2e6;padding-bottom:6px;margin-top:0;">Data Files</h2>
  {sections}
</section>"""


def build_report(summary_json_path: str) -> str:
    with open(summary_json_path, encoding="utf-8") as f:
        s = json.load(f)

    bi = s["base_indicators"]
    ds = s["detailed_summary"]
    ah = s.get("api_health", {})
    dr = s["date_range"]
    verdict = bi["verdict"]
    color = VERDICT_COLOR.get(verdict, "#6c757d")
    bg = VERDICT_BG.get(verdict, "#e2e3e5")
    report_dir = Path(summary_json_path).parent

    account_name = s.get("account_name")
    account_display = (
        f"{account_name} <span style='color:#888;font-size:0.9em;'>({s['account_id']})</span>"
        if account_name else s["account_id"]
    )

    header = f"""
<div style="display:flex;align-items:center;gap:16px;margin-bottom:24px;flex-wrap:wrap;">
  <div style="font-size:1rem;color:#555;line-height:1.7;">
    <strong>Account:</strong> {account_display}<br>
    <strong>Period:</strong> {dr['start']} &ndash; {dr['end']}<br>
    <strong>Run:</strong> {s['run_timestamp']}
  </div>
  <div style="margin-left:auto;background:{color};color:white;
              padding:10px 24px;border-radius:6px;font-size:1.4rem;font-weight:bold;">
    {verdict}
  </div>
</div>"""

    body = (
        header
        + render_base_indicators(bi)
        + render_api_health(ah)
        + render_step_timings(s.get("step_timings", {}))
        + render_unmatched_trips(report_dir)
        + render_alerts(ds)
        + render_csv_previews(report_dir)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trip Aggregation Report — {account_name or s['account_id']} — {dr['start'][:10]}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      max-width: 760px;
      margin: 40px auto;
      padding: 0 20px;
      color: #212529;
    }}
    h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
    a {{ color: #0d6efd; }}
    table {{ font-size: 0.95rem; }}
  </style>
</head>
<body>
  <h1>Trip Aggregation Report</h1>
  {body}
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-json", required=True, help="Path to summary.json")
    parser.add_argument("--output-dir", required=True, help="Directory to write report.html")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    html = build_report(args.summary_json)
    out_path = os.path.join(args.output_dir, "report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to: {out_path}")


if __name__ == "__main__":
    main()
