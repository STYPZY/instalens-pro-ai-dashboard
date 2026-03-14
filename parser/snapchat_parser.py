import json
import os
from collections import defaultdict, Counter


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_json_folder(folder):
    """Find the json/ subfolder inside extracted Snapchat ZIP."""
    for root, dirs, files in os.walk(folder):
        if os.path.basename(root).lower() == "json":
            if any(f.endswith(".json") for f in os.listdir(root)):
                return root
    return folder


def parse_account(json_folder):
    data = load_json(os.path.join(json_folder, "account.json")) or {}
    basic = data.get("Basic Information", data)
    return {
        "username":     basic.get("Username", ""),
        "display_name": basic.get("Name", ""),
        "email":        basic.get("Email", ""),
        "phone":        basic.get("Phone Number", ""),
        "created":      basic.get("Creation Date", ""),
        "birthday":     basic.get("Birthday", ""),
        "snap_score":   basic.get("Snap Score (Approximate)", "") or basic.get("Snap Score", ""),
    }


def parse_friends(json_folder):
    data = load_json(os.path.join(json_folder, "friends.json")) or {}

    friends = []
    for e in data.get("Friends", []):
        friends.append({
            "username":     e.get("Username", ""),
            "display_name": e.get("Display Name", ""),
            "added_date":   e.get("Friend Since", ""),
            "source":       e.get("Source Type", ""),
        })

    blocked = []
    for e in data.get("Blocked Users", []):
        blocked.append({
            "username":     e.get("Username", ""),
            "blocked_date": e.get("Blocked Date", ""),
        })

    deleted = []
    for e in data.get("Deleted Friends", []):
        deleted.append({
            "username":     e.get("Username", ""),
            "deleted_date": e.get("Deleted Date", ""),
        })

    pending = []
    for e in data.get("Pending Friend Requests", []):
        pending.append({
            "username":     e.get("Username", ""),
            "request_date": e.get("Request Date", ""),
        })

    sources = Counter(f["source"] for f in friends if f["source"])

    return {
        "friends":           friends,
        "friends_count":     len(friends),
        "blocked":           blocked,
        "blocked_count":     len(blocked),
        "deleted":           deleted,
        "deleted_count":     len(deleted),
        "pending":           pending,
        "pending_count":     len(pending),
        "source_breakdown":  dict(sources.most_common(10)),
    }


def parse_memories(json_folder):
    data = load_json(os.path.join(json_folder, "memories_history.json")) or {}
    saved = data.get("Saved Media", [])

    photos = 0
    videos = 0
    by_year  = defaultdict(lambda: {"photos": 0, "videos": 0})
    by_month = defaultdict(int)
    locations = []

    for entry in saved:
        mtype = entry.get("Media Type", "").upper()
        date  = entry.get("Date", "")

        if mtype == "VIDEO":
            videos += 1
            kind = "videos"
        else:
            photos += 1
            kind = "photos"

        if date:
            try:
                year  = date[:4]
                month = date[:7]
                if 2010 <= int(year) <= 2035:
                    by_year[year][kind] += 1
                    by_month[month] += 1
            except Exception:
                pass

        loc = entry.get("Location", "")
        if loc and loc.strip():
            locations.append({"date": date, "location": loc})

    return {
        "total":          photos + videos,
        "photos":         photos,
        "videos":         videos,
        "by_year":        dict(sorted(by_year.items())),
        "by_month":       dict(sorted(by_month.items())),
        "locations":      locations[:50],
        "location_count": len(locations),
    }


def parse_chat_history(json_folder):
    data = load_json(os.path.join(json_folder, "chat_history.json")) or {}

    conversations  = {}
    total_sent     = 0
    total_received = 0
    media_count    = 0

    if "Chat History" in data:
        for conv_key, messages in data["Chat History"].items():
            name = conv_key.replace("Conversation with ", "").strip()
            if name not in conversations:
                conversations[name] = {"sent": 0, "received": 0, "media": 0, "last_active": ""}
            for msg in (messages or []):
                sender = msg.get("From", "")
                is_me  = (sender.lower() in ("me", "") or not sender)
                if is_me:
                    conversations[name]["sent"] += 1
                    total_sent += 1
                else:
                    conversations[name]["received"] += 1
                    total_received += 1
                if msg.get("Media Type", "").upper() not in ("", "TEXT", "NONE"):
                    conversations[name]["media"] += 1
                    media_count += 1
                ts = msg.get("Created", "")
                if ts > conversations[name]["last_active"]:
                    conversations[name]["last_active"] = ts
    else:
        for msg in data.get("Received Chats", []):
            sender = msg.get("From", "unknown")
            if sender not in conversations:
                conversations[sender] = {"sent": 0, "received": 0, "media": 0, "last_active": ""}
            conversations[sender]["received"] += 1
            total_received += 1
            if msg.get("Media Type", "").upper() not in ("", "TEXT", "NONE"):
                conversations[sender]["media"] += 1
                media_count += 1
            ts = msg.get("Created", "")
            if ts > conversations[sender]["last_active"]:
                conversations[sender]["last_active"] = ts

        for msg in data.get("Sent Chats", []):
            recipient = msg.get("To", "unknown")
            if recipient not in conversations:
                conversations[recipient] = {"sent": 0, "received": 0, "media": 0, "last_active": ""}
            conversations[recipient]["sent"] += 1
            total_sent += 1
            ts = msg.get("Created", "")
            if ts > conversations[recipient]["last_active"]:
                conversations[recipient]["last_active"] = ts

    sorted_convs = sorted(
        [{"name": k, **v} for k, v in conversations.items()],
        key=lambda x: x["sent"] + x["received"],
        reverse=True
    )

    return {
        "total_sent":          total_sent,
        "total_received":      total_received,
        "total_messages":      total_sent + total_received,
        "media_count":         media_count,
        "conversations":       sorted_convs[:50],
        "total_conversations": len(conversations),
    }


