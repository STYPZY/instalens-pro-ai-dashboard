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
    best = None
    best_count = 0
    for root, dirs, files in os.walk(folder):
        json_count = sum(1 for f in files if f.endswith(".json"))
        if json_count > best_count:
            best_count = json_count
            best = root
    return best if best else folder


def scan_all_json(json_folder):
    all_data = {}
    for root, dirs, files in os.walk(json_folder):
        for f in files:
            if f.endswith(".json"):
                data = load_json(os.path.join(root, f))
                if data is not None:
                    all_data[f.lower()] = data
    return all_data


def get_data(all_data, *filenames):
    for name in filenames:
        data = all_data.get(name.lower())
        if data is not None:
            return data
    return {}


def parse_account(all_data):
    data = get_data(all_data, "account.json") or {}
    basic = data.get("Basic Information") or data
    if not isinstance(basic, dict):
        basic = data

    hist = get_data(all_data, "account_history.json") or {}
    email = ""
    phone = ""
    email_changes = hist.get("Email Change", [])
    if email_changes and isinstance(email_changes, list):
        email = email_changes[0].get("Email Address", "") if email_changes[0] else ""
    phone_changes = hist.get("Mobile Number Change", [])
    if phone_changes and isinstance(phone_changes, list):
        phone = phone_changes[0].get("Mobile Number", "") if phone_changes[0] else ""

    snap_score = ""
    profile = get_data(all_data, "user_profile.json") or {}
    engagement = profile.get("Engagement", [])
    if isinstance(engagement, list):
        for e in engagement:
            if isinstance(e, dict) and "Snap Score" in str(e.get("Event", "")):
                snap_score = str(e.get("Occurrences", ""))
                break

    return {
        "username":     basic.get("Username", ""),
        "display_name": basic.get("Name", ""),
        "email":        email,
        "phone":        phone,
        "created":      basic.get("Creation Date", ""),
        "birthday":     basic.get("Birthday", "") or basic.get("Date of Birth", ""),
        "snap_score":   snap_score,
        "country":      basic.get("Country", ""),
        "last_active":  basic.get("Last Active", ""),
    }


def parse_friends(all_data):
    data = get_data(all_data, "friends.json") or {}

    def extract_users(lst):
        result = []
        for e in (lst or []):
            if not isinstance(e, dict):
                continue
            result.append({
                "username":     e.get("Username", ""),
                "display_name": e.get("Display Name", ""),
                "added_date":   e.get("Creation Timestamp", "") or e.get("Friend Since", ""),
                "source":       e.get("Source", "") or e.get("Source Type", ""),
            })
        return result

    friends  = extract_users(data.get("Friends", []))
    blocked  = [{"username": e.get("Username", ""), "blocked_date": e.get("Creation Timestamp", "")}
                for e in data.get("Blocked Users", []) if isinstance(e, dict)]
    deleted  = extract_users(data.get("Deleted Friends", []))
    pending  = extract_users(data.get("Pending Requests", []))
    ignored  = extract_users(data.get("Ignored Snapchatters", []))
    sent_req = extract_users(data.get("Friend Requests Sent", []))

    sources = Counter(f["source"] for f in friends if f["source"])

    return {
        "friends":              friends,
        "friends_count":        len(friends),
        "blocked":              blocked,
        "blocked_count":        len(blocked),
        "deleted":              deleted,
        "deleted_count":        len(deleted),
        "pending":              pending,
        "pending_count":        len(pending),
        "ignored":              ignored,
        "ignored_count":        len(ignored),
        "sent_requests":        sent_req,
        "sent_requests_count":  len(sent_req),
        "source_breakdown":     dict(sources.most_common(10)),
    }


