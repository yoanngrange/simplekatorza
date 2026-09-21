#!/usr/bin/env python3
"""Temporary: test whether adding an explicit date_geq/date_leq bound
(in addition to datetime_geq/datetime_leq) changes results for the
Adaptive Groups dataset."""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

CF_API_TOKEN = os.environ["CF_API_TOKEN"]
CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
CF_SITE_TAG = os.environ["CF_SITE_TAG"]


def cf_graphql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
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


now = datetime.now(timezone.utc)
start = now - timedelta(days=3)

query = """
query($accountTag: string!, $siteTag: string!, $dstart: string!, $dend: string!, $dtstart: string!, $dtend: string!) {
  viewer {
    accounts(filter: {accountTag: $accountTag}) {
      rumPageloadEventsAdaptiveGroups(
        limit: 20
        filter: {
          siteTag: $siteTag
          date_geq: $dstart
          date_leq: $dend
          datetime_geq: $dtstart
          datetime_leq: $dtend
        }
      ) {
        count
        dimensions { date requestHost requestPath }
      }
    }
  }
}
"""
variables = {
    "accountTag": CF_ACCOUNT_ID,
    "siteTag": CF_SITE_TAG,
    "dstart": start.strftime("%Y-%m-%d"),
    "dend": now.strftime("%Y-%m-%d"),
    "dtstart": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "dtend": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
}
data = cf_graphql(query, variables)
print("DEBUG date+datetime bound query:", json.dumps(data))

# Also try date-only bound, no datetime filter at all
query2 = """
query($accountTag: string!, $siteTag: string!, $dstart: string!, $dend: string!) {
  viewer {
    accounts(filter: {accountTag: $accountTag}) {
      rumPageloadEventsAdaptiveGroups(
        limit: 20
        filter: {siteTag: $siteTag, date_geq: $dstart, date_leq: $dend}
      ) {
        count
        dimensions { date requestHost requestPath }
      }
    }
  }
}
"""
data2 = cf_graphql(query2, {
    "accountTag": CF_ACCOUNT_ID,
    "siteTag": CF_SITE_TAG,
    "dstart": start.strftime("%Y-%m-%d"),
    "dend": now.strftime("%Y-%m-%d"),
})
print("DEBUG date-only bound query:", json.dumps(data2))
