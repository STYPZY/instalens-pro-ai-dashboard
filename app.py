from flask import Flask, render_template, request
from parser.zip_reader import read_instagram_zip
from parser.connections_parser import parse_connections
from analytics.relationship_analysis import relationship_stats
from analytics.ghost_analysis import ghost_followers
from analytics.ranking_analysis import follower_ranking

app = Flask(__name__)

# Default safe dashboard
dashboard = {
    "relationship": {
        "not_following_back_list": [],
        "fans_list": []
    },
    "ghosts": [],
    "ranking": [],
    "followers": [],
    "following": []
}

@app.route("/", methods=["GET","POST"])
def dashboard_page():
    global dashboard

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

    return render_template("dashboard.html", dashboard=dashboard)


@app.route("/tables")
def tables():
    return render_template("tables.html", dashboard=dashboard)


@app.route("/network")
def network():
    return render_template("network.html", dashboard=dashboard)


@app.route("/connections")
def connections():
    return render_template("connections.html", dashboard=dashboard)


if __name__ == "__main__":
    app.run(debug=True)