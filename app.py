from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
from werkzeug.utils import secure_filename
import threading
import tempfile
import os
import time
import requests as http_requests
import logging
from threading import Lock

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
#  CLOUDINARY CONFIG
# ─────────────────────────────────────────────

cloudinary_enabled = False
if os.environ.get("CLOUDINARY_CLOUD_NAME"):
    try:
        cloudinary.config(
            cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
            api_key=os.environ.get("CLOUDINARY_API_KEY"),
            api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
        )
        cloudinary_enabled = True
        logger.info("✅ Cloudinary configured successfully")
    except Exception as e:
        logger.warning(f"⚠️  Cloudinary config failed: {str(e)}")
else:
    logger.info("ℹ️  Cloudinary not configured - local uploads only")


# ─────────────────────────────────────────────
#  THREAD-SAFE JOB TRACKING
# ─────────────────────────────────────────────

processing_jobs = {}
jobs_lock = Lock()


def set_job_status(job_id, status):
    """Thread-safe job status update"""
    with jobs_lock:
        processing_jobs[job_id] = {
            "status": status,
            "timestamp": time.time()
        }


def get_job_status(job_id):
    """Thread-safe job status retrieval"""
    with jobs_lock:
        return processing_jobs.get(job_id)


def cleanup_old_jobs():
    """Remove jobs older than 30 minutes"""
    with jobs_lock:
        current_time = time.time()
        expired = [jid for jid, data in processing_jobs.items() 
                  if current_time - data.get("timestamp", current_time) > 1800]
        for jid in expired:
            del processing_jobs[jid]


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
        set_job_status(job_id, "processing")
        logger.info(f"[{job_id}] Starting Instagram analysis...")
        
        # ✅ SAFE VALIDATION (does NOT stop execution)
        try:
            validate_zip(zip_path)
            check_zip_safety(zip_path)
            logger.info(f"[{job_id}] ZIP validation passed")
        except Exception as e:
            logger.warning(f"[{job_id}] Validation warning: {str(e)}")

        # 🔍 DEBUG: show zip structure
        import zipfile
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                logger.info(f"[{job_id}] ZIP contents: {z.namelist()[:10]}")
        except Exception as e:
            logger.error(f"[{job_id}] ZIP read error: {str(e)}")

        # ✅ SAFE PARSE
        try:
            folder = read_instagram_zip(zip_path)
            logger.info(f"[{job_id}] Successfully extracted Instagram ZIP")
        except Exception as e:
            error_msg = f"This is not a valid Instagram export (JSON format expected). Details: {str(e)}"
            set_job_status(job_id, {"error": error_msg, "dashboard_id": None})
            logger.error(f"[{job_id}] {error_msg}")
            return

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

        set_job_status(job_id, {"status": "complete", "dashboard_id": dashboard_id})
        logger.info(f"[{job_id}] Analysis complete. Dashboard ID: {dashboard_id}")

    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        set_job_status(job_id, {"error": error_msg, "dashboard_id": None})
        logger.error(f"[{job_id}] {error_msg}")

    finally:
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
                logger.info(f"[{job_id}] Cleaned up temp file")
        except Exception as e:
            logger.warning(f"[{job_id}] Could not delete temp file: {str(e)}")


# ─────────────────────────────────────────────
#  SNAPCHAT — background worker
# ─────────────────────────────────────────────

def analyze_snapchat_zip(job_id, zip_path):
    try:
        set_job_status(job_id, "processing")
        logger.info(f"[{job_id}] Starting Snapchat analysis...")
        
        validate_zip(zip_path)
        check_zip_safety(zip_path)
        logger.info(f"[{job_id}] ZIP validation passed")
        
        folder       = read_instagram_zip(zip_path)
        data         = parse_snapchat_export(folder)
        dashboard_id = create_dashboard({
            "type":   "snapchat",
            "data":   data,
            "folder": folder,
        })
        
        set_job_status(job_id, {"status": "complete", "dashboard_id": dashboard_id})
        logger.info(f"[{job_id}] Analysis complete. Dashboard ID: {dashboard_id}")
        
    except Exception as e:
        error_msg = f"Snapchat processing failed: {str(e)}"
        set_job_status(job_id, {"error": error_msg, "dashboard_id": None})
        logger.error(f"[{job_id}] {error_msg}")
        
    finally:
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
                logger.info(f"[{job_id}] Cleaned up temp file")
        except Exception as e:
            logger.warning(f"[{job_id}] Could not delete temp file: {str(e)}")


