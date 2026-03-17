from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
from werkzeug.utils import secure_filename
import threading
import tempfile
import os
import time
import requests as http_requests

# Cloudinary
import cloudinary
import cloudinary.uploader
import cloudinary.utils

# Parsing — Instagram
from parser.zip_reader import read_instagram_zip
from parser.connections_parser import parse_connections
from parser.media_parser import parse_media_stats

# Parsing — Snapchat
from parser.snapchat_parser import parse_snapchat_export

# Utils
from utils.cache_manager import create_dashboard, get_dashboard
from utils.upload_validator import validate_upload, validate_file_size, validate_zip, check_zip_safety
from utils.reverse_search_links import reverse_search_urls
from utils.csv_exporter import export_followers_csv, export_following_csv, export_not_following_back_csv
from utils.snapchat_exporter import export_friends_csv, export_blocked_csv, export_chat_csv

# Analytics — Instagram
from analytics.relationship_analysis import relationship_stats
from analytics.ghost_analysis import ghost_followers
from analytics.ranking_analysis import interaction_ranking, loyal_followers


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

# ─────────────────────────────────────────────
#  CLOUDINARY CONFIG
# ─────────────────────────────────────────────

cloudinary.config(
    cloud_name="dpremvspd",
    api_key="518213445682397",
    api_secret="MXJuAYaxa6hVVmOo0zqvREhzVa4",
)

processing_jobs = {}


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _expired():
    return render_template("index.html", error="Session expired — please upload your export again.", snap_dashboard_id=None)


# ─────────────────────────────────────────────
#  INSTAGRAM — background worker
# ─────────────────────────────────────────────

def analyze_instagram_zip(job_id, zip_path):
    try:
        validate_zip(zip_path)
        check_zip_safety(zip_path)
        folder       = read_instagram_zip(zip_path)
        connections, export_type = parse_connections(folder)
        analysis     = relationship_stats(connections)
        ghosts       = ghost_followers(connections)
        ranking      = interaction_ranking(connections)
        loyal        = loyal_followers(connections)
        dashboard_id = create_dashboard({
            "type":        "instagram",
            "connections": connections,
            "analysis":    analysis,
            "export_type": export_type,
            "folder":      folder,
            "ghosts":      ghosts,
            "ranking":     ranking,
            "loyal":       loyal,
        })
        processing_jobs[job_id] = dashboard_id
    except Exception as e:
        processing_jobs[job_id] = {"error": str(e)}
    finally:
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
        except Exception:
            pass


# ─────────────────────────────────────────────
#  SNAPCHAT — background worker
# ─────────────────────────────────────────────

def analyze_snapchat_zip(job_id, zip_path):
    try:
        validate_zip(zip_path)
        check_zip_safety(zip_path)
        folder       = read_instagram_zip(zip_path)
        data         = parse_snapchat_export(folder)
        dashboard_id = create_dashboard({
            "type":   "snapchat",
            "data":   data,
            "folder": folder,
        })
        processing_jobs[job_id] = dashboard_id
    except Exception as e:
        processing_jobs[job_id] = {"error": str(e)}
    finally:
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
        except Exception:
            pass


# ─────────────────────────────────────────────
#  CLOUDINARY ROUTES
# ─────────────────────────────────────────────

@app.route("/get-upload-signature")
def get_upload_signature():
    return jsonify({
        "cloud_name": "dpremvspd",
        "api_key": "518213445682397",
        "upload_preset": "instalens_upload",
    })


@app.route("/process-from-cloudinary", methods=["POST"])
def process_from_cloudinary():
    data      = request.get_json()
    public_id = data.get("public_id")
    platform  = data.get("platform", "instagram")

    if not public_id:
        return jsonify({"error": "No public_id provided"}), 400

    try:
        # Generate a signed URL so server can download the file
        url = f"https://api.cloudinary.com/v1_1/dpremvspd/resources/raw/upload/{public_id}"
        response = http_requests.get(
            url,
            auth=("518213445682397", "MXJuAYaxa6hVVmOo0zqvREhzVa4"),
            stream=True,
            timeout=300
        )
        response.raise_for_status()

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        for chunk in response.iter_content(chunk_size=65536):
            temp_file.write(chunk)
        temp_file.flush()
        temp_file.close()

        # Delete from Cloudinary immediately after downloading
        try:
            cloudinary.uploader.destroy(public_id, resource_type="raw", invalidate=True)
        except Exception:
            pass

        try:
            validate_file_size(temp_file.name)
        except ValueError as e:
            os.unlink(temp_file.name)
            return jsonify({"error": str(e)}), 400

        job_id = os.urandom(16).hex()
        if platform == "snapchat":
            threading.Thread(target=analyze_snapchat_zip, args=(job_id, temp_file.name)).start()
        else:
            threading.Thread(target=analyze_instagram_zip, args=(job_id, temp_file.name)).start()

        return jsonify({"job_id": job_id})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/cleanup-cloudinary", methods=["POST"])
