import os
from ml_model import process_video, DATABASE_PATH

print("DATABASE PATH:", DATABASE_PATH)
print("DATABASE EXISTS:", os.path.exists(DATABASE_PATH))

print("\nDatabase folders:")
for folder in os.listdir(DATABASE_PATH):
    folder_path = os.path.join(DATABASE_PATH, folder)
    if os.path.isdir(folder_path):
        print(folder, ":", len(os.listdir(folder_path)), "images")

print("\nRunning ML on video...")

result = process_video(
    video_path="test_video.mp4",
    location="Chennai Mall"
)

print("\nFINAL RESULT:")
print(result)