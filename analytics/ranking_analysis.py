from collections import Counter


def interaction_ranking(connections):
    """
    Ranks users by interaction score (likes = 1pt, comments = 2pts).
    Only meaningful when likes/comments contain actual usernames.
    """
    likes = connections.get("likes", [])
    comments = connections.get("comments", [])

    counter = Counter()

    for user in likes:
        if isinstance(user, str):
            counter[user] += 1

    for user in comments:
        if isinstance(user, str):
            counter[user] += 2

    ranking = sorted(counter.items(), key=lambda x: x[1], reverse=True)

    return [{"user": user, "score": score} for user, score in ranking[:20]]


def loyal_followers(connections):
    """
    Returns the top interacting users who also follow you back.
    """
    followers_set = set(connections.get("followers", []))
    ranking = interaction_ranking(connections)

    return [entry for entry in ranking if entry["user"] in followers_set]