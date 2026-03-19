from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
from werkzeug.utils import secure_filename
import threading
import tempfile
import os
import time
import requests as http_requests
import logging
from threading import Lock
import socket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

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
#  CLOUDINARY CONFIG - DETECT LOCALHOST PROPERLY
# ─────────────────────────────────────────────

cloudinary_enabled = False

# ✅ METHOD 1: Check if explicitly told to use local mode
if os.environ.get('FORCE_LOCAL_MODE') == 'true' or os.environ.get('SKIP_CLOUDINARY') == 'true':
    logger.info("🔵 FORCE_LOCAL_MODE detected - Forcing LOCAL UPLOADS ONLY")
    cloudinary_enabled = False

else:
    # ✅ METHOD 2: Detect if running on localhost by checking hostname
    try:
        hostname = socket.gethostname()
        local_ips = socket.gethostbyname_ex(hostname)[2]

        logger.info(f"🔍 Server Hostname: {hostname}")
        logger.info(f"🔍 Server IPs: {local_ips}")

        is_localhost_machine = any(
            ip.startswith('127.') or
            ip.startswith('192.168.') or
            ip.startswith('10.') or
            ip.startswith('172.')
            for ip in local_ips
        ) or hostname.lower() in ['localhost', 'desktop', 'pc']

        logger.info(f"🔍 Is Local Machine: {is_localhost_machine}")

    except Exception as e:
        logger.warning(f"⚠️  Could not detect hostname: {str(e)}")
        is_localhost_machine = False

    if is_localhost_machine:
        logger.info("🔵 LOCAL MACHINE DETECTED - Forcing LOCAL UPLOADS ONLY")
        logger.info("   Even though Cloudinary credentials may exist in .env")
        cloudinary_enabled = False
    else:
        has_cloudinary_credentials = bool(
            os.environ.get("CLOUDINARY_CLOUD_NAME") and
            os.environ.get("CLOUDINARY_API_KEY") and
            os.environ.get("CLOUDINARY_API_SECRET")
        )

        if has_cloudinary_credentials:
            try:
                cloudinary.config(
                    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
                    api_key=os.environ.get("CLOUDINARY_API_KEY"),
                    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
                )
                cloudinary_enabled = True
                logger.info("✅ PRODUCTION MODE - Cloudinary configured successfully")
                logger.info(f"   Cloud: {os.environ.get('CLOUDINARY_CLOUD_NAME')}")
            except Exception as e:
                logger.warning(f"⚠️  Cloudinary config failed: {str(e)}")
                cloudinary_enabled = False
        else:
            logger.info("🔵 LOCAL MODE - Cloudinary credentials not found")
            logger.info("   Using LOCAL UPLOADS ONLY")
            cloudinary_enabled = False


# ─────────────────────────────────────────────
#  THREAD-SAFE JOB TRACKING
# ─────────────────────────────────────────────

processing_jobs = {}
jobs_lock = Lock()


def set_job_status(job_id, status, dashboard_id=None, error=None):
    """Thread-safe job status update"""
    with jobs_lock:
        processing_jobs[job_id] = {
            "status": status,
            "dashboard_id": dashboard_id,
            "error": error,
            "timestamp": time.time()
        }


def get_job_status(job_id):
    """Thread-safe job status retrieval"""
    with jobs_lock:
        return processing_jobs.get(job_id)


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
        set_job_status(job_id, "complete", dashboard_id=dashboard_id)
    except Exception as e:
        logger.error(f"Instagram analysis error: {str(e)}")
        set_job_status(job_id, "error", error=str(e))
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
        set_job_status(job_id, "complete", dashboard_id=dashboard_id)
    except Exception as e:
        logger.error(f"Snapchat analysis error: {str(e)}")
        set_job_status(job_id, "error", error=str(e))
    finally:
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
        except Exception:
            pass


# ─────────────────────────────────────────────
#  SHARED PROCESSING ROUTE
# ─────────────────────────────────────────────

@app.route("/processing/<job_id>")
def processing(job_id):
    return render_template("processing.html", job_id=job_id, snap_dashboard_id=None)


@app.route("/api/job-status/<job_id>")
def api_job_status(job_id):
    """Polling endpoint for processing.html to check job status."""
    status_data = get_job_status(job_id)
    if status_data is None:
        return jsonify({"status": "processing"})

    if status_data.get("status") == "error":
        return jsonify({"status": "error", "error": status_data.get("error", "Unknown error")})

    if status_data.get("status") == "complete" and status_data.get("dashboard_id"):
        return jsonify({"status": "complete", "dashboard_id": status_data["dashboard_id"]})

    return jsonify({"status": "processing"})


