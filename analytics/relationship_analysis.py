def relationship_stats(data):

    followers = set(data["followers"])
    following = set(data["following"])

    mutual = followers.intersection(following)
    fans = followers - following
    not_following_back = following - followers

    return {
        "followers": len(followers),
        "following": len(following),
        "mutual": len(mutual),
        "fans": len(fans),

        "not_following_back": len(not_following_back),

        # lists for templates
        "fans_list": list(fans),
        "not_following_back_list": list(not_following_back)
    }