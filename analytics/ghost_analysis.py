
def ghost_followers(data):
    followers=set(data["followers"])
    following=set(data["following"])
    ghosts=list(followers-following)
    return ghosts[:100]
