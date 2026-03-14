def ghost_followers(connections):
    """
    Returns followers who have never liked or commented on any posts.
    Only meaningful when likes/comments contain actual usernames.
    """
    followers = set(connections.get("followers", []))
    likes = set(connections.get("likes", []))
    comments = set(connections.get("comments", []))

    interactions = likes.union(comments)

    ghosts = [user for user in followers if user not in interactions]

    return {
        "ghosts": sorted(ghosts),
        "ghost_count": len(ghosts),
        "total_followers": len(followers),
        "ghost_percentage": round((len(ghosts) / len(followers) * 100), 1) if followers else 0,
    }