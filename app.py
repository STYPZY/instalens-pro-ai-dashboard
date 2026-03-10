from flask import Flask, render_template, request, session
from parser.zip_reader import read_instagram_zip
from parser.connections_parser import parse_connections
from analytics.relationship_analysis import relationship_stats
from analytics.ghost_analysis import ghost_followers
from analytics.ranking_analysis import follower_ranking

import uuid

app = Flask(__name__)
app.secret_key = "instalens_secret_key"

# store dashboards for multiple users
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


@app.route("/", methods=["GET","POST"])
def dashboard_page():

    if "uid" not in session:
        session["uid"] = str(uuid.uuid4())

    uid = session["uid"]

    if request.method == "POST":

        file = request.files.get("file")

        if file:

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

    dashboard = get_dashboard()

    return render_template("dashboard.html", dashboard=dashboard)


@app.route("/tables")
def tables():
    dashboard = get_dashboard()
    return render_template("tables.html", dashboard=dashboard)


@app.route("/network")
def network():
    dashboard = get_dashboard()
    return render_template("network.html", dashboard=dashboard)


@app.route("/connections")
def connections():
    dashboard = get_dashboard()
    return render_template("connections.html", dashboard=dashboard)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)