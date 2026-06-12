import os
import cv2
import urllib.request
from collections import Counter
from ultralytics import YOLO
from deepface import DeepFace

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FACE_MODEL_PATH = os.path.join(BASE_DIR, "yolov8n-face.pt")
DATABASE_PATH = os.path.join(BASE_DIR, "face_database")
DEBUG_FOLDER = os.path.join(BASE_DIR, "static", "debug_faces")

os.makedirs(DEBUG_FOLDER, exist_ok=True)

if not os.path.exists(FACE_MODEL_PATH):
    print("Downloading YOLO Face Detector...")
    url = "https://huggingface.co/deepghs/yolo-face/resolve/main/yolov8n-face/model.pt"
    urllib.request.urlretrieve(url, FACE_MODEL_PATH)
    print("Download Complete!")

face_detector = YOLO(FACE_MODEL_PATH)


def process_video(video_path, location):
    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    predictions = []
    sightings = []

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        frame_count += 1

        # Process every 10th frame to reduce time
        if frame_count % 10 != 0:
            continue

        results = face_detector.predict(
            frame,
            conf=0.10,
            verbose=False
        )

        for result in results:
            for box in result.boxes:
                # 1. Safely extract coordinates as native Python integers
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().tolist())

                face_crop = frame[y1:y2, x1:x2]

                if face_crop.size == 0:
                    continue

                # 2. Draw a rectangle on a distinct copy for debugging
                frame_with_box = frame.copy()
                cv2.rectangle(
                    frame_with_box,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                frame_image_name = f"frame_{frame_count}_{x1}_{y1}.jpg"
                crop_image_name = f"crop_{frame_count}_{x1}_{y1}.jpg"

                frame_path = os.path.join(DEBUG_FOLDER, frame_image_name)
                crop_path = os.path.join(DEBUG_FOLDER, crop_image_name)

                cv2.imwrite(frame_path, frame_with_box)
                cv2.imwrite(crop_path, face_crop)

                try:
                    # 3. FIX: Pass 'face_crop' array directly from memory.
                    # This safely permits multiple unique face evaluations per frame without file collisions.
                    matches = DeepFace.find(
                        img_path=face_crop,
                        db_path=DATABASE_PATH,
                        model_name="Facenet",
                        enforce_detection=False,
                        silent=True
                    )

                    if len(matches) == 0 or len(matches[0]) == 0:
                        continue

                    best_match = matches[0].iloc[0]

                    identity_path = best_match["identity"]
                    distance = float(best_match["distance"])

                    person_name = identity_path.split(os.sep)[-2]

                    # Accept match if distance is below threshold
                    if distance < 1.00:
                        seconds = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000

                        predictions.append(person_name)

                        sightings.append({
                            "person": person_name,
                            "timestamp": round(seconds, 2),
                            "location": location,
                            "distance": round(distance, 3),
                            "frame_image": f"/static/debug_faces/{frame_image_name}",
                            "crop_image": f"/static/debug_faces/{crop_image_name}"
                        })

                except Exception as e:
                    print(f"DeepFace error on frame {frame_count}:", e)

        print(f"Processed Frame: {frame_count}")

    cap.release()

    if len(predictions) == 0:
        return {
            "final_person": "No confident match found",  # Restored for your Flask backend
            "detected_people": [],
            "detections": [],
            "summary": {}
        }

    counts = Counter(predictions)
    
    # Extract the single most common person (the "winner" your backend expects)
    final_person = counts.most_common(1)[0][0]
    all_detected_people = list(counts.keys())

    return {
        "final_person": final_person,                  # Restored for your Flask backend
        "detected_people": all_detected_people,        # Keeps multi-person tracking data intact
        "detections": sightings,
        "summary": {person: count for person, count in counts.items()}
    }