# ─────────────────────────────────────────────
#  UPLOAD ROUTES — Local & Cloudinary
# ─────────────────────────────────────────────

@app.route("/upload-local", methods=["POST"])
def upload_local():
    """Handle direct local file upload (used when Cloudinary is disabled)."""
    file = request.files.get("file")
    platform = request.form.get("platform", "instagram")

    if not file or not file.filename:
        return jsonify({"error": "No file selected."}), 400

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    file.save(temp_file.name)
    temp_file.close()

    try:
        validate_file_size(temp_file.name)
    except ValueError as e:
        try:
            os.unlink(temp_file.name)
        except Exception:
            pass
        return jsonify({"error": str(e)}), 400

    job_id = os.urandom(16).hex()
    set_job_status(job_id, "processing")

    if platform == "snapchat":
        threading.Thread(target=analyze_snapchat_zip, args=(job_id, temp_file.name), daemon=True).start()
    else:
        threading.Thread(target=analyze_instagram_zip, args=(job_id, temp_file.name), daemon=True).start()

    return jsonify({"job_id": job_id})


@app.route("/get-upload-signature")
def get_upload_signature():
    """Return Cloudinary signed upload params, or signal local-only mode."""
    if not cloudinary_enabled:
        return jsonify({"local_only": True})

    try:
        timestamp = int(time.time())
        params_to_sign = {"timestamp": timestamp}
        signature = cloudinary.utils.api_sign_request(
            params_to_sign,
            os.environ.get("CLOUDINARY_API_SECRET")
        )
        return jsonify({
            "signature":  signature,
            "timestamp":  timestamp,
            "cloud_name": os.environ.get("CLOUDINARY_CLOUD_NAME"),
            "api_key":    os.environ.get("CLOUDINARY_API_KEY"),
            "local_only": False,
        })
    except Exception as e:
        logger.error(f"Signature generation error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/process-from-cloudinary", methods=["POST"])
def process_from_cloudinary():
    """Download from Cloudinary and kick off background analysis."""
    if not cloudinary_enabled:
        return jsonify({"error": "Cloudinary is not enabled on this server."}), 400

    body = request.get_json(silent=True) or {}
    public_id = body.get("public_id")
    platform  = body.get("platform", "instagram")

    if not public_id:
        return jsonify({"error": "Missing public_id"}), 400

    try:
        url = cloudinary.utils.cloudinary_url(public_id, resource_type="raw")[0]
        response = http_requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.close()

        try:
            cloudinary.uploader.destroy(public_id, resource_type="raw")
        except Exception as e:
            logger.warning(f"Could not delete Cloudinary asset {public_id}: {e}")

    except Exception as e:
        logger.error(f"Cloudinary download error: {str(e)}")
        return jsonify({"error": f"Failed to retrieve file from Cloudinary: {str(e)}"}), 500

    job_id = os.urandom(16).hex()
    set_job_status(job_id, "processing")

    if platform == "snapchat":
        threading.Thread(target=analyze_snapchat_zip, args=(job_id, temp_file.name), daemon=True).start()
    else:
        threading.Thread(target=analyze_instagram_zip, args=(job_id, temp_file.name), daemon=True).start()

    return jsonify({"job_id": job_id})


@app.route("/cleanup-cloudinary", methods=["POST"])
def cleanup_cloudinary():
    """Beacon endpoint to clean up abandoned Cloudinary uploads."""
    if not cloudinary_enabled:
        return "", 204

    try:
        import json
        body = request.get_data(as_text=True)
        data = json.loads(body)
        public_id = data.get("public_id")
        if public_id:
            cloudinary.uploader.destroy(public_id, resource_type="raw")
    except Exception as e:
        logger.warning(f"Cleanup beacon error: {str(e)}")

    return "", 204


# ─────────────────────────────────────────────
#  INSTAGRAM ROUTES
# ─────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def index():
    # Legacy POST fallback (form submit without JS)
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            return render_template("index.html", error="Please select a file before submitting.", snap_dashboard_id=None)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        file.save(temp_file.name)
        temp_file.close()
        try:
            validate_file_size(temp_file.name)
        except ValueError as e:
            os.unlink(temp_file.name)
            return render_template("index.html", error=str(e), snap_dashboard_id=None)
        job_id = os.urandom(16).hex()
        set_job_status(job_id, "processing")
        threading.Thread(target=analyze_instagram_zip, args=(job_id, temp_file.name), daemon=True).start()
        return redirect(url_for("processing", job_id=job_id))
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
        return _expired()
    folder = data.get("folder")
    media  = parse_media_stats(folder) if folder else {}
    return render_template("media_report.html", media=media, dashboard=data, dashboard_id=dashboard_id, snap_dashboard_id=None)


