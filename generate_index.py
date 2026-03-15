#!/usr/bin/env python3
"""
generate_index.py — Scans the GitHub Pages repo directory tree and regenerates index.html.

Usage:
    python3 generate_index.py --repo-dir /path/to/pages-repo
"""

import argparse
import json
import os
from pathlib import Path


VERDICT_COLOR = {"PASS": "#198754", "WARN": "#fd7e14", "FAIL": "#dc3545"}
VERDICT_BG = {"PASS": "#d1e7dd", "WARN": "#fff3cd", "FAIL": "#f8d7da"}


def read_summary_metrics(account_dir: Path) -> dict:
    summary = account_dir / "summary.json"
    if summary.exists():
        try:
            with open(summary) as f:
                data = json.load(f)
            bi = data.get("base_indicators", {})
            ds = data.get("detailed_summary", {})
            mismatched = ds.get("mismatched_alerts", [])
            passed = ds.get("passed_alerts", [])
            total_alert_types = len(mismatched) + len(passed)
            total_joined = ds.get("total_joined_trips_for_alert_comparison", 0)
            total_mismatch_count = sum(a.get("mismatch_count", 0) for a in mismatched)
            total_possible = total_joined * total_alert_types
            alert_mismatch_pct = (
                f"{round(total_mismatch_count / total_possible * 100, 1)}%"
                if total_possible else "—"
            )
            return {
                "verdict": bi.get("verdict", "?"),
                "unbroken_unmatched": bi.get("unbroken_unmatched_count", "—"),
                "broken_unmatched": bi.get("broken_unmatched_count", "—"),
                "missing_trips": bi.get("missing_trip_count", "—"),
                "alert_mismatch_pct": alert_mismatch_pct,
            }
        except Exception:
            pass
    return {"verdict": "?", "unbroken_unmatched": "—", "broken_unmatched": "—", "missing_trips": "—", "alert_mismatch_pct": "—"}


