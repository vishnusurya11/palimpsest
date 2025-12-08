import os
import re
import sys
import requests
import yaml
from dotenv import load_dotenv

# -------------------------------------------------
# CONFIG – change these for other projects/repos
# -------------------------------------------------
OWNER = "vishnusurya11"
REPO = "palimpsest"
CONFIG_PATH = "config/pali_items.yaml"

BASE_ID_PREFIX = "PALI"  # sanity check only
PRIORITY_LABELS = {"P0", "P1", "P2"}

KIND_CONFIG = {
    "epic": {
        "label": "Epics",
        "id_regex": r"^PALI-E\d+$",
    },
    "story": {
        "label": "Stories",
        "id_regex": r"^PALI-E\d+-S\d+$",
    },
    "task": {
        "label": "Tasks",
        "id_regex": r"^PALI-E\d+-S\d+-T\d+$",
    },
    "subtask": {
        "label": "Sub-tasks",
        "id_regex": r"^PALI-E\d+-S\d+-T\d+-ST\d+$",
    },
}
# -------------------------------------------------

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise SystemExit(
        "GITHUB_TOKEN environment variable not set. "
        "Set GITHUB_TOKEN in your .env file."
    )

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

ISSUES_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/issues"


# ---------- Load & flatten YAML ----------