# ─────────────────────────────────────────────
#  ROUTES — MAIN
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", error=None, snap_dashboard_id=None)


@app.route("/processing/<job_id>")
def processing(job_id):
    """Show processing page with JavaScript polling"""
    return render_template("processing.html", job_id=job_id)


@app.route("/api/job-status/<job_id>")
def api_job_status(job_id):
    """API endpoint for checking job status"""
    cleanup_old_jobs()
    
    status_data = get_job_status(job_id)
    
    if status_data is None:
        return jsonify({"error": "Job not found"}), 404
    
    if status_data.get("status") == "processing":
        return jsonify({"status": "processing"})
    
    if "error" in status_data:
        return jsonify({
            "status": "error",
            "error": status_data["error"]
        })
    
    if status_data.get("status") == "complete" and status_data.get("dashboard_id"):
        return jsonify({
            "status": "complete",
            "dashboard_id": status_data["dashboard_id"]
        })
    
    return jsonify({"status": "unknown"})


# ─────────────────────────────────────────────
#  CLOUDINARY ROUTES
# ─────────────────────────────────────────────

@app.route("/get-upload-signature")
def get_upload_signature():
    """Get Cloudinary upload configuration"""
    if not cloudinary_enabled:
        return jsonify({
            "error": "Cloudinary not configured",
            "local_only": True
        }), 400
    
    return jsonify({
        "cloud_name": os.environ.get("CLOUDINARY_CLOUD_NAME"),
        "api_key": os.environ.get("CLOUDINARY_API_KEY"),
        "upload_preset": os.environ.get("CLOUDINARY_UPLOAD_PRESET", "instalens_upload"),
    })


@app.route("/process-from-cloudinary", methods=["POST"])
def process_from_cloudinary():
    """Download file from Cloudinary and process it"""
    data      = request.get_json()
    public_id = data.get("public_id")
    platform  = data.get("platform", "instagram")

    if not public_id:
        return jsonify({"error": "No public_id provided"}), 400

    if not cloudinary_enabled:
        return jsonify({"error": "Cloudinary not configured"}), 500

    try:
        # Use Cloudinary SDK to fetch the resource
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
        api_key = os.environ.get("CLOUDINARY_API_KEY")
        api_secret = os.environ.get("CLOUDINARY_API_SECRET")
        
        # Build proper URL using Cloudinary SDK
        resource_url = cloudinary.utils.cloudinary_url(
            public_id, 
            resource_type="raw"
        )[0]
        
        logger.info(f"Downloading from Cloudinary: {resource_url}")
        
        response = http_requests.get(
            resource_url,
            stream=True,
            timeout=300
        )
        response.raise_for_status()

        # Write to temp file safely
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        try:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    temp_file.write(chunk)
            temp_file.flush()
            temp_file.close()  # Ensure file is closed before processing
            
            logger.info(f"Downloaded file size: {os.path.getsize(temp_file.name)} bytes")

            # Validate before processing
            try:
                validate_file_size(temp_file.name)
            except ValueError as e:
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass
                return jsonify({"error": str(e)}), 400

            # Delete from Cloudinary immediately after downloading
            try:
                cloudinary.uploader.destroy(public_id, resource_type="raw", invalidate=True)
                logger.info(f"Deleted {public_id} from Cloudinary")
            except Exception as e:
                logger.warning(f"Could not delete {public_id} from Cloudinary: {str(e)}")

            job_id = os.urandom(16).hex()
            if platform == "snapchat":
                threading.Thread(target=analyze_snapchat_zip, args=(job_id, temp_file.name)).start()
            else:
                threading.Thread(target=analyze_instagram_zip, args=(job_id, temp_file.name)).start()

            return jsonify({"job_id": job_id})
        
        except Exception as e:
            # Clean up temp file on error
            try:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
            except Exception:
                pass
            raise
            
    except Exception as e:
        logger.error(f"Cloudinary processing error: {str(e)}")
        return jsonify({"error": f"Cloudinary processing failed: {str(e)}"}), 500


