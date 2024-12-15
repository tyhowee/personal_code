from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
import requests
from pipeline.data_cube_generator import (
    process_data_cube,
)  # Import the pipeline function

# Flask App Initialization
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Mapbox Access Token (Replace with your actual token)
MAPBOX_ACCESS_TOKEN = "pk.eyJ1IjoidHlob3dlIiwiYSI6ImNtNG9zb3VnYTBkbWMybG9mNnFwYjQwYTAifQ.6DdWyeUfTpiuW36elXkarw"


# Fetch Mapbox Layer Function
def fetch_mapbox_layer(layer_id):
    """
    Fetch a GeoJSON layer from Mapbox using the Dataset or Tileset API.

    Args:
        layer_id (str): The Mapbox layer ID to fetch.

    Returns:
        dict: The GeoJSON data for the layer.
    """
    url = f"https://api.mapbox.com/datasets/v1/{layer_id}/features?access_token={MAPBOX_ACCESS_TOKEN}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()  # GeoJSON data
    else:
        raise Exception(
            f"Failed to fetch layer {layer_id}. Status code: {response.status_code}, Message: {response.text}"
        )


@app.route("/process", methods=["POST"])
def process_polygon():
    try:
        # Log incoming request data
        print("Incoming data:", request.json)

        # User-defined mask GeoJSON
        data = request.json
        if "mask" not in data:
            return jsonify({"error": "Mask polygon is missing"}), 400

        mask_geojson = data["mask"]
        print("Mask GeoJSON received:", mask_geojson)

        # Fetch layers dynamically from Mapbox
        geojson_files = fetch_mapbox_layer("geojson_layer_id")
        line_geojson_files = fetch_mapbox_layer("line_geojson_layer_id")
        target_files = fetch_mapbox_layer("target_layer_id")
        raster_files = []  # Placeholder
        parquet_files = []  # Placeholder

        # Log fetched layers
        print("GeoJSON Files:", geojson_files)
        print("Line GeoJSON Files:", line_geojson_files)
        print("Target Files:", target_files)

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