def cleanup_cloudinary():
    try:
        data      = request.get_json(force=True, silent=True) or {}
        public_id = data.get("public_id")
        if public_id:
            cloudinary.uploader.destroy(public_id, resource_type="raw", invalidate=True)
    except Exception:
        pass
    return "", 204


# ─────────────────────────────────────────────
#  SHARED PROCESSING ROUTE
# ─────────────────────────────────────────────

@app.route("/processing/<job_id>")
def processing(job_id):
    result = processing_jobs.get(job_id)
    if result is None:
        return render_template("processing.html")
    if isinstance(result, dict) and "error" in result:
        return render_template("index.html", error=f"Processing failed: {result['error']}")
    stored = get_dashboard(result)
    if stored and stored.get("type") == "snapchat":
        return redirect(url_for("snapchat_dashboard", dashboard_id=result))
    return redirect(url_for("dashboard", dashboard_id=result))


# ─────────────────────────────────────────────
#  INSTAGRAM ROUTES
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", error=None, snap_dashboard_id=None)


@app.route("/dashboard/<dashboard_id>")
def dashboard(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("dashboard.html", dashboard=data, dashboard_id=dashboard_id, snap_dashboard_id=None)


@app.route("/connections/<dashboard_id>")
def connections(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("connections.html", dashboard=data, dashboard_id=dashboard_id, snap_dashboard_id=None)


@app.route("/network/<dashboard_id>")
def network(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("network.html", dashboard=data, dashboard_id=dashboard_id, snap_dashboard_id=None)


@app.route("/tables/<dashboard_id>")
def tables(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("tables.html", dashboard=data, dashboard_id=dashboard_id, snap_dashboard_id=None)


@app.route("/media/<dashboard_id>")
def media_stats(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return redirect(url_for("index"))
    folder = data.get("folder")
    media  = parse_media_stats(folder) if folder else {}
    return render_template("media_report.html", media=media, dashboard=data, dashboard_id=dashboard_id, snap_dashboard_id=None)


@app.route("/export/followers/<dashboard_id>")
def export_followers(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return Response(export_followers_csv(data["connections"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=followers.csv"})


@app.route("/export/following/<dashboard_id>")
def export_following(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return Response(export_following_csv(data["connections"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=following.csv"})


@app.route("/export/notfollowingback/<dashboard_id>")
def export_not_following_back(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return Response(export_not_following_back_csv(data["connections"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=not_following_back.csv"})


@app.route("/media-analysis", methods=["GET", "POST"])
def media_analysis():
    if request.method == "POST":
        file = request.files.get("media")
        if not file or file.filename == "":
            return render_template("media_upload.html", error="No file selected.")
        original_name = secure_filename(file.filename)
        ext = os.path.splitext(original_name)[1].lower()
        if ext in {".zip", ".tar", ".gz", ".rar", ".7z"}:
            return render_template("media_upload.html", error="Please upload an image or video file.")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        file.save(temp_file.name)
        try:
            from analytics.forensic_analyzer import analyze_file
            report       = analyze_file(temp_file.name)
            report["filename"] = original_name
            search_links = reverse_search_urls(temp_file.name)
            return render_template("metadata_report.html", report=report, filename=original_name, search_links=search_links)
        except Exception as e:
            return render_template("media_upload.html", error=f"Analysis failed: {str(e)}")
        finally:
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass
    return render_template("media_upload.html", error=None, snap_dashboard_id=None)


@app.route("/metadata-analyzer", methods=["GET", "POST"])
def metadata_analyzer():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return render_template("metadata_upload.html", error="No file selected.")
        original_name = secure_filename(file.filename)
        ext = os.path.splitext(original_name)[1].lower()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        file.save(temp_file.name)
        try:
            from analytics.forensic_analyzer import analyze_file
            report = analyze_file(temp_file.name)
            return render_template("metadata_report.html", report=report, filename=original_name)
        except Exception as e:
            return render_template("metadata_upload.html", error=str(e))
        finally:
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass
    return render_template("metadata_upload.html", error=None, snap_dashboard_id=None)


@app.route("/api/search/<dashboard_id>")
def api_search(dashboard_id):
    query = request.args.get("q", "").strip().lower()
    if not query or len(query) < 2:
        return jsonify({"results": []})
    data = get_dashboard(dashboard_id)
    if not data:
        return jsonify({"results": []})
    connections   = data.get("connections", {})
    followers_set = set(connections.get("followers", []))
    following_set = set(connections.get("following", []))
    results, seen = [], set()
    for user in sorted(followers_set.union(following_set)):
        if query in user.lower() and user not in seen:
            seen.add(user)
            if user in followers_set and user in following_set:
                label = "Mutual"
            elif user in following_set:
                label = "Not Following Back"
            else:
                label = "Fan"
            results.append({"user": user, "label": label})
    return jsonify({"results": results[:20]})


# ─────────────────────────────────────────────
#  SNAPCHAT ROUTES
# ─────────────────────────────────────────────

@app.route("/snapchat", methods=["GET"])
def snapchat_upload():
    return render_template("snapchat_upload.html", error=None)


@app.route("/snapchat/debug/<dashboard_id>")
def snapchat_debug(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return "Session expired"
    from parser.snapchat_debug import debug_snapchat_export
    folder = stored.get("folder", "")
    report = debug_snapchat_export(folder)
    return f"<pre style='font-size:12px;padding:20px;'>{report}</pre>"


@app.route("/snapchat/dashboard/<dashboard_id>")
def snapchat_dashboard(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired — please upload your export again.")
    return render_template("snapchat_dashboard.html", data=stored["data"], dashboard_id=dashboard_id,
                           snap_dashboard_id=dashboard_id)


@app.route("/snapchat/friends/<dashboard_id>")
def snapchat_friends(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired — please upload your export again.")
    return render_template("snapchat_friends.html", data=stored["data"], dashboard_id=dashboard_id,
                           snap_dashboard_id=dashboard_id)


@app.route("/snapchat/memories/<dashboard_id>")
def snapchat_memories(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired — please upload your export again.")
    return render_template("snapchat_memories.html", data=stored["data"], dashboard_id=dashboard_id,
                           snap_dashboard_id=dashboard_id)


@app.route("/snapchat/chats/<dashboard_id>")
def snapchat_chats(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired — please upload your export again.")
    return render_template("snapchat_chats.html", data=stored["data"], dashboard_id=dashboard_id,
                           snap_dashboard_id=dashboard_id)


@app.route("/snapchat/snaps/<dashboard_id>")
def snapchat_snaps(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired — please upload your export again.")
    return render_template("snapchat_snaps.html", data=stored["data"], dashboard_id=dashboard_id,
                           snap_dashboard_id=dashboard_id)


@app.route("/snapchat/activity/<dashboard_id>")
def snapchat_activity(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired — please upload your export again.")
    return render_template("snapchat_activity.html", data=stored["data"], dashboard_id=dashboard_id,
                           snap_dashboard_id=dashboard_id)


@app.route("/snapchat/export/friends/<dashboard_id>")
def snapchat_export_friends_csv(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired.")
    return Response(export_friends_csv(stored["data"]["friends"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=snapchat_friends.csv"})


@app.route("/snapchat/export/blocked/<dashboard_id>")
def snapchat_export_blocked_csv(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired.")
    return Response(export_blocked_csv(stored["data"]["friends"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=snapchat_blocked.csv"})


@app.route("/snapchat/export/chats/<dashboard_id>")
def snapchat_export_chat_csv(dashboard_id):
    stored = get_dashboard(dashboard_id)
    if not stored:
        return render_template("snapchat_upload.html", error="Session expired.")
    return Response(export_chat_csv(stored["data"]["chat_history"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=snapchat_chats.csv"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)