def parse_memories(all_data):
    data = get_data(all_data,
        "memories_history.json", "memories.json",
        "saved_media.json", "memories-history.json"
    ) or {}

    saved = []
    if "" in data and isinstance(data[""], list):
        saved = data[""]
    else:
        for key in ("Saved Media", "savedMedia", "memories", "Memories", "Media"):
            if key in data and isinstance(data[key], list):
                saved = data[key]
                break

    photos = 0
    videos = 0
    by_year  = defaultdict(lambda: {"photos": 0, "videos": 0})
    by_month = defaultdict(int)
    locations = []

    for entry in saved:
        if not isinstance(entry, dict):
            continue
        mtype = str(entry.get("Media Type") or entry.get("mediaType") or "").upper()
        date  = str(entry.get("Date") or entry.get("Created") or entry.get("Timestamp") or
                    entry.get("Date and time (hourly)") or "")
        if mtype == "VIDEO":
            videos += 1
            kind = "videos"
        else:
            photos += 1
            kind = "photos"
        if date and len(date) >= 4:
            try:
                year = date[:4]
                month = date[:7]
                if 2010 <= int(year) <= 2035:
                    by_year[year][kind] += 1
                    by_month[month] += 1
            except Exception:
                pass
        loc = str(entry.get("Location") or entry.get("location") or "").strip()
        if loc:
            locations.append({"date": date, "location": loc})

    return {
        "total":          photos + videos,
        "photos":         photos,
        "videos":         videos,
        "by_year":        dict(sorted(by_year.items())),
        "by_month":       dict(sorted(by_month.items())),
        "locations":      locations[:50],
        "location_count": len(locations),
        "not_in_export":  (photos + videos) == 0,
    }


def parse_chat_history(all_data):
    data = get_data(all_data, "chat_history.json", "chats.json") or {}

    conversations  = {}
    total_sent     = 0
    total_received = 0
    media_count    = 0

    if isinstance(data, dict) and all(isinstance(v, list) for v in data.values()) and data:
        for username, messages in data.items():
            if not isinstance(messages, list):
                continue
            conversations[username] = {"sent": 0, "received": 0, "media": 0, "last_active": ""}
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                is_sender = msg.get("IsSender")
                if is_sender is None:
                    sender = str(msg.get("From") or "")
                    is_sender = sender.lower() not in ("", username.lower())
                if is_sender:
                    conversations[username]["sent"] += 1
                    total_sent += 1
                else:
                    conversations[username]["received"] += 1
                    total_received += 1
                mtype = str(msg.get("Media Type") or "").upper()
                if mtype not in ("", "TEXT", "NONE", "NOTE"):
                    conversations[username]["media"] += 1
                    media_count += 1
                ts = str(msg.get("Created") or "")
                if ts > conversations[username]["last_active"]:
                    conversations[username]["last_active"] = ts

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


def parse_snap_history(all_data):
    data = get_data(all_data, "snap_history.json", "snaps.json") or {}

    total_sent     = 0
    total_received = 0
    sent_images    = 0
    sent_videos    = 0
    recv_images    = 0
    recv_videos    = 0
    sent_to        = Counter()
    recv_from      = Counter()

    if isinstance(data, dict) and all(isinstance(v, list) for v in data.values()) and data:
        for username, snaps in data.items():
            if not isinstance(snaps, list):
                continue
            for snap in snaps:
                if not isinstance(snap, dict):
                    continue
                is_sender = snap.get("IsSender")
                if is_sender is None:
                    sender = str(snap.get("From") or "")
                    is_sender = sender.lower() not in ("", username.lower())
                mtype = str(snap.get("Media Type") or "").upper()
                if is_sender:
                    total_sent += 1
                    sent_to[username] += 1
                    if mtype in ("IMAGE", "PHOTO"):
                        sent_images += 1
                    elif mtype == "VIDEO":
                        sent_videos += 1
                else:
                    total_received += 1
                    recv_from[username] += 1
                    if mtype in ("IMAGE", "PHOTO"):
                        recv_images += 1
                    elif mtype == "VIDEO":
                        recv_videos += 1

    return {
        "total_sent":     total_sent,
        "total_received": total_received,
        "sent_images":    sent_images,
        "sent_videos":    sent_videos,
        "recv_images":    recv_images,
        "recv_videos":    recv_videos,
        "top_sent_to":    [{"user": u, "count": c} for u, c in sent_to.most_common(10)],
        "top_recv_from":  [{"user": u, "count": c} for u, c in recv_from.most_common(10)],
    }


