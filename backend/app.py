import os
import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_cors import CORS

from database import init_db, DB_PATH
from ml_model import process_video

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

init_db()


# ── Helper ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # lets us access columns by name
    return conn


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    conn = get_db()
    cursor = conn.cursor()

    # Recent complaints (latest 10)
    cursor.execute("""
        SELECT id, complainant_name, complaint_type, location, created_at
        FROM complaints
        ORDER BY id DESC
        LIMIT 10
    """)
    complaints = cursor.fetchall()

    # Stats
    cursor.execute("SELECT COUNT(*) FROM complaints")
    total_complaints = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM detections")
    total_detections = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        complaints=complaints,
        total_complaints=total_complaints,
        total_detections=total_detections,
        total_videos=0,         # extend later if you track videos in DB
    )


@app.route("/upload")
def upload_page():
    return render_template("upload.html")


# ── Complaint submission (HTML form) ─────────────────────────────────────────

@app.route("/submit_complaint", methods=["POST"])
def submit_complaint():
    complainant_name = request.form.get("complainant_name", "").strip()
    complaint_type   = request.form.get("complaint_type", "Other").strip()
    description      = request.form.get("description", "").strip()
    location         = request.form.get("location", "").strip()

    if not complainant_name or not description or not location:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("upload_page"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO complaints (complainant_name, complaint_type, description, location)
        VALUES (?, ?, ?, ?)
    """, (complainant_name, complaint_type, description, location))
    complaint_id = cursor.lastrowid
    conn.commit()

    # If a video was also attached, process it immediately
    video = request.files.get("video")
    if video and video.filename:
        video_path = os.path.join(UPLOAD_FOLDER, video.filename)
        video.save(video_path)

        result = process_video(video_path, location)

        for detection in result["detections"]:
            cursor.execute("""
                INSERT INTO detections
                    (complaint_id, detected_person, video_timestamp, location, distance)
                VALUES (?, ?, ?, ?, ?)
            """, (
                complaint_id,
                detection["person"],
                detection["timestamp"],
                detection["location"],
                detection["distance"],
            ))
        conn.commit()
        conn.close()

        return render_template(
            "result.html",
            final_person=result["final_person"],
            summary=result["summary"],
            detections=result["detections"],
        )

    conn.close()
    flash(f"Complaint #{complaint_id} registered successfully.", "success")
    return redirect(url_for("home"))


# ── Complaint submission (JSON API) ──────────────────────────────────────────

@app.route("/register_complaint", methods=["POST"])
def register_complaint():
    data = request.json or {}

    required = ["complainant_name", "complaint_type", "description", "location"]
    missing  = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO complaints (complainant_name, complaint_type, description, location)
        VALUES (?, ?, ?, ?)
    """, (data["complainant_name"], data["complaint_type"], data["description"], data["location"]))
    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"message": "Complaint registered successfully", "complaint_id": complaint_id})


# ── Video upload (JSON API) ───────────────────────────────────────────────────

@app.route("/upload_video", methods=["POST"])
def upload_video():
    complaint_id = request.form.get("complaint_id")
    location     = request.form.get("location", "")
    video        = request.files.get("video")

    if not video or not complaint_id:
        return jsonify({"error": "complaint_id and video are required"}), 400

    video_path = os.path.join(UPLOAD_FOLDER, video.filename)
    video.save(video_path)

    result = process_video(video_path, location)

    conn = get_db()
    cursor = conn.cursor()
    for detection in result["detections"]:
        cursor.execute("""
            INSERT INTO detections
                (complaint_id, detected_person, video_timestamp, location, distance)
            VALUES (?, ?, ?, ?, ?)
        """, (
            complaint_id,
            detection["person"],
            detection["timestamp"],
            detection["location"],
            detection["distance"],
        ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Video processed successfully", "result": result})


# ── Video submit (HTML form – separate upload page flow) ─────────────────────

@app.route("/submit_video", methods=["POST"])
def submit_video():
    complaint_id = request.form.get("complaint_id")
    location     = request.form.get("location", "")
    video        = request.files.get("video")

    if not video or not complaint_id:
        flash("Complaint ID and video are required.", "error")
        return redirect(url_for("upload_page"))

    video_path = os.path.join(UPLOAD_FOLDER, video.filename)
    video.save(video_path)

    result = process_video(video_path, location)

    conn = get_db()
    cursor = conn.cursor()
    for detection in result["detections"]:
        cursor.execute("""
            INSERT INTO detections
                (complaint_id, detected_person, video_timestamp, location, distance)
            VALUES (?, ?, ?, ?, ?)
        """, (
            complaint_id,
            detection["person"],
            detection["timestamp"],
            detection["location"],
            detection["distance"],
        ))
    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        final_person=result["final_person"],
        summary=result["summary"],
        detections=result["detections"],
    )


# ── Report API ────────────────────────────────────────────────────────────────

@app.route("/report/<int:complaint_id>", methods=["GET"])
def get_report(complaint_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT detected_person, video_timestamp, location, distance
        FROM detections
        WHERE complaint_id = ?
    """, (complaint_id,))
    rows = cursor.fetchall()
    conn.close()

    detections = [
        {"person": r["detected_person"], "timestamp": r["video_timestamp"],
         "location": r["location"], "distance": r["distance"]}
        for r in rows
    ]

    return jsonify({"complaint_id": complaint_id, "detections": detections})


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)