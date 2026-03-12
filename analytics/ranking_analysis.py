from collections import Counter


def interaction_ranking(data):

    likes = data.get("likes", [])
    comments = data.get("comments", [])

    counter = Counter()

    for user in likes:
        counter[user] += 1

    for user in comments:
        counter[user] += 2

    ranking = sorted(counter.items(), key=lambda x: x[1], reverse=True)

    return ranking[:20]


def loyal_followers(data):

    followers = set(data.get("followers", []))
    ranking = interaction_ranking(data)

    loyal = []

    for user, score in ranking:

        if user in followers:
            loyal.append({
                "user": user,
                "score": score
            })

    return loyal