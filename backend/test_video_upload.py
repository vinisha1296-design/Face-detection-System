import requests

url = "http://127.0.0.1:5000/upload_video"

data = {
    "complaint_id": "1",
    "location": "Chennai Mall"
}

video_path = "test_video.mp4"

with open(video_path, "rb") as video_file:
    files = {
        "video": video_file
    }

    response = requests.post(
        url,
        data=data,
        files=files
    )

print(response.json())