def parse_snap_history(json_folder):
    data = load_json(os.path.join(json_folder, "snap_history.json")) or {}

    sent     = data.get("Sent Snap History", [])
    received = data.get("Received Snap History", [])

    sent_images = sum(1 for s in sent     if s.get("Media Type", "").upper() in ("IMAGE", "PHOTO"))
    sent_videos = sum(1 for s in sent     if s.get("Media Type", "").upper() == "VIDEO")
    recv_images = sum(1 for r in received if r.get("Media Type", "").upper() in ("IMAGE", "PHOTO"))
    recv_videos = sum(1 for r in received if r.get("Media Type", "").upper() == "VIDEO")

    sent_to   = Counter(s.get("To",   "") for s in sent     if s.get("To"))
    recv_from = Counter(r.get("From", "") for r in received if r.get("From"))

    return {
        "total_sent":     len(sent),
        "total_received": len(received),
        "sent_images":    sent_images,
        "sent_videos":    sent_videos,
        "recv_images":    recv_images,
        "recv_videos":    recv_videos,
        "top_sent_to":    [{"user": u, "count": c} for u, c in sent_to.most_common(10)],
        "top_recv_from":  [{"user": u, "count": c} for u, c in recv_from.most_common(10)],
    }


def parse_search_history(json_folder):
    data  = load_json(os.path.join(json_folder, "search_history.json")) or {}
    items = data.get("Search History", [])
    terms = [s.get("Search Term", "") for s in items if s.get("Search Term")]
    top   = Counter(terms).most_common(20)
    return {
        "total":     len(items),
        "unique":    len(set(terms)),
        "top_terms": [{"term": t, "count": c} for t, c in top],
    }


def parse_location_history(json_folder):
    data      = load_json(os.path.join(json_folder, "location_history.json")) or {}
    locations = data.get("Location History", [])
    return {
        "total":  len(locations),
        "recent": locations[:20],
    }


def parse_login_history(json_folder):
    data   = load_json(os.path.join(json_folder, "account.json")) or {}
    logins = data.get("Login History", [])
    if not logins:
        data2  = load_json(os.path.join(json_folder, "login_history.json")) or {}
        logins = data2.get("Login History", [])

    ips       = list({l.get("IP", "")      for l in logins if l.get("IP")})
    devices   = list({l.get("Device", "")  for l in logins if l.get("Device")})
    countries = list({l.get("Country", "") for l in logins if l.get("Country")})

    return {
        "total":      len(logins),
        "unique_ips": len(ips),
        "devices":    devices[:10],
        "countries":  countries[:10],
        "recent":     logins[:20],
    }


def parse_story_history(json_folder):
    data    = load_json(os.path.join(json_folder, "story_history.json")) or {}
    stories = data.get("My Story", []) or data.get("Story History", [])
    by_year = defaultdict(int)
    for s in stories:
        date = s.get("Date", "")
        if date:
            try:
                year = date[:4]
                if 2010 <= int(year) <= 2035:
                    by_year[year] += 1
            except Exception:
                pass
    return {
        "total":   len(stories),
        "by_year": dict(sorted(by_year.items())),
    }


def parse_snapchat_export(folder):
    """Master parser — finds json/ folder and parses all available data."""
    json_folder = find_json_folder(folder)
    return {
        "account":        parse_account(json_folder),
        "friends":        parse_friends(json_folder),
        "memories":       parse_memories(json_folder),
        "chat_history":   parse_chat_history(json_folder),
        "snap_history":   parse_snap_history(json_folder),
        "search_history": parse_search_history(json_folder),
        "location":       parse_location_history(json_folder),
        "login":          parse_login_history(json_folder),
        "stories":        parse_story_history(json_folder),
    }