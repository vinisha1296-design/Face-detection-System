import requests

url = "http://127.0.0.1:5000/register_complaint"

data = {
    "complainant_name": "Aditi",
    "complaint_type": "Theft",
    "description": "Suspicious person near mall",
    "location": "Chennai Mall"
}

response = requests.post(url, json=data)

print(response.json())