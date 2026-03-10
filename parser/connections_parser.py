
def parse_connections(data):

    followers=[]
    following=[]

    for file,content in data.items():

        if "followers" in file and isinstance(content,list):
            for i in content:
                try:
                    followers.append(i["string_list_data"][0]["value"])
                except:
                    pass

        if "following" in file and isinstance(content,dict):
            for i in content.get("relationships_following",[]):
                following.append(i.get("title"))

    return {
        "followers":followers,
        "following":following
    }
