def normalize_data(parsed):

    normalized = {
        "followers": [],
        "following": [],
        "likes": [],
        "comments": []
    }

    if not parsed:
        return normalized

    normalized["followers"] = list(set(parsed.get("followers", [])))
    normalized["following"] = list(set(parsed.get("following", [])))
    normalized["likes"] = parsed.get("likes", [])
    normalized["comments"] = parsed.get("comments", [])

    return normalized