def parse_search_history(all_data):
    data = get_data(all_data, "search_history.json") or {}

    items = data.get("", [])
    if not items:
        for key in ("Search History", "searchHistory", "searches"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                break

    terms = []
    for s in items:
        if not isinstance(s, dict):
            continue
        term = str(s.get("Search Term") or s.get("searchTerm") or s.get("query") or "")
        if term:
            terms.append(term)

    top = Counter(terms).most_common(20)
    return {
        "total":     len(items),
        "unique":    len(set(terms)),
        "top_terms": [{"term": t, "count": c} for t, c in top],
    }


def parse_location_history(all_data):
    data = get_data(all_data, "location_history.json", "location.json", "snap_map.json") or {}
    locations = data.get("", []) or data.get("Location History", []) or []
    return {
        "total":  len(locations),
        "recent": locations[:20],
    }


def parse_login_history(all_data):
    data = get_data(all_data, "account.json") or {}
    logins = data.get("Login History", [])

    ips       = list({str(l.get("IP") or "")      for l in logins if l.get("IP")})
    devices_raw = [str(l.get("Device") or "")     for l in logins if l.get("Device")]
    countries = list({str(l.get("Country") or "") for l in logins if l.get("Country")})
    devices   = list({d.split("/")[0] if "/" in d else d for d in devices_raw if d})

    return {
        "total":      len(logins),
        "unique_ips": len(ips),
        "devices":    devices[:10],
        "countries":  [c for c in countries if c][:10],
        "recent":     logins[:20],
    }


def parse_story_history(all_data):
    data = get_data(all_data, "story_history.json", "stories.json", "my_stories.json") or {}
    stories = data.get("", []) or data.get("My Story", []) or data.get("Story History", []) or []

    by_year = defaultdict(int)
    for s in stories:
        if not isinstance(s, dict):
            continue
        date = str(s.get("Date") or s.get("Created") or s.get("Timestamp") or
                   s.get("Date and time (hourly)") or "")
        if date and len(date) >= 4:
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


def parse_account_history(all_data):
    data = get_data(all_data, "account_history.json") or {}
    return {
        "password_changes":     len(data.get("Password Change", [])),
        "display_name_changes": len(data.get("Display Name Change", [])),
        "two_fa_events":        data.get("Two-Factor Authentication", []),
        "download_requests":    data.get("Download My Data Reports", []),
    }


def parse_user_profile(all_data):
    data = get_data(all_data, "user_profile.json") or {}

    engagement = {}
    for e in (data.get("Engagement") or []):
        if isinstance(e, dict) and e.get("Event"):
            engagement[e["Event"]] = e.get("Occurrences", 0)

    time_spent   = data.get("Breakdown of Time Spent on App", [])
    demographics = data.get("Demographics") or {}
    app_profile  = data.get("App Profile") or {}

    return {
        "engagement":  engagement,
        "time_spent":  time_spent if isinstance(time_spent, list) else [],
        "age_group":   demographics.get("Cohort Age", ""),
        "gender":      demographics.get("Derived Ad Demographic", ""),
        "country":     app_profile.get("Country", ""),
    }


def parse_snapchat_export(folder):
    json_folder = find_json_folder(folder)
    all_data    = scan_all_json(json_folder)

    return {
        "account":         parse_account(all_data),
        "friends":         parse_friends(all_data),
        "memories":        parse_memories(all_data),
        "chat_history":    parse_chat_history(all_data),
        "snap_history":    parse_snap_history(all_data),
        "search_history":  parse_search_history(all_data),
        "location":        parse_location_history(all_data),
        "login":           parse_login_history(all_data),
        "stories":         parse_story_history(all_data),
        "account_history": parse_account_history(all_data),
        "user_profile":    parse_user_profile(all_data),
    }