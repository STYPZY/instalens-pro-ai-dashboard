import csv
import io


def export_followers_csv(data):

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username", "Type"])

    followers_set = set(data.get("followers", []))
    following_set = set(data.get("following", []))

    for user in sorted(data.get("followers", [])):
        label = "Mutual" if user in following_set else "Fan"
        writer.writerow([user, label])

    return output.getvalue()


def export_following_csv(data):

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username", "Type"])

    followers_set = set(data.get("followers", []))

    for user in sorted(data.get("following", [])):
        label = "Mutual" if user in followers_set else "Not Following Back"
        writer.writerow([user, label])

    return output.getvalue()


def export_not_following_back_csv(data):

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username"])

    followers_set = set(data.get("followers", []))
    not_following_back = [u for u in data.get("following", []) if u not in followers_set]

    for user in sorted(not_following_back):
        writer.writerow([user])

    return output.getvalue()