# ─────────────────────────────────────────────
#  LOCAL UPLOAD ROUTE
# ─────────────────────────────────────────────

@app.route("/upload-local", methods=["POST"])
def upload_local():
    """Handle local file uploads"""
    file = request.files.get("file")
    platform = request.form.get("platform", "instagram")

    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    temp_file = None
    try:
        filename = secure_filename(file.filename)
        
        # Create temp file safely
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        file.save(temp_file.name)
        temp_file.close()  # Close immediately after writing
        
        logger.info(f"Local upload received: {filename}, size: {os.path.getsize(temp_file.name)}")

        # Validate file
        validate_file_size(temp_file.name)
        validate_zip(temp_file.name)
        check_zip_safety(temp_file.name)
        
        logger.info(f"Local upload validation passed")

        job_id = os.urandom(16).hex()

        if platform == "snapchat":
            threading.Thread(target=analyze_snapchat_zip, args=(job_id, temp_file.name)).start()
        else:
            threading.Thread(target=analyze_instagram_zip, args=(job_id, temp_file.name)).start()

        return jsonify({"job_id": job_id})

    except ValueError as e:
        # Validation error
        logger.warning(f"Validation error: {str(e)}")
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
        # General error
        logger.error(f"Upload error: {str(e)}")
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


# ─────────────────────────────────────────────
#  INSTAGRAM ANALYSIS ROUTES
# ─────────────────────────────────────────────

@app.route("/dashboard/<dashboard_id>")
def dashboard(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("dashboard.html", data=data, dashboard_id=dashboard_id)


@app.route("/following/<dashboard_id>")
def following(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("tables.html", data=data, dashboard_id=dashboard_id, table="following")


@app.route("/followers/<dashboard_id>")
def followers(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("tables.html", data=data, dashboard_id=dashboard_id, table="followers")


@app.route("/not-following-back/<dashboard_id>")
def not_following_back(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return render_template("tables.html", data=data, dashboard_id=dashboard_id, table="not_following_back")


@app.route("/csv/followers/<dashboard_id>")
def csv_followers(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return Response(export_followers_csv(data["connections"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=followers.csv"})


@app.route("/csv/following/<dashboard_id>")
def csv_following(dashboard_id):
    data = get_dashboard(dashboard_id)
    if not data:
        return _expired()
    return Response(export_following_csv(data["connections"]), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=following.csv"})


@app.route("/csv/not-following-back/<dashboard_id>")
def csv_not_following_back(dashboard_id):
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
        try:
            file.save(temp_file.name)
            temp_file.close()
            
            from analytics.forensic_analyzer import analyze_file
            report = analyze_file(temp_file.name)
            report["filename"] = original_name
            search_links = reverse_search_urls(temp_file.name)
            return render_template("metadata_report.html", report=report, filename=original_name, search_links=search_links)
        
        except Exception as e:
            logger.error(f"Media analysis error: {str(e)}")
            return render_template("media_upload.html", error=f"Analysis failed: {str(e)}")
        
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
            return render_template("metadata_upload.html", error="No file selected.")
        
        original_name = secure_filename(file.filename)
        ext = os.path.splitext(original_name)[1].lower()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        
        try:
            file.save(temp_file.name)
            temp_file.close()
            
            from analytics.forensic_analyzer import analyze_file
            report = analyze_file(temp_file.name)
            return render_template("metadata_report.html", report=report, filename=original_name)
        
        except Exception as e:
            logger.error(f"Metadata analysis error: {str(e)}")
            return render_template("metadata_upload.html", error=str(e))
        
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