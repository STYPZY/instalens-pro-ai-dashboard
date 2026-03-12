def relationship_stats(data):

    followers = set(data.get("followers", []))
    following = set(data.get("following", []))

    mutual = followers.intersection(following)
    not_following_back = following - followers
    fans = followers - following

    return {
        "followers": len(followers),
        "following": len(following),
        "mutual": list(mutual),
        "not_following_back": list(not_following_back),
        "fans": list(fans)
    }