def build_index(repo_dir: Path) -> str:
    # Collect all report.html paths: <date>/<account_id>/report.html
    entries: dict[str, list[tuple[str, str, str]]] = {}  # date -> [(account_id, verdict, url)]

    for report_html in sorted(repo_dir.glob("*/*/report.html"), reverse=True):
        account_id = report_html.parent.name
        date_str = report_html.parent.parent.name
        # Skip non-date directories (e.g. root files)
        if not date_str[0].isdigit():
            continue
        metrics = read_summary_metrics(report_html.parent)
        url = f"{date_str}/{account_id}/report.html"
        entries.setdefault(date_str, []).append((account_id, metrics, url))

    if not entries:
        date_sections = "<p style='color:#888;'>No reports published yet.</p>"
    else:
        sections = []
        for date_str in sorted(entries.keys(), reverse=True):
            account_rows = ""
            for account_id, metrics, url in sorted(entries[date_str], key=lambda x: x[0]):
                verdict = metrics["verdict"]
                unbroken = metrics["unbroken_unmatched"]
                broken = metrics["broken_unmatched"]
                missing = metrics["missing_trips"]
                alert_pct = metrics["alert_mismatch_pct"]
                color = VERDICT_COLOR.get(verdict, "#6c757d")
                bg = VERDICT_BG.get(verdict, "#e2e3e5")
                unbroken_style = "color:#dc3545;font-weight:600;" if unbroken not in ("—", 0, "0") else "color:#555;"
                broken_style = "color:#dc3545;font-weight:600;" if broken not in ("—", 0, "0") else "color:#555;"
                missing_style = "color:#dc3545;font-weight:600;" if missing not in ("—", 0, "0") else "color:#555;"
                alert_style = "color:#dc3545;font-weight:600;" if alert_pct not in ("—", "0.0%", "0%") else "color:#555;"
                account_rows += f"""
                <tr>
                  <td style="padding:8px 12px;">
                    <a href="{url}" style="text-decoration:none;color:#0d6efd;font-weight:500;">{account_id}</a>
                  </td>
                  <td style="padding:8px 12px;">
                    <span style="background:{bg};color:{color};padding:3px 10px;border-radius:4px;font-weight:600;font-size:0.85rem;">{verdict}</span>
                  </td>
                  <td style="padding:8px 12px;text-align:center;{missing_style}">{missing}</td>
                  <td style="padding:8px 12px;text-align:center;{unbroken_style}">{unbroken}</td>
                  <td style="padding:8px 12px;text-align:center;{broken_style}">{broken}</td>
                  <td style="padding:8px 12px;text-align:center;{alert_style}">{alert_pct}</td>
                  <td style="padding:8px 12px;">
                    <button onclick="openLog('{date_str}/{account_id}/run.log','{date_str} / {account_id}')" style="background:none;border:none;color:#6c757d;font-size:0.85rem;cursor:pointer;padding:0;text-decoration:underline;">log</button>
                  </td>
                </tr>"""

            sections.append(f"""
            <div style="margin-bottom:32px;">
              <h2 style="font-size:1.1rem;color:#333;border-bottom:2px solid #dee2e6;padding-bottom:6px;">{date_str}</h2>
              <table style="border-collapse:collapse;width:100%;max-width:1060px;">
                <thead>
                  <tr style="background:#f8f9fa;">
                    <th style="text-align:left;padding:8px 12px;color:#555;">Account</th>
                    <th style="text-align:left;padding:8px 12px;color:#555;">Verdict</th>
                    <th style="text-align:center;padding:8px 12px;color:#555;">Missing Trips</th>
                    <th style="text-align:center;padding:8px 12px;color:#555;">Unbroken Unmatched</th>
                    <th style="text-align:center;padding:8px 12px;color:#555;">Broken Unmatched</th>
                    <th style="text-align:center;padding:8px 12px;color:#555;">Alert Types Mismatched</th>
                    <th style="padding:8px 12px;color:#555;"></th>
                  </tr>
                </thead>
                <tbody>{account_rows}</tbody>
              </table>
            </div>""")
        date_sections = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trip Aggregation Reports</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 1100px; margin: 40px auto; padding: 0 20px; color: #212529; }}
    a {{ color: #0d6efd; }}
  </style>
</head>
<body>
  <h1 style="font-size:1.6rem;margin-bottom:8px;">Trip Aggregation Reports</h1>
  <p style="color:#888;margin-bottom:32px;">Daily data quality reports — auto-generated by cron.</p>
  {date_sections}

  <dialog id="log-modal" style="width:92%;max-width:960px;border:none;border-radius:8px;padding:0;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid #dee2e6;background:#f8f9fa;border-radius:8px 8px 0 0;">
      <span id="log-modal-title" style="font-weight:600;font-size:0.9rem;color:#333;"></span>
      <button onclick="document.getElementById('log-modal').close()" style="background:none;border:none;font-size:1.1rem;cursor:pointer;color:#666;line-height:1;">&#x2715;</button>
    </div>
    <pre id="log-modal-content" style="background:#1e1e1e;color:#d4d4d4;padding:16px;margin:0;font-size:0.73rem;line-height:1.5;max-height:72vh;overflow-y:auto;white-space:pre-wrap;word-break:break-all;border-radius:0 0 8px 8px;">Loading\u2026</pre>
  </dialog>
  <script>
    function openLog(path, title) {{
      var modal = document.getElementById('log-modal');
      var pre   = document.getElementById('log-modal-content');
      document.getElementById('log-modal-title').textContent = title;
      pre.textContent = 'Loading\u2026';
      modal.showModal();
      fetch(path).then(function(r) {{ return r.text(); }}).then(function(t) {{
        pre.textContent = t;
      }}).catch(function() {{
        pre.textContent = 'Failed to load log.';
      }});
    }}
    document.getElementById('log-modal').addEventListener('click', function(e) {{
      if (e.target === this) this.close();
    }});
  </script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", required=True, help="Path to the GitHub Pages repo root")
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir)
    index_path = repo_dir / "index.html"
    index_path.write_text(build_index(repo_dir), encoding="utf-8")
    print(f"index.html written to: {index_path}")


if __name__ == "__main__":
    main()
