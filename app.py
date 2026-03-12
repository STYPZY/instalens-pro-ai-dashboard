from flask import Flask, render_template, request, session
from parser.zip_reader import read_instagram_zip
from parser.connections_parser import parse_connections
from analytics.relationship_analysis import relationship_stats
from analytics.ghost_analysis import ghost_followers
from analytics.ranking_analysis import follower_ranking

import uuid
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "instalens_secret_key")

app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

user_dashboards = {}

def empty_dashboard():
    return {
        "relationship": {
            "not_following_back_list": [],
            "fans_list": []
        },
        "ghosts": [],
        "ranking": [],
        "followers": [],
        "following": []
    }

def get_dashboard():
    uid = session.get("uid")
    if uid and uid in user_dashboards:
        return user_dashboards[uid]
    return empty_dashboard()

def render_dashboard(page):
    return render_template(page, dashboard=get_dashboard())


@app.route("/", methods=["GET","POST"])
def dashboard_page():

    if "uid" not in session:
        session["uid"] = str(uuid.uuid4())

    uid = session["uid"]

    if request.method == "POST":

        file = request.files.get("file")

        if file and file.filename.endswith(".zip"):

            raw = read_instagram_zip(file)
            data = parse_connections(raw)

            relationship = relationship_stats(data)
            ghosts = ghost_followers(data)
            ranking = follower_ranking(data)

            dashboard = {
                "relationship": relationship,
                "ghosts": ghosts,
                "ranking": ranking,
                "followers": data.get("followers", []),
                "following": data.get("following", [])
            }

            user_dashboards[uid] = dashboard

            if len(user_dashboards) > 100:
                user_dashboards.clear()

    return render_dashboard("dashboard.html")


@app.route("/tables")
def tables():
    return render_dashboard("tables.html")


@app.route("/network")
def network():
    return render_dashboard("network.html")


@app.route("/connections")
def connections():
    return render_dashboard("connections.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)