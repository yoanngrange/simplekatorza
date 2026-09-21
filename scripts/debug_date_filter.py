#!/usr/bin/env python3
"""Temporary: list every Cloudflare account this token can see, and for
each one, check whether our known siteTag has any RUM data at all,
using a very wide (but quota-legal) date_geq/date_leq bound."""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

CF_API_TOKEN = os.environ["CF_API_TOKEN"]
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


# List every account visible to this token
accounts_query = """
query {
  viewer {
    accounts {
      accountTag
    }
  }
}
"""
data = cf_graphql(accounts_query)
print("DEBUG visible accounts:", json.dumps(data))

accounts = [a["accountTag"] for a in data.get("data", {}).get("viewer", {}).get("accounts", [])]

now = datetime.now(timezone.utc)
start = now - timedelta(days=3)

for acct in accounts:
    query = """
    query($accountTag: string!, $siteTag: string!, $dstart: string!, $dend: string!) {
      viewer {
        accounts(filter: {accountTag: $accountTag}) {
          rumPageloadEventsAdaptiveGroups(
            limit: 5
            filter: {siteTag: $siteTag, date_geq: $dstart, date_leq: $dend}
          ) {
            count
            dimensions { date requestHost }
          }
        }
      }
    }
    """
    variables = {
        "accountTag": acct,
        "siteTag": CF_SITE_TAG,
        "dstart": start.strftime("%Y-%m-%d"),
        "dend": now.strftime("%Y-%m-%d"),
    }
    result = cf_graphql(query, variables)
    print(f"DEBUG account {acct} siteTag lookup:", json.dumps(result))
