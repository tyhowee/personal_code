from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from pipeline.data_cube_generator import process_data_cube

# Flask App Initialization
app = Flask(__name__)
CORS(app)

# Mapbox Access Token (Replace with your actual token)
MAPBOX_ACCESS_TOKEN = "pk.eyJ1IjoidHlob3dlIiwiYSI6ImNtNG9zb3VnYTBkbWMybG9mNnFwYjQwYTAifQ.6DdWyeUfTpiuW36elXkarw"


# Fetch Mapbox Layer Function
def fetch_mapbox_layer(tileset_id, bbox):
    """
    Fetch a GeoJSON layer from Mapbox using the Static Tiles API.

    Args:
        tileset_id (str): The Mapbox tileset ID to fetch.
        bbox (list): Bounding box [minX, minY, maxX, maxY] to filter the data.

    Returns:
        dict: The GeoJSON data for the layer within the bounding box.
    """
    # Construct the API request for the Static Tiles API
    url = (
        f"https://api.mapbox.com/v4/{tileset_id}/tilequery/"
        f"{bbox[0]},{bbox[1]}.json?access_token={MAPBOX_ACCESS_TOKEN}"
    )
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()  # GeoJSON data
    else:
        raise Exception(
            f"Failed to fetch layer {tileset_id}. Status code: {response.status_code}, Message: {response.text}"
        )


@app.route("/process", methods=["POST"])
def process_polygon():
    try:
        # Log incoming request data
        print("Incoming data:", request.json)

        # Extract mask and layers from the request
        data = request.json
        if "mask" not in data or "layers" not in data:
            return jsonify({"error": "Mask polygon or layer list is missing"}), 400

        mask_geojson = data["mask"]
        layer_ids = data["layers"]  # List of Mapbox layer IDs
        print("Mask GeoJSON received:", mask_geojson)
        print("Layer IDs received:", layer_ids)

        # Extract bounding box (bbox) from the polygon mask
        coords = mask_geojson["geometry"]["coordinates"][0]
        min_x = min(coord[0] for coord in coords)
        max_x = max(coord[0] for coord in coords)
        min_y = min(coord[1] for coord in coords)
        max_y = max(coord[1] for coord in coords)
        bbox = [min_x, min_y, max_x, max_y]
        print("Calculated bounding box:", bbox)

        # Filter valid layers (exclude Mapbox system layers and base layers)
        valid_layers = [
            layer_id
            for layer_id in layer_ids
            if not layer_id.startswith("gl-draw") and layer_id != "mapbox-satellite"
        ]
        print("Valid layers for fetching:", valid_layers)

        # Fetch data for all valid layers within the bbox
        geojson_files = []
        for layer_id in valid_layers:
            try:
                layer_data = fetch_mapbox_layer(layer_id, bbox)
                geojson_files.append(layer_data)
                print(f"Fetched data for layer {layer_id}")
            except Exception as e:
                print(f"Error fetching layer {layer_id}: {e}")

        # Ensure we have fetched some valid data
        if not geojson_files:
            return (
                jsonify({"error": "No valid data fetched for the provided layers"}),
                400,
            )

        # Initialize placeholders for other file types
        line_geojson_files = []
        target_files = []
        raster_files = []  # Placeholder (raster data fetching not supported here)
        parquet_files = []  # Placeholder

        # Call the pipeline
        result = process_data_cube(
            geojson_mask=mask_geojson,
            geojson_files=geojson_files,
            line_geojson_files=line_geojson_files,
            target_files=target_files,
            raster_files=raster_files,
            parquet_files=parquet_files,
        )

        return jsonify({"status": "success", "result": result})

    except Exception as e:
        # Log the exception for debugging
        print("Error during processing:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
