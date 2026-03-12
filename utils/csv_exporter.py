import csv
import io


def export_followers_csv(data):

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow(["Username"])

    for user in data.get("followers", []):
        writer.writerow([user])

    return output.getvalue()


def export_following_csv(data):

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow(["Username"])

    for user in data.get("following", []):
        writer.writerow([user])

    return output.getvalue()