from flask import Flask, render_template, request, redirect, url_for, Response
import threading
import tempfile
import os

# Parsing
from parser.zip_reader import read_instagram_zip
from parser.connections_parser import parse_connections

# Utils
from utils.cache_manager import create_dashboard, get_dashboard
from utils.upload_validator import validate_upload, validate_zip, check_zip_safety
from utils.reverse_search_links import reverse_search_urls
from utils.csv_exporter import export_followers_csv

# Analytics
from analytics.media_provenance import analyze_media


app = Flask(__name__)

# Upload limit (1GB)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

# Background job tracker
processing_jobs = {}


# --------------------------------
# ZIP ANALYSIS WORKER
# --------------------------------
def analyze_zip(job_id, zip_path):

    try:

        # Validate uploaded zip
        validate_zip(zip_path)
        check_zip_safety(zip_path)

        # Extract zip
        folder = read_instagram_zip(zip_path)

        # Parse connections
        connections, export_type = parse_connections(folder)

        # Store dashboard in cache
        dashboard_id = create_dashboard({
            "connections": connections,
            "export_type": export_type
        })

        processing_jobs[job_id] = dashboard_id

    except Exception as e:

        processing_jobs[job_id] = {"error": str(e)}


# --------------------------------
# HOME PAGE
# --------------------------------
@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        file = request.files.get("file")

        if not file:
            return "No file uploaded"

        # Validate upload
        validate_upload(file)

        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)

        # Create job
        job_id = os.urandom(16).hex()

        # Run background analysis
        thread = threading.Thread(
            target=analyze_zip,
            args=(job_id, temp_file.name)
        )
        thread.start()

        return redirect(url_for("processing", job_id=job_id))

    return render_template("index.html")


# --------------------------------
# PROCESSING PAGE
# --------------------------------
@app.route("/processing/<job_id>")
def processing(job_id):

    result = processing_jobs.get(job_id)

    if result is None:
        return render_template("processing.html")

    if isinstance(result, dict) and "error" in result:
        return result["error"]

    return redirect(url_for("dashboard", dashboard_id=result))


# --------------------------------
# DASHBOARD
# --------------------------------
@app.route("/dashboard/<dashboard_id>")
def dashboard(dashboard_id):

    dashboard = get_dashboard(dashboard_id)

    if not dashboard:
        return "Dashboard expired"

    return render_template(
        "dashboard.html",
        dashboard=dashboard,
        dashboard_id=dashboard_id
    )


# --------------------------------
# CONNECTIONS PAGE
# --------------------------------
@app.route("/connections/<dashboard_id>")
def connections(dashboard_id):

    dashboard = get_dashboard(dashboard_id)

    if not dashboard:
        return "Dashboard expired"

    return render_template(
        "connections.html",
        dashboard=dashboard,
        dashboard_id=dashboard_id
    )


# --------------------------------
# NETWORK GRAPH PAGE
# --------------------------------
@app.route("/network/<dashboard_id>")
def network(dashboard_id):

    dashboard = get_dashboard(dashboard_id)

    if not dashboard:
        return "Dashboard expired"

    return render_template(
        "network.html",
        dashboard=dashboard,
        dashboard_id=dashboard_id
    )


# --------------------------------
# TABLES PAGE
# --------------------------------
@app.route("/tables/<dashboard_id>")
def tables(dashboard_id):

    dashboard = get_dashboard(dashboard_id)

    if not dashboard:
        return "Dashboard expired"

    return render_template(
        "tables.html",
        dashboard=dashboard,
        dashboard_id=dashboard_id
    )


# --------------------------------
# EXPORT FOLLOWERS CSV
# --------------------------------
@app.route("/export/followers/<dashboard_id>")
def export_followers(dashboard_id):

    dashboard = get_dashboard(dashboard_id)

    if not dashboard:
        return "Dashboard expired"

    csv_data = export_followers_csv(dashboard["connections"])

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=followers.csv"
        }
    )


# --------------------------------
# MEDIA PROVENANCE ANALYZER
# --------------------------------
@app.route("/media-analysis", methods=["GET", "POST"])
def media_analysis():

    if request.method == "POST":

        file = request.files.get("media")

        if not file:
            return "No file uploaded"

        # Save media temporarily
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)

        # Analyze media
        report = analyze_media(temp_file.name)

        # Generate reverse search links
        search_links = reverse_search_urls(temp_file.name)

        return render_template(
            "media_report.html",
            report=report,
            search_links=search_links
        )

    return render_template("media_upload.html")


# --------------------------------
# RUN SERVER
# --------------------------------
if __name__ == "__main__":
    app.run(debug=True)

# --------------------------------
# DEBUG — show file tree from extracted zip
# --------------------------------
@app.route("/debug/<dashboard_id>")
def debug_dashboard(dashboard_id):
    d = get_dashboard(dashboard_id)
    if not d:
        return "expired"
    out = "<pre>"
    conn = d.get("connections", {})
    out += "followers: %d\n" % len(conn.get("followers", []))
    out += "following: %d\n" % len(conn.get("following", []))
    out += "likes: %d\n" % len(conn.get("likes", []))
    out += "comments: %d\n" % len(conn.get("comments", []))
    out += "\nSample followers:\n" + str(conn.get("followers", [])[:5])
    out += "\nSample following:\n" + str(conn.get("following", [])[:5])
    out += "</pre>"
    return out