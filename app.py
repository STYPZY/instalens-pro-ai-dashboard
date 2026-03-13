from flask import Flask, render_template, request, redirect, url_for, Response
from werkzeug.utils import secure_filename
import threading
import tempfile
import os

# Parsing
from parser.zip_reader import read_instagram_zip
from parser.connections_parser import parse_connections
from parser.media_parser import parse_media_stats

# Utils
from utils.cache_manager import create_dashboard, get_dashboard
from utils.upload_validator import validate_upload, validate_zip, check_zip_safety
from utils.reverse_search_links import reverse_search_urls
from utils.csv_exporter import export_followers_csv

# Analytics
from analytics.media_provenance import analyze_media
from analytics.relationship_analysis import relationship_stats


app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

processing_jobs = {}


def analyze_zip(job_id, zip_path):

    try:

        validate_zip(zip_path)
        check_zip_safety(zip_path)

        folder = read_instagram_zip(zip_path)

        connections, export_type = parse_connections(folder)

        analysis = relationship_stats(connections)

        dashboard_id = create_dashboard({
            "connections": connections,
            "analysis": analysis,
            "export_type": export_type,
            "folder": folder,
        })

        processing_jobs[job_id] = dashboard_id

    except Exception as e:

        processing_jobs[job_id] = {"error": str(e)}


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        file = request.files.get("file")

        if not file:
            return "No file uploaded"

        validate_upload(file)

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)

        job_id = os.urandom(16).hex()

        thread = threading.Thread(
            target=analyze_zip,
            args=(job_id, temp_file.name)
        )
        thread.start()

        return redirect(url_for("processing", job_id=job_id))

    return render_template("index.html")


@app.route("/processing/<job_id>")
def processing(job_id):

    result = processing_jobs.get(job_id)

    if result is None:
        return render_template("processing.html")

    if isinstance(result, dict) and "error" in result:
        return result["error"]

    return redirect(url_for("dashboard", dashboard_id=result))


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


@app.route("/media/<dashboard_id>")
def media_stats(dashboard_id):
    dashboard = get_dashboard(dashboard_id)
    if not dashboard:
        return redirect(url_for("index"))
    folder = dashboard.get("folder")
    media = parse_media_stats(folder) if folder else {}
    return render_template(
        "media_report.html",
        media=media,
        dashboard=dashboard,
        dashboard_id=dashboard_id
    )


@app.route("/media-analysis", methods=["GET", "POST"])
def media_analysis():

    if request.method == "POST":

        file = request.files.get("media")

        if not file or file.filename == "":
            return render_template("media_upload.html", error="No file selected.")

        original_name = secure_filename(file.filename)
        ext = os.path.splitext(original_name)[1].lower()

        BLOCKED = {".zip", ".tar", ".gz", ".rar", ".7z"}
        if ext in BLOCKED:
            return render_template("media_upload.html", error="Please upload an image or video file.")

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        file.save(temp_file.name)

        try:
            report = analyze_media(temp_file.name)
            report["filename"] = original_name

            search_links = reverse_search_urls(temp_file.name)

            return render_template(
                "media_report.html",
                report=report,
                search_links=search_links
            )
        except Exception as e:
            return render_template("media_upload.html", error=f"Analysis failed: {str(e)}")
        finally:
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass

    return render_template("media_upload.html", error=None)


if __name__ == "__main__":
    app.run(debug=True)