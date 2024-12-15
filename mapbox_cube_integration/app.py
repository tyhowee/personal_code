from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from pipeline.data_cube_generator import process_data_cube
import mercantile
from mapbox_vector_tile import decode
import traceback
import json
import tempfile
import os

# Flask App Initialization
app = Flask(__name__)
CORS(app)

# Mapbox Configuration
MAPBOX_ACCESS_TOKEN = "sk.eyJ1IjoidHlob3dlIiwiYSI6ImNtNHE3a3VvbzEyOXgyaXB1eGgxcmZidmgifQ.3Cot-Gp7F3i5odGNVaL1aA"
USERNAME = "tyhowe"  # Your Mapbox username


# Function to dynamically fetch tileset IDs
def fetch_tileset_ids(username: str) -> dict:
    url = f"https://api.mapbox.com/tilesets/v1/{username}?access_token={MAPBOX_ACCESS_TOKEN}"
    print(f"[DEBUG] Fetching tilesets from: {url}")
    tileset_mapping = {}
    try:
        response = requests.get(url)
        if response.status_code == 200:
            tilesets = response.json()
            for tileset in tilesets:
                name = tileset.get("name")
                tileset_id = tileset.get("id")
                if name and tileset_id:
                    tileset_mapping[name] = tileset_id
            print(f"[DEBUG] Fetched tilesets: {tileset_mapping}")
        else:
            print(f"[ERROR] Failed to fetch tilesets: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Exception while fetching tilesets: {e}")
        traceback.print_exc()
    return tileset_mapping


# Fetch Mapbox Layer Function
def fetch_mapbox_layer(tileset_id: str, bbox: list, zoom: int = 12) -> list:
    min_x, min_y, max_x, max_y = bbox
    tiles = list(mercantile.tiles(min_x, min_y, max_x, max_y, zoom))
    features = []
    for tile in tiles:
        url = f"https://api.mapbox.com/v4/{tileset_id}/{tile.z}/{tile.x}/{tile.y}.vector.pbf?access_token={MAPBOX_ACCESS_TOKEN}"
        print(f"[DEBUG] Fetching vector tile: {url}")
        try:
            response = requests.get(url)
            if response.status_code == 200:
                decoded_tile = decode(response.content)
                for layer_name, layer_data in decoded_tile.items():
                    features.extend(layer_data["features"])
            else:
                print(f"[ERROR] Failed to fetch tile {tile}: {response.status_code}")
        except Exception as e:
            print(f"[ERROR] Exception fetching tile {tile}: {e}")
    return features


def get_tileset_type(tileset_id: str) -> str:
    url = f"https://api.mapbox.com/tilesets/v1/{tileset_id}?access_token={MAPBOX_ACCESS_TOKEN}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("type", "vector")
    except Exception as e:
        print(f"[ERROR] Unable to fetch tileset type: {e}")
    return "vector"


def filter_tilesets(available_tilesets: dict, requested_layers: list) -> dict:
    """
    Match requested layer names to available tileset IDs with normalization.

    Args:
        available_tilesets (dict): Tilesets fetched from Mapbox.
        requested_layers (list): Layers requested from the client.

    Returns:
        dict: Matched tilesets.
    """
    # Normalize tileset names for easier matching
    normalized_tilesets = {
        name.lower().replace("_", "-"): tileset_id
        for name, tileset_id in available_tilesets.items()
    }

    filtered = {}
    for layer in requested_layers:
        normalized_layer = layer.strip().lower()
        if normalized_layer in normalized_tilesets:
            filtered[layer] = normalized_tilesets[normalized_layer]
    return filtered


def fetch_tilesets() -> dict:
    try:
        return fetch_tileset_ids(USERNAME)
    except Exception as e:
        print(f"[ERROR] Failed to fetch tilesets: {e}")
        return {}


@app.route("/process", methods=["POST"])
def process_polygon():
    try:
        print("[DEBUG] Incoming request data:", json.dumps(request.json, indent=2))

        # Extract mask from request
        data = request.json
        if "mask" not in data:
            return jsonify({"error": "Mask polygon is missing"}), 400

        mask_geojson = data["mask"]
        coords = mask_geojson["geometry"]["coordinates"][0]
        bbox = [
            min(coord[0] for coord in coords),
            min(coord[1] for coord in coords),
            max(coord[0] for coord in coords),
            max(coord[1] for coord in coords),
        ]
        print(f"[DEBUG] Calculated bounding box: {bbox}")

        # Fetch tilesets and filter by requested layers
        tileset_mapping = fetch_tilesets()
        requested_layers = data["layers"]
        filtered_tilesets = filter_tilesets(tileset_mapping, requested_layers)
        print(f"[DEBUG] Filtered tilesets: {filtered_tilesets}")

        # Fetch data and save to temporary files
        geojson_file_paths = []
        for name, tileset_id in filtered_tilesets.items():
            print(f"[DEBUG] Fetching data for tileset: {name} (ID: {tileset_id})")
            layer_data = fetch_mapbox_layer(tileset_id, bbox)
            if layer_data:
                temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False)
                json.dump({"type": "FeatureCollection", "features": layer_data}, temp_file)
                temp_file.close()
                geojson_file_paths.append(temp_file.name)
                print(f"[DEBUG] Saved {len(layer_data)} features to: {temp_file.name}")
            else:
                print(f"[WARNING] No data found for tileset: {name}")
        
        # Validate geojson_file_paths
        if not geojson_file_paths:
            print("[ERROR] No valid GeoJSON files were created. Aborting processing.")
            return jsonify({"error": "No valid data fetched for requested layers"}), 400
        
        # Debug output before calling process_data_cube
        print(f"[DEBUG] GeoJSON file paths: {geojson_file_paths}")


        # Call data cube pipeline
        result = process_data_cube(
            geojson_mask=mask_geojson,
            geojson_files=geojson_file_paths,
            line_geojson_files=[],
            target_files=[],
            raster_files=[],
            parquet_files=[],
        )

        # Cleanup temporary files
        for file_path in geojson_file_paths:
            try:
                os.remove(file_path)
                print(f"[DEBUG] Deleted temporary file: {file_path}")
            except Exception as e:
                print(f"[ERROR] Failed to delete file {file_path}: {e}")

        return jsonify({"status": "success", "result": result})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print("[DEBUG] Starting Flask server...")
    app.run(debug=True)
