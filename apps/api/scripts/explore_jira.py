"""
Jira Cloud API exploration script.
Prints real response shapes from your Jira instance so we can write
accurate connector code and Pydantic models.

Usage (Windows):
    set JIRA_BASE_URL=https://yoursite.atlassian.net
    set JIRA_EMAIL=you@example.com
    set JIRA_TOKEN=your_api_token
    uv run python apps/api/scripts/explore_jira.py
"""

import base64
import json
import os
import sys

try:
    import httpx
except ImportError:
    print("httpx not available -- run: uv add httpx")
    sys.exit(1)

BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
EMAIL    = os.environ.get("JIRA_EMAIL", "")
TOKEN    = os.environ.get("JIRA_TOKEN", "")

if not all([BASE_URL, EMAIL, TOKEN]):
    print("Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN environment variables.")
    sys.exit(1)

creds   = base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()
HEADERS = {"Authorization": f"Basic {creds}", "Accept": "application/json"}


def get(path: str, **params) -> dict | list:
    r = httpx.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=15)
    if not r.is_success:
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
        return {}
    return r.json()


def post(path: str, body: dict) -> dict:
    r = httpx.post(
        f"{BASE_URL}{path}",
        headers={**HEADERS, "Content-Type": "application/json"},
        json=body,
        timeout=15,
    )
    if not r.is_success:
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
        return {}
    return r.json()


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. Health check ───────────────────────────────────────────────────────────

section("1. GET /rest/api/3/myself  (health check)")
myself = get("/rest/api/3/myself")
print(json.dumps(myself, indent=2))

# Always use the token owner as fallback user for issue search
myself_account_id = myself.get("accountId", "")


# ── 2. Users ──────────────────────────────────────────────────────────────────

section("2. GET /rest/api/3/users/search?accountType=atlassian  (human users only)")
# Must filter accountType=atlassian to exclude bots/integrations
users_resp = get("/rest/api/3/users/search", maxResults=10, accountType="atlassian")
print(json.dumps(users_resp, indent=2))

users: list[dict] = []
if isinstance(users_resp, list):
    users = [u for u in users_resp if u.get("active")]
elif isinstance(users_resp, dict):
    users = [u for u in users_resp.get("values", []) if u.get("active")]

print(f"\n  Found {len(users)} active human users")
for u in users:
    email = u.get("emailAddress", "<hidden - privacy setting>")
    print(f"    accountId={u['accountId']}  email={email}  name={u.get('displayName')}")

# Fall back to token owner if no users returned
if not users and myself_account_id:
    print(f"  No users from search -- using token owner as test subject: {myself_account_id}")
    users = [myself]


# ── 3. Projects ───────────────────────────────────────────────────────────────

section("3. GET /rest/api/3/project/search  (all projects)")
projects_resp = get("/rest/api/3/project/search", maxResults=10, expand="description,lead")
print(json.dumps(projects_resp, indent=2))

projects_list = projects_resp.get("values", []) if isinstance(projects_resp, dict) else []
print(f"\n  Found {len(projects_list)} projects")
for p in projects_list:
    print(f"    key={p['key']}  name={p['name']}  type={p.get('projectTypeKey')}")


# ── 4. Issues -- statusCategory approach (pipeline-neutral) ──────────────────

section("4. Issue search -- statusCategory in (In Progress, Done)")

account_id = users[0]["accountId"] if users else myself_account_id
print(f"\n  Querying issues for accountId={account_id}")

# statusCategory works across ALL projects regardless of custom status names
# (HECHO, TESTING, DONE, RESUELTO, REVIEWING, etc. all map to these 3 categories)
body = {
    "jql": (
        f'assignee = "{account_id}" '
        'AND statusCategory in ("In Progress", "Done") '
        "ORDER BY updated DESC"
    ),
    "fields": [
        "summary",
        "status",       # includes statusCategory
        "components",   # skill signal
        "labels",       # skill signal
        "issuetype",
        "project",
        "created",
        "updated",
    ],
    "maxResults": 10,
}
issues_resp = post("/rest/api/3/search/jql", body)
print(json.dumps(issues_resp, indent=2))

print("\n  Status categories observed:")
for issue in issues_resp.get("issues", []):
    st = issue["fields"]["status"]
    cat = st.get("statusCategory", {})
    print(f"    status='{st['name']}'  category.key='{cat.get('key')}'  category.name='{cat.get('name')}'")

print("\n  Skill signals per issue (components + labels):")
for issue in issues_resp.get("issues", []):
    f = issue["fields"]
    components = [c["name"] for c in f.get("components", [])]
    labels = f.get("labels", [])
    print(f"    {issue['key']}: components={components}  labels={labels}")


# ── 5. Status categories reference ───────────────────────────────────────────

section("5. GET /rest/api/3/statuscategory  (canonical category list)")
cats = get("/rest/api/3/statuscategory")
print(json.dumps(cats, indent=2))


# ── 6. Components for each project ───────────────────────────────────────────

section("6. GET /rest/api/3/project/{key}/components  (skill inference source)")
for p in projects_list[:3]:
    key = p["key"]
    print(f"\n  Project {key}:")
    components = get(f"/rest/api/3/project/{key}/components")
    if isinstance(components, list) and components:
        for c in components:
            print(f"    component: {c.get('name')}")
    else:
        print("    (no components defined)")


# ── 7. All statuses for first project (confirms pipeline-neutral approach) ────

section("7. GET /rest/api/3/project/{key}/statuses  (custom status names per project)")
for p in projects_list[:3]:
    key = p["key"]
    print(f"\n  Project {key} statuses:")
    statuses_resp = get(f"/rest/api/3/project/{key}/statuses")
    if isinstance(statuses_resp, list):
        for issuetype in statuses_resp:
            for st in issuetype.get("statuses", []):
                cat = st.get("statusCategory", {})
                print(f"    '{st['name']}'  -> category='{cat.get('key')}'")