# Alias so old /media-stats/ links still work
@app.route("/media-stats/<dashboard_id>")
def media_stats_alias(dashboard_id):
    return redirect(url_for("media_stats", dashboard_id=dashboard_id))


@app.route("/following/<dashboard_id>")
def following(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("tables.html", dashboard=data, dashboard_id=dashboard_id, table="following", snap_dashboard_id=None)


@app.route("/followers/<dashboard_id>")
def followers(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("tables.html", dashboard=data, dashboard_id=dashboard_id, table="followers", snap_dashboard_id=None)


@app.route("/not-following-back/<dashboard_id>")
def not_following_back(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("tables.html", dashboard=data, dashboard_id=dashboard_id, table="not_following_back", snap_dashboard_id=None)


# ─────────────────────────────────────────────
#  CSV EXPORT ROUTES
# ─────────────────────────────────────────────

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


@app.route("/export/not-following-back/<dashboard_id>")
def export_not_following_back(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return Response(export_not_following_back_csv(data["connections"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=not_following_back.csv"})


# ─────────────────────────────────────────────
#  MEDIA / METADATA ANALYSIS
# ─────────────────────────────────────────────

@app.route("/media-analysis", methods=["GET", "POST"])
def media_analysis():
    if request.method == "POST":
        file = request.files.get("media")
        if not file or file.filename == "":
            return render_template("media_upload.html", error="No file selected.", snap_dashboard_id=None)

        original_name = secure_filename(file.filename)
        ext = os.path.splitext(original_name)[1].lower()

        if ext in {".zip", ".tar", ".gz", ".rar", ".7z"}:
            return render_template("media_upload.html", error="Please upload an image or video file.", snap_dashboard_id=None)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        try:
            file.save(temp_file.name)
            temp_file.close()

            from analytics.forensic_analyzer import analyze_file
            report = analyze_file(temp_file.name)
            report["filename"] = original_name
            search_links = reverse_search_urls(temp_file.name)
            return render_template("metadata_report.html", report=report, filename=original_name,
                                   search_links=search_links, snap_dashboard_id=None)

        except Exception as e:
            logger.error(f"Media analysis error: {str(e)}")
            return render_template("media_upload.html", error=f"Analysis failed: {str(e)}", snap_dashboard_id=None)

        finally:
            try:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
            except Exception as e:
                logger.warning(f"Could not clean up temp file: {str(e)}")

    return render_template("media_upload.html", error=None, snap_dashboard_id=None)


@app.route("/metadata-analyzer", methods=["GET", "POST"])
def metadata_analyzer():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return render_template("metadata_upload.html", error="No file selected.", snap_dashboard_id=None)

        original_name = secure_filename(file.filename)
        ext = os.path.splitext(original_name)[1].lower()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)

        try:
            file.save(temp_file.name)
            temp_file.close()

            from analytics.forensic_analyzer import analyze_file
            report = analyze_file(temp_file.name)
            return render_template("metadata_report.html", report=report, filename=original_name,
                                   snap_dashboard_id=None)

        except Exception as e:
            logger.error(f"Metadata analysis error: {str(e)}")
            return render_template("metadata_upload.html", error=str(e), snap_dashboard_id=None)

        finally:
            try:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
            except Exception as e:
                logger.warning(f"Could not clean up temp file: {str(e)}")

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

@app.route("/snapchat", methods=["GET", "POST"])
def snapchat_upload():
    if request.method == "POST":
        # Legacy form-submit fallback (no JS)
        file = request.files.get("file")
        if not file or not file.filename:
            return render_template("snapchat_upload.html", error="Please select a file before submitting.")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        file.save(temp_file.name)
        temp_file.close()
        try:
            validate_file_size(temp_file.name)
        except ValueError as e:
            os.unlink(temp_file.name)
            return render_template("snapchat_upload.html", error=str(e))
        job_id = os.urandom(16).hex()
        set_job_status(job_id, "processing")
        threading.Thread(target=analyze_snapchat_zip, args=(job_id, temp_file.name), daemon=True).start()
        return redirect(url_for("processing", job_id=job_id))
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