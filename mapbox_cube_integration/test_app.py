import requests

url = "http://127.0.0.1:5000/process"
data = {
    "mask": {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
        },
    }
}

response = requests.post(url, json=data)
print(response.json())
