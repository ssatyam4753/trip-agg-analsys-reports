#!/usr/bin/env python3
"""
render_report.py — Generate a self-contained HTML report from a summary.json file.

Usage:
    python3 render_report.py --summary-json <path/to/summary.json> --output-dir <dest/>
"""

import argparse
import json
import os
from pathlib import Path


VERDICT_COLOR = {"PASS": "#198754", "WARN": "#fd7e14", "FAIL": "#dc3545"}
VERDICT_BG = {"PASS": "#d1e7dd", "WARN": "#fff3cd", "FAIL": "#f8d7da"}


def render_base_indicators(bi: dict) -> str:
    rows = [
        ("Trip Coverage", f"{bi['trip_coverage_pct']}%"),
        ("Total Trips in Collection", bi["total_trips_in_collection"]),
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


def render_files(report_dir: Path) -> str:
    links = []
    if (report_dir / "run.log").exists():
        links.append('<a href="run.log">&#x1F4CB; Execution Log</a>')
    csvs = sorted(report_dir.glob("*.csv"))
    if csvs:
        csv_links = " &nbsp;|&nbsp; ".join(
            f'<a href="{c.name}">{c.stem}</a>' for c in csvs
        )
        links.append(f"&#x1F4C2; CSVs: {csv_links}")

    if not links:
        return ""

    return f"""
<section style="margin-top:32px;padding-top:16px;border-top:1px solid #dee2e6;font-size:0.9rem;">
  {"<br>".join(links)}
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
        + render_alerts(ds)
        + render_files(report_dir)
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