def load_flat_items(config_path: str):
    if not os.path.exists(config_path):
        raise SystemExit(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    epics = data.get("epics", [])
    flat = []

    for epic in epics:
        epic_id = epic["id"].strip()
        epic_phase = epic["phase"].strip()
        epic_priority = epic["priority"].strip()
        epic_title = epic["title"].strip()
        epic_desc = (epic.get("description") or "").strip()

        flat.append(
            {
                "id": epic_id,
                "kind": "epic",
                "phase": epic_phase,
                "priority": epic_priority,
                "title": epic_title,
                "description": epic_desc,
                "epic_id": None,
                "story_id": None,
                "task_id": None,
            }
        )

        for story in epic.get("stories", []) or []:
            story_id = story["id"].strip()
            story_phase = (story.get("phase") or epic_phase).strip()
            story_priority = (story.get("priority") or epic_priority).strip()
            story_title = story["title"].strip()
            story_desc = (story.get("description") or "").strip()

            flat.append(
                {
                    "id": story_id,
                    "kind": "story",
                    "phase": story_phase,
                    "priority": story_priority,
                    "title": story_title,
                    "description": story_desc,
                    "epic_id": epic_id,
                    "story_id": None,
                    "task_id": None,
                }
            )

            for task in story.get("tasks", []) or []:
                task_id = task["id"].strip()
                task_phase = (task.get("phase") or story_phase).strip()
                task_priority = (task.get("priority") or story_priority).strip()
                task_title = task["title"].strip()
                task_desc = (task.get("description") or "").strip()

                flat.append(
                    {
                        "id": task_id,
                        "kind": "task",
                        "phase": task_phase,
                        "priority": task_priority,
                        "title": task_title,
                        "description": task_desc,
                        "epic_id": epic_id,
                        "story_id": story_id,
                        "task_id": None,
                    }
                )

                for sub in task.get("subtasks", []) or []:
                    sub_id = sub["id"].strip()
                    sub_phase = (sub.get("phase") or task_phase).strip()
                    sub_priority = (sub.get("priority") or task_priority).strip()
                    sub_title = sub["title"].strip()
                    sub_desc = (sub.get("description") or "").strip()

                    flat.append(
                        {
                            "id": sub_id,
                            "kind": "subtask",
                            "phase": sub_phase,
                            "priority": sub_priority,
                            "title": sub_title,
                            "description": sub_desc,
                            "epic_id": epic_id,
                            "story_id": story_id,
                            "task_id": task_id,
                        }
                    )

    return flat


# ---------- Helpers for title/body ----------

def desired_title(item):
    return f"[{item['id']}] {item['title']}"


def desired_body(item, config_path: str):
    item_id = item["id"]
    kind_word = {
        "epic": "Epic",
        "story": "Story",
        "task": "Task",
        "subtask": "Sub-task",
    }[item["kind"]]
    phase = item["phase"]
    priority = item["priority"]
    desc_block = item["description"] or "TODO: add a clear goal / description for this item."

    lines = [
        f"# {item_id} – {item['title']}",
        "",
        f"**ID:** {item_id}  ",
        f"**Kind:** {kind_word}  ",
        f"**Phase:** {phase}  ",
        f"**Priority:** {priority}  ",
    ]

    if item["epic_id"]:
        lines.append(f"**Epic:** {item['epic_id']}  ")
    if item["story_id"]:
        lines.append(f"**Story:** {item['story_id']}  ")
    if item["task_id"]:
        lines.append(f"**Task:** {item['task_id']}  ")

    lines.extend(
        [
            "",
            "**Goal / Description**  ",
            desc_block,
            "",
            "---",
            "",
            f"This issue is fully managed by `{config_path}`.",
            "Edit YAML, then rerun the sync script.",
        ]
    )

    return "\n".join(lines)


# ---------- Discover existing issues ----------

def extract_id_from_title(title: str):
    title = title.strip()

    if title.startswith("["):
        closing = title.find("]")
        if closing != -1:
            inner = title[1:closing].strip()
            return inner

    first_token = title.split(" ")[0]
    return first_token if first_token.startswith(BASE_ID_PREFIX) else None


def get_existing_items_map(id_regex: re.Pattern):
    existing = {}
    page = 1

    while True:
        params = {"state": "all", "per_page": 100, "page": page}
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
            item_id = extract_id_from_title(title)
            if not item_id:
                continue

            if not id_regex.match(item_id):
                continue

            if item_id not in existing:
                existing[item_id] = issue

        page += 1

    return existing


def get_all_existing_items():
    """
    Map every YAML-style ID (PALI-*) to the full issue object.
    Used when wiring up sub-issue relationships.
    """
    existing = {}
    page = 1
    while True:
        params = {"state": "all", "per_page": 100, "page": page}
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
            item_id = extract_id_from_title(title)
            if not item_id:
                continue
            if item_id.startswith(BASE_ID_PREFIX) and item_id not in existing:
                existing[item_id] = issue
        page += 1
    return existing


# ---------- Labels / priority / id-segment labels ----------

ID_SEGMENTS_RE = re.compile(
    r"^PALI-(E\d+)(?:-(S\d+))?(?:-(T\d+))?(?:-(ST\d+))?$"
)


def extract_id_segment_labels(item_id: str):
    """
    Turn 'PALI-E1-S5-T3-ST2' into ['E1', 'S5', 'T3', 'ST2'].
    """
    m = ID_SEGMENTS_RE.match(item_id)
    if not m:
        return []
    return [g for g in m.groups() if g]


def compute_labels(current_labels, item_label: str, priority: str, item_id: str):
    new_labels = list(current_labels)

    # Ensure base label (Epics / Stories / Tasks / Sub-tasks)
    if item_label not in new_labels:
        new_labels.append(item_label)

    # Ensure ID segment labels (E1, S3, T2, ST1...)
    for seg in extract_id_segment_labels(item_id):
        if seg not in new_labels:
            new_labels.append(seg)

    # Remove old priority labels
    new_labels = [l for l in new_labels if l not in PRIORITY_LABELS]

    # Add current priority
    if priority in PRIORITY_LABELS and priority not in new_labels:
        new_labels.append(priority)
    elif priority not in PRIORITY_LABELS:
        print(f"[WARN] Unknown priority '{priority}'; expected one of {PRIORITY_LABELS}")

    return new_labels


# ---------- Create / Update / Prune ----------

def create_item(item, item_label: str):
    issue_title = desired_title(item)
    body = desired_body(item, CONFIG_PATH)
    labels = compute_labels([], item_label, item["priority"], item["id"])

    payload = {"title": issue_title, "body": body, "labels": labels}

    resp = requests.post(ISSUES_URL, headers=HEADERS, json=payload)
    if resp.status_code == 201:
        data = resp.json()
        print(f"[CREATE] {item['id']}: #{data['number']} → {data['html_url']}")
    else:
        print(f"[CREATE-FAILED] {item['id']}: {resp.status_code}")
        print(resp.text)


def update_item(issue, item, item_label: str):
    issue_number = issue["number"]
    current_title = issue.get("title", "")
    current_labels = [lbl["name"] for lbl in issue.get("labels", [])]

    new_title = desired_title(item)
    new_body = desired_body(item, CONFIG_PATH)
    new_labels = compute_labels(current_labels, item_label, item["priority"], item["id"])

    needs_update = False
    if current_title != new_title:
        needs_update = True
    if issue.get("body", "") != new_body:
        needs_update = True
    if set(current_labels) != set(new_labels):
        needs_update = True

    if not needs_update:
        print(f"[SKIP] {item['id']}: no changes")
        return

    payload = {
        "title": new_title,
        "body": new_body,
        "labels": new_labels,
    }

    url = f"{ISSUES_URL}/{issue_number}"
    resp = requests.patch(url, headers=HEADERS, json=payload)
    if resp.status_code == 200:
        print(f"[UPDATE] {item['id']}: issue #{issue_number} updated")
    else:
        print(f"[UPDATE-FAILED] {item['id']}: {resp.status_code}")
        print(resp.text)


def prune_items(kind: str, flat_items, existing_map):
    """Close issues that match this kind's pattern but are NOT in YAML."""
    cfg = KIND_CONFIG[kind]
    valid_ids = {it["id"] for it in flat_items if it["kind"] == kind}

    for issue_id, issue in existing_map.items():
        if issue_id in valid_ids:
            continue

        number = issue["number"]
        print(f"[PRUNE] Closing orphan {kind} {issue_id} (#{number})")
        url = f"{ISSUES_URL}/{number}"
        payload = {"state": "closed"}
        resp = requests.patch(url, headers=HEADERS, json=payload)
        if resp.status_code != 200:
            print(f"[PRUNE-FAILED] {issue_id}: {resp.status_code}")
            print(resp.text)


# ---------- Sub-issue linking ----------

def add_sub_issue(parent_issue_number: int, child_issue_id: int):
    """
    Use GitHub's 'Add sub-issue' REST endpoint so that the child
    shows up in the Sub-issues panel, not just as text in the body.
    """
    url = f"{ISSUES_URL}/{parent_issue_number}/sub_issues"
    payload = {"sub_issue_id": child_issue_id}
    resp = requests.post(url, headers=HEADERS, json=payload)

    if resp.status_code == 201:
        print(f"[LINK] parent#{parent_issue_number} ← sub_id {child_issue_id}")
    elif resp.status_code == 422:
        # Validation failed – most likely the relationship already exists.
        print(f"[LINK-SKIP] relationship already exists for parent#{parent_issue_number}")
    else:
        print(
            f"[LINK-FAILED] parent#{parent_issue_number} sub_id {child_issue_id}: "
            f"{resp.status_code}"
        )
        print(resp.text)


def sync_sub_issue_links(flat_items):
    """
    For each Story/Task/Subtask, attach it as a real sub-issue to its parent
    (Epic/Story/Task) using the REST sub-issues API.
    """
    all_issues = get_all_existing_items()

    for item in flat_items:
        kind = item["kind"]
        item_id = item["id"]
        issue = all_issues.get(item_id)
        if not issue:
            continue  # should not happen if sync ran first

        parent_key = None
        if kind == "story" and item["epic_id"]:
            parent_key = item["epic_id"]
        elif kind == "task" and item["story_id"]:
            parent_key = item["story_id"]
        elif kind == "subtask" and item["task_id"]:
            parent_key = item["task_id"]

        if not parent_key:
            continue

        parent_issue = all_issues.get(parent_key)
        if not parent_issue:
            print(f"[LINK-WARN] No parent issue found for {item_id} (parent {parent_key})")
            continue

        parent_number = parent_issue["number"]
        child_id = issue["id"]
        add_sub_issue(parent_number, child_id)


# ---------- Run for one kind ----------

def sync_kind(kind: str, flat_items, do_prune: bool):
    cfg = KIND_CONFIG[kind]
    item_label = cfg["label"]
    id_regex = re.compile(cfg["id_regex"])

    items_for_kind = [it for it in flat_items if it["kind"] == kind]
    existing_map = get_existing_items_map(id_regex)

    print(
        f"Existing {kind} items found:",
        ", ".join(sorted(existing_map.keys())) or "none",
    )

    for item in items_for_kind:
        existing = existing_map.get(item["id"])
        if existing is None:
            create_item(item, item_label)
        else:
            update_item(existing, item, item_label)

    if do_prune:
        prune_items(kind, flat_items, existing_map)


# ---------- Main ----------

def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python sync_items.py [epic|story|task|subtask|all] [--prune]")

    arg = sys.argv[1].lower()
    allowed = {"epic", "story", "task", "subtask", "all"}
    if arg not in allowed:
        raise SystemExit(f"Invalid kind '{arg}'. Use one of: epic, story, task, subtask, all")

    do_prune = "--prune" in sys.argv[2:]

    flat_items = load_flat_items(CONFIG_PATH)

    if arg == "all":
        for kind in ["epic", "story", "task", "subtask"]:
            print(f"\n=== Syncing {kind} (prune={do_prune}) ===")
            sync_kind(kind, flat_items, do_prune)

        # After everything exists / is updated, wire up parent-child links.
        print("\n=== Syncing sub-issue relationships ===")
        sync_sub_issue_links(flat_items)
    else:
        print(f"\n=== Syncing {arg} (prune={do_prune}) ===")
        sync_kind(arg, flat_items, do_prune)

        # If you run per-kind, we don't touch sub-issue links automatically.
        # Run `python sync_items.py all` occasionally to keep hierarchy wired.


if __name__ == "__main__":
    main()
