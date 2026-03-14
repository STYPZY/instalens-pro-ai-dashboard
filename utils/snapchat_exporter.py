import csv
import io


def export_friends_csv(data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username", "Display Name", "Added Date", "Source"])
    for f in sorted(data.get("friends", []), key=lambda x: x.get("username", "")):
        writer.writerow([f.get("username", ""), f.get("display_name", ""),
                         f.get("added_date", ""), f.get("source", "")])
    return output.getvalue()


def export_blocked_csv(data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Username", "Blocked Date"])
    for f in data.get("blocked", []):
        writer.writerow([f.get("username", ""), f.get("blocked_date", "")])
    return output.getvalue()


def export_chat_csv(chat_data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Sent", "Received", "Total", "Media", "Last Active"])
    for c in chat_data.get("conversations", []):
        total = c.get("sent", 0) + c.get("received", 0)
        writer.writerow([c.get("name", ""), c.get("sent", 0), c.get("received", 0),
                         total, c.get("media", 0), c.get("last_active", "")])
    return output.getvalue()