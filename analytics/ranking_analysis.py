
import random

def follower_ranking(data):
    followers=data["followers"]
    ranking=[]
    for f in followers:
        ranking.append({
            "username":f,
            "score":random.randint(1,100)
        })
    ranking=sorted(ranking,key=lambda x:x["score"],reverse=True)
    return ranking[:50]
