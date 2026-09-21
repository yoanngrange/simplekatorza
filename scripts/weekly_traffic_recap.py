#!/usr/bin/env python3
"""Fetch last 7 days of Cloudflare Web Analytics for simplekatorza.com and
email a short recap via Resend. Runs unattended from GitHub Actions, so any
failure (Cloudflare auth/schema issue, Resend error) is emailed as plain text
instead of failing silently.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

CF_API_TOKEN = os.environ["CF_API_TOKEN"]
CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
CF_SITE_TAG = os.environ["CF_SITE_TAG"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
REPORT_EMAIL_TO = os.environ.get("REPORT_EMAIL_TO", "yoann.grange@gmail.com")
REPORT_EMAIL_FROM = os.environ.get("REPORT_EMAIL_FROM", "Simplekatorza Reports <reports@basic-map.com>")
SITE_NAME = os.environ.get("SITE_NAME", "simplekatorza.com")


def cf_graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def week_bounds(weeks_ago):
    now = datetime.now(timezone.utc)
    end = now - timedelta(days=7 * weeks_ago)
    start = end - timedelta(days=7)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.strftime(fmt), end.strftime(fmt)


def fetch_pageviews(start, end):
    query = """
    query($accountTag: string!, $siteTag: string!, $start: string!, $end: string!) {
      viewer {
        accounts(filter: {accountTag: $accountTag}) {
          total: rumPageloadEventsAdaptiveGroups(
            limit: 1
            filter: {siteTag: $siteTag, datetime_geq: $start, datetime_leq: $end}
          ) {
            count
          }
          byPage: rumPageloadEventsAdaptiveGroups(
            limit: 10
            filter: {siteTag: $siteTag, datetime_geq: $start, datetime_leq: $end}
            orderBy: [count_DESC]
          ) {
            count
            dimensions { requestPath }
          }
        }
      }
    }
    """
    variables = {
        "accountTag": CF_ACCOUNT_ID,
        "siteTag": CF_SITE_TAG,
        "start": start,
        "end": end,
    }
    data = cf_graphql(query, variables)
    if data.get("errors"):
        raise RuntimeError(f"Cloudflare GraphQL error: {data['errors']}")
    accounts = data["data"]["viewer"]["accounts"]
    if not accounts:
        raise RuntimeError("No Cloudflare account matched accountTag")
    total = sum(g["count"] for g in accounts[0]["total"]) if accounts[0]["total"] else 0
    top_pages = [
        (g["dimensions"]["requestPath"], g["count"]) for g in accounts[0].get("byPage", [])
    ]
    return total, top_pages


def send_email(subject, text_body):
    body = json.dumps(
        {
            "from": REPORT_EMAIL_FROM,
            "to": [REPORT_EMAIL_TO],
            "subject": subject,
            "text": text_body,
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=body,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend error {e.code}: {e.read().decode(errors='replace')}") from e


def build_recap_body():
    this_start, this_end = week_bounds(0)
    total_this_week, top_pages = fetch_pageviews(this_start, this_end)

    lines = [f"{SITE_NAME} — last 7 days", "", f"Total pageviews: {total_this_week}"]

    try:
        prev_start, prev_end = week_bounds(1)
        total_prev_week, _ = fetch_pageviews(prev_start, prev_end)
        if total_prev_week:
            delta = total_this_week - total_prev_week
            pct = round(100 * delta / total_prev_week)
            sign = "+" if delta >= 0 else ""
            lines.append(f"Vs previous week: {sign}{delta} ({sign}{pct}%)")
    except Exception:
        pass  # week-over-week comparison is a nice-to-have, not worth failing the run over

    if len(top_pages) > 1:
        lines.append("")
        lines.append("Top pages:")
        for path, count in top_pages[:5]:
            lines.append(f"  {path or '/'} — {count}")

    return "\n".join(lines)


def main():
    subject = f"{SITE_NAME} — weekly traffic recap"
    try:
        body = build_recap_body()
    except Exception as exc:
        body = (
            f"Couldn't pull this week's Cloudflare Web Analytics data for {SITE_NAME}.\n\n"
            f"Error: {exc}\n\n"
            "This is a Cloudflare API call failure (auth, schema, or network) inside the "
            "GitHub Actions runner — check the workflow run log for the full traceback."
        )
        send_email(subject, body)
        print(body, file=sys.stderr)
        sys.exit(1)

    send_email(subject, body)
    print(body)


if __name__ == "__main__":
    main()
