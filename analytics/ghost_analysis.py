def ghost_followers(data):

    followers = set(data.get("followers", []))
    likes = set(data.get("likes", []))
    comments = set(data.get("comments", []))

    interactions = likes.union(comments)

    ghosts = []

    for user in followers:
        if user not in interactions:
            ghosts.append(user)

    return ghosts