import json
import os


def load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def extract_username_from_item(item):
    """
    Extract username from a string_list_data item.
    Followers format:  {"value": "username", "href": "...", "timestamp": ...}
    Following format:  {"href": "https://www.instagram.com/_u/username", "timestamp": ...}
                       (NO "value" key — username is in the href)
    """
    if not isinstance(item, dict):
        return None
    if item.get("value"):
        return item["value"]
    href = item.get("href", "")
    if "/_u/" in href:
        return href.split("/_u/")[-1].rstrip("/")
    return None


def extract_usernames_from_list(data_list):
    usernames = []
    for entry in data_list:
        if not isinstance(entry, dict):
            continue
        sld = entry.get("string_list_data", [])
        for item in sld:
            u = extract_username_from_item(item)
            if u:
                usernames.append(u)
        # Fallback: title field contains username in following.json
        if not usernames or not sld:
            if entry.get("title"):
                usernames.append(entry["title"])
    return usernames


def extract_usernames(data):
    if isinstance(data, list):
        return extract_usernames_from_list(data)
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, list) and len(val) > 0:
                result = extract_usernames_from_list(val)
                if result:
                    return result
    return []


def count_interactions(data):
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in data:
            if isinstance(data[key], list):
                return len(data[key])
    return 0


def find_connections_folder(folder):
    for root, dirs, files in os.walk(folder):
        if os.path.basename(root) == "followers_and_following":
            if "threads" not in root.replace("\\", "/").lower():
                return root
    return None


def find_activity_folder(folder, subfolder_name):
    for root, dirs, files in os.walk(folder):
        norm = root.replace("\\", "/").lower()
        parts = norm.split("/")
        if (os.path.basename(root).lower() == subfolder_name.lower()
                and "your_instagram_activity" in parts
                and "threads" not in parts):
            return root
    return None


def parse_json_export(folder):

    print("\n=== PARSING JSON EXPORT ===")

    conn_folder = find_connections_folder(folder)
    print(f"  connections folder: {conn_folder}")

    followers = []
    following = []

    if conn_folder:
        for f in sorted(os.listdir(conn_folder)):
            if not f.endswith(".json"):
                continue
            path = os.path.join(conn_folder, f)

            if f.startswith("followers") and "hashtag" not in f:
                data = load_json_file(path)
                if data:
                    extracted = extract_usernames(data)
                    print(f"  followers from {f}: {len(extracted)}")
                    followers.extend(extracted)

            elif f == "following.json":
                data = load_json_file(path)
                if data:
                    extracted = extract_usernames(data)
                    print(f"  following from {f}: {len(extracted)}")
                    following.extend(extracted)

    likes_folder = find_activity_folder(folder, "likes")
    likes_count = 0
    if likes_folder:
        for f in os.listdir(likes_folder):
            if f.endswith(".json") and f.startswith("liked_posts"):
                data = load_json_file(os.path.join(likes_folder, f))
                if data:
                    c = count_interactions(data)
                    print(f"  likes from {f}: {c}")
                    likes_count += c

    comments_folder = find_activity_folder(folder, "comments")
    comments_count = 0
    if comments_folder:
        for f in os.listdir(comments_folder):
            if f.endswith(".json") and (
                f.startswith("post_comments") or f == "reels_comments.json"
            ):
                data = load_json_file(os.path.join(comments_folder, f))
                if data:
                    c = count_interactions(data)
                    print(f"  comments from {f}: {c}")
                    comments_count += c

    print(f"\n  TOTALS => followers:{len(followers)} following:{len(following)} likes:{likes_count} comments:{comments_count}")
    print("=== END PARSING ===\n")

    return {
        "followers": list(set(followers)),
        "following": list(set(following)),
        "likes":     list(range(likes_count)),
        "comments":  list(range(comments_count)),
    }