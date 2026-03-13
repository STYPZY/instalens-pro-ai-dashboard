def relationship_stats(data):

    followers = list(set(data.get("followers", [])))
    following = list(set(data.get("following", [])))

    followers_set = set(followers)
    following_set = set(following)

    mutual = followers_set.intersection(following_set)
    not_following_back = following_set - followers_set
    fans = followers_set - following_set

    return {
        "report": {
            "total_followers": len(followers),
            "total_following": len(following)
        },

        "current": {
            "followers": followers,
            "following": following,
            "followers_count": len(followers),
            "following_count": len(following)
        },

        "relationships": {
            "mutual": list(mutual),
            "mutual_count": len(mutual),

            "not_following_back": list(not_following_back),
            "not_following_back_count": len(not_following_back),

            "fans": list(fans),
            "fans_count": len(fans)
        }
    }