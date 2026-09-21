#!/usr/bin/env python3
"""Temporary: test whether millisecond-precision timestamps change the
result, and dump raw dimensioned rows for the last 6 hours with no
aggregation filter beyond siteTag + a short datetime window."""
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
start_ms = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
end_ms = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

query = """
query($accountTag: string!, $siteTag: string!, $start: string!, $end: string!) {
  viewer {
    accounts(filter: {accountTag: $accountTag}) {
      rumPageloadEventsAdaptiveGroups(
        limit: 20
        filter: {siteTag: $siteTag, datetime_geq: $start, datetime_leq: $end}
      ) {
        count
        dimensions { datetimeMinute siteTag requestHost requestPath }
      }
    }
  }
}
"""
data = cf_graphql(query, {"accountTag": CF_ACCOUNT_ID, "siteTag": CF_SITE_TAG, "start": start_ms, "end": end_ms})
print(f"DEBUG ms-precision last-6h query (start={start_ms} end={end_ms}):", json.dumps(data))

# Also try filtering by siteTag alone with a dimensions-only groupby, no explicit datetime bounds variable typing issue check: use siteTag_in
query2 = """
query($accountTag: string!, $siteTag: string!) {
  viewer {
    accounts(filter: {accountTag: $accountTag}) {
      rumPageloadEventsAdaptiveGroups(
        limit: 20
        filter: {siteTag_in: [$siteTag]}
        orderBy: [datetimeMinute_DESC]
      ) {
        count
        dimensions { datetimeMinute siteTag requestHost }
      }
    }
  }
}
"""
data2 = cf_graphql(query2, {"accountTag": CF_ACCOUNT_ID, "siteTag": CF_SITE_TAG})
print("DEBUG siteTag_in + orderBy datetimeMinute_DESC, no explicit date bound:", json.dumps(data2))
