#!/usr/bin/env python3
"""Temporary: introspect Cloudflare's GraphQL schema to find the exact
input field names for the RUM Web Analytics dataset filter, instead of
guessing against docs/examples."""
import json
import os
import urllib.request

CF_API_TOKEN = os.environ["CF_API_TOKEN"]


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


# Step 1: find every schema type whose name mentions RumPageload or its filter
schema_query = """
query {
  __schema {
    types { name }
  }
}
"""
data = cf_graphql(schema_query)
names = [t["name"] for t in data["data"]["__schema"]["types"]]
matches = [n for n in names if "rumpageload" in n.lower()]
print("DEBUG matching type names:", json.dumps(matches))

# Step 2: introspect each matching type's fields/inputFields
for name in matches:
    type_query = """
    query($name: String!) {
      __type(name: $name) {
        name
        kind
        fields { name }
        inputFields { name type { name kind ofType { name kind } } }
      }
    }
    """
    tdata = cf_graphql(type_query, {"name": name})
    print(f"DEBUG type detail for {name}:", json.dumps(tdata))
