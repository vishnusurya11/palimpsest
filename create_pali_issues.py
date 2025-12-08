import os
import requests
import yaml
from dotenv import load_dotenv

# Load .env file from current directory
load_dotenv()

# === CONFIG ===
OWNER = "vishnusurya11"
REPO = "palimpsest"
EPIC_LABEL = "Epics"  # label added to all PALI-E* issues
PALI_CONFIG_PATH = "config/pali_items.yaml"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise SystemExit(
        "GITHUB_TOKEN environment variable not set. "
        "Set GITHUB_TOKEN in your .env file."
    )

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

ISSUES_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/issues"


# ---------- Config helpers ----------

def load_pali_items():
    if not os.path.exists(PALI_CONFIG_PATH):
        raise SystemExit(f"Config file not found: {PALI_CONFIG_PATH}")

    with open(PALI_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    items = data.get("items", [])
    normalized = []
    for item in items:
        try:
            pali_id = item["id"].strip()
            phase = item["phase"].strip()
            priority = item["priority"].strip()
            title = item["title"].strip()
            description = item.get("description", "").strip()
        except KeyError as e:
            raise SystemExit(f"Missing key in config for item: {item} ({e})")

        normalized.append(
            {
                "id": pali_id,
                "phase": phase,
                "priority": priority,
                "title": title,
                "description": description,
            }
        )
    return normalized


def desired_issue_title(pali_id: str, title: str) -> str:
    # Title format: [PALI-E1] Codex Ingestion Backbone
    return f"[{pali_id}] {title}"


def desired_issue_body(
    pali_id: str,
    phase: str,
    priority: str,
    title: str,
    description: str,
) -> str:
    desc_block = description or "TODO: add a clear goal / description for this item."

    return f"""# {pali_id} – {title}

**ID:** {pali_id}  
**Phase:** {phase}  
**Priority:** {priority}  

**Goal / Description**  
{desc_block}

---

This issue is managed by a script from `config/pali_items.yaml`.  
Update that file and rerun the script to change title/body/priority.
"""


# ---------- Existing issue discovery ----------

def extract_pali_id_from_title(title: str) -> str | None:
    """
    Support both formats:

    - "[PALI-E1] Codex Ingestion Backbone"  -> "PALI-E1"
    - "PALI-E1 – Codex Ingestion Backbone"  -> "PALI-E1"  (old style)
    """
    title = title.strip()

    # New format: [PALI-E1] ...
    if title.startswith("[PALI-E"):
        closing = title.find("]")
        if closing != -1:
            inner = title[1:closing].strip()
            if inner.startswith("PALI-E"):
                return inner

    # Old format fallback: PALI-E1 – ...
    if title.startswith("PALI-E"):
        first_token = title.split(" ")[0]
        if first_token.startswith("PALI-E"):
            return first_token

    return None


def get_existing_pali_map():
    """
    Fetch all issues (open+closed) and return a mapping:
      { "PALI-E1": issue_dict, ... }

    Currently we only track PALI-E* (epic-level items).
    """
    existing = {}
    page = 1

    while True:
        params = {
            "state": "all",
            "per_page": 100,
            "page": page,
        }
        resp = requests.get(ISSUES_URL, headers=HEADERS, params=params)
        if resp.status_code != 200:
            raise SystemExit(f"Failed to list issues: {resp.status_code} {resp.text}")

        issues = resp.json()
        if not issues:
            break

        for issue in issues:
            if "pull_request" in issue:
                continue

            title = issue.get("title", "")
            pali_id = extract_pali_id_from_title(title)
            # Only track PALI-E* for now
            if pali_id and pali_id.startswith("PALI-E") and pali_id not in existing:
                existing[pali_id] = issue

        page += 1

    return existing


# ---------- Labels / priority ----------

def compute_labels(current_labels: list[str], priority: str) -> list[str]:
    """
    Ensure Epics label + exactly one of P0/P1/P2.
    Don't touch any other labels.
    """
    priority_label = priority  # e.g. "P0"
    priority_set = {"P0", "P1", "P2"}

    new_labels = list(current_labels)

    # Ensure Epics label
    if EPIC_LABEL not in new_labels:
        new_labels.append(EPIC_LABEL)

    # Remove any existing priority labels
    new_labels = [l for l in new_labels if l not in priority_set]

    # Add desired priority
    if priority_label not in new_labels:
        new_labels.append(priority_label)

    return new_labels


# ---------- Create / Update ----------

def create_pali_item(item: dict):
    pali_id = item["id"]
    phase = item["phase"]
    priority = item["priority"]
    title = item["title"]
    description = item["description"]

    # Only manage PALI-E* in this script
    if not pali_id.startswith("PALI-E"):
        print(f"[SKIP-NON-E] {pali_id}: not an epic, ignored by this script")
        return

    issue_title = desired_issue_title(pali_id, title)
    body = desired_issue_body(pali_id, phase, priority, title, description)
    labels = compute_labels([], priority)

    payload = {
        "title": issue_title,
        "body": body,
        "labels": labels,
    }

    resp = requests.post(ISSUES_URL, headers=HEADERS, json=payload)
    if resp.status_code == 201:
        data = resp.json()
        print(f"[CREATE] {pali_id}: #{data['number']} → {data['html_url']}")
    else:
        print(f"[CREATE-FAILED] {pali_id}: {resp.status_code}")
        print(resp.text)


def update_pali_item(issue: dict, item: dict):
    pali_id = item["id"]
    phase = item["phase"]
    priority = item["priority"]
    title = item["title"]
    description = item["description"]

    issue_number = issue["number"]
    current_title = issue.get("title", "")
    current_body = issue.get("body", "") or ""
    current_labels = [lbl["name"] for lbl in issue.get("labels", [])]

    new_title = desired_issue_title(pali_id, title)
    new_body = desired_issue_body(pali_id, phase, priority, title, description)
    new_labels = compute_labels(current_labels, priority)

    needs_update = False
    if current_title != new_title or current_body != new_body:
        needs_update = True
    if set(current_labels) != set(new_labels):
        needs_update = True

    if not needs_update:
        print(f"[SKIP] {pali_id}: no changes")
        return

    payload = {
        "title": new_title,
        "body": new_body,
        "labels": new_labels,
    }

    url = f"{ISSUES_URL}/{issue_number}"
    resp = requests.patch(url, headers=HEADERS, json=payload)
    if resp.status_code == 200:
        print(f"[UPDATE] {pali_id}: issue #{issue_number} updated")
    else:
        print(f"[UPDATE-FAILED] {pali_id}: {resp.status_code}")
        print(resp.text)


def main():
    pali_items = load_pali_items()
    existing_map = get_existing_pali_map()
    existing_ids = sorted(existing_map.keys())
    print("Existing PALI-E* items found:", ", ".join(existing_ids) or "none")

    for item in pali_items:
        pali_id = item["id"]

        # Only manage epics in this script for now
        if not pali_id.startswith("PALI-E"):
            print(f"[SKIP-NON-E] {pali_id}: not an epic, ignored by this script")
            continue

        issue = existing_map.get(pali_id)
        if issue is None:
            create_pali_item(item)
        else:
            update_pali_item(issue, item)


if __name__ == "__main__":
    main()
