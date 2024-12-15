import os
import requests

import geopandas as gpd
import numpy as np
import tempfile
import json

from typing import Tuple, List


MAPBOX_ACCESS_TOKEN = "pk.eyJ1IjoidHlob3dlIiwiYSI6ImNtNG9zb3VnYTBkbWMybG9mNnFwYjQwYTAifQ.6DdWyeUfTpiuW36elXkarw"


# File Selection (replace tk with glob in future?)--------------------------------------------------
def fetch_file_from_mapbox(file_url, save_path):
    """Fetch a file from Mapbox and save it locally."""
    response = requests.get(
        file_url, headers={"Authorization": f"Bearer {MAPBOX_ACCESS_TOKEN}"}
    )
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        print(f"File saved: {save_path}")
        return save_path
    else:
        raise RuntimeError(
            f"Failed to fetch file from Mapbox. Status code: {response.status_code}, {response.text}"
        )


def select_all_files():
    """
    Fetch files dynamically from Mapbox and classify them into categories.
    Replace the manual selection with dynamic fetching.
    """
    # Example Mapbox URLs for your files (update these with your actual dataset URLs)
    mapbox_files = {
        "mask_file": "https://api.mapbox.com/path/to/mask.geojson?access_token=YOUR_MAPBOX_ACCESS_TOKEN",
        "geojson_files": [
            "https://api.mapbox.com/path/to/vector1.geojson?access_token=YOUR_MAPBOX_ACCESS_TOKEN",
            "https://api.mapbox.com/path/to/vector2.geojson?access_token=YOUR_MAPBOX_ACCESS_TOKEN",
        ],
        "line_geojson_files": [
            "https://api.mapbox.com/path/to/lines.geojson?access_token=YOUR_MAPBOX_ACCESS_TOKEN"
        ],
        "target_files": [
            "https://api.mapbox.com/path/to/points.geojson?access_token=YOUR_MAPBOX_ACCESS_TOKEN"
        ],
        "raster_files": [
            "https://api.mapbox.com/path/to/raster.tif?access_token=YOUR_MAPBOX_ACCESS_TOKEN"
        ],
        "parquet_files": [
            "https://api.mapbox.com/path/to/data.parquet?access_token=YOUR_MAPBOX_ACCESS_TOKEN"
        ],
    }

    # Initialize local file paths
    local_files = {
        "mask_file": None,
        "geojson_files": [],
        "line_geojson_files": [],
        "target_files": [],
        "raster_files": [],
        "parquet_files": [],
    }

    # Fetch files from Mapbox and save locally
    for key, file_paths in mapbox_files.items():
        if isinstance(file_paths, str):  # Single file (e.g., mask file)
            local_files[key] = fetch_file_from_mapbox(
                file_paths, os.path.basename(file_paths)
            )
        elif isinstance(file_paths, list):  # Multiple files
            local_files[key] = [
                fetch_file_from_mapbox(url, os.path.basename(url)) for url in file_paths
            ]

    # Print imported file information
    print("Imported Files:")
    for key, files in local_files.items():
        if isinstance(files, list):
            print(f"{key.capitalize()}: {[os.path.basename(f) for f in files]}")
        else:
            print(f"{key.capitalize()}: {os.path.basename(files) if files else 'None'}")

    return (
        local_files["mask_file"],
        local_files["geojson_files"],
        local_files["line_geojson_files"],
        local_files["target_files"],
        local_files["raster_files"],
        local_files["parquet_files"],
    )


# Function to select columns from a GeoJSON file
def select_columns(geojson_file, vector_features_to_process):
    """
    Automatically process all columns in the GeoJSON file.
    """
    gdf = gpd.read_file(geojson_file)
    columns = gdf.columns.tolist()
    print(f"Available columns in {os.path.basename(geojson_file)}: {columns}")

    # Automatically select all columns (or customize this logic as needed)
    selected_columns = columns  # Example: Use all columns
    vector_features_to_process.extend([(geojson_file, col) for col in selected_columns])
    print(f"Selected columns: {selected_columns}")


# Function to select columns (attributes) from a GeoParquet file
def select_parquet_columns(geoparquet_file, parquet_features_to_process):
    """
    Automatically process all columns in the Parquet file.
    """
    gdf = gpd.read_parquet(geoparquet_file)
    columns = gdf.columns.tolist()
    print(f"Available columns in {os.path.basename(geoparquet_file)}: {columns}")

    # Automatically select all columns (or customize this logic as needed)
    selected_columns = columns  # Example: Use all columns
    parquet_features_to_process.extend(
        [(geoparquet_file, col) for col in selected_columns]
    )
    print(f"Selected columns: {selected_columns}")


# Grid Size--------------------------------------------------
# Function to compute grid size based on the mask file
def compute_grid_size(bbox: list, short_edge_cells: int = 20) -> Tuple[int, int]:
    """
    Computes the grid size for a given bounding box.

    Args:
        bbox (list): Bounding box as [minx, miny, maxx, maxy].
        short_edge_cells (int): Number of cells along the shorter edge of the grid.

    Returns:
        Tuple[int, int]: The computed grid size as (rows, columns).
    """
    minx, miny, maxx, maxy = bbox

    # Calculate width and height of the bounding box
    width = maxx - minx
    height = maxy - miny

    # Determine which is the short and long edge
    if width < height:
        short_edge = width
        long_edge = height
        orientation = "portrait"
    else:
        short_edge = height
        long_edge = width
        orientation = "landscape"

    # Compute the aspect ratio
    aspect_ratio = long_edge / short_edge

    # Compute the number of cells for the long edge
    long_edge_cells = int(short_edge_cells * aspect_ratio)

    # Determine the grid size based on the orientation
    if orientation == "portrait":
        grid_size = (short_edge_cells, long_edge_cells)
    else:
        grid_size = (long_edge_cells, short_edge_cells)

    return grid_size


# Combine Layers--------------------------------------------------

def flatten_layer_names(layer_names):
    """
    Flattens a list of layer names if it contains nested lists.

    Args:
        layer_names (list): A list of layer names, which may contain nested lists.

    Returns:
        list: A flattened list of layer names.
    """
    if any(isinstance(name, list) for name in layer_names):
        return [item for sublist in layer_names for item in sublist]
    return layer_names


def combine_layers(layers):
    print('-----------------------------')
    print('Combining Layers.................')
    data_arrays = []
    layer_names = []

    for data_array, names in layers:
        if data_array.size != 0:
            data_arrays.append(data_array)
            if isinstance(names, list):
                layer_names.extend(names)  # Flatten and add names
            else:
                layer_names.append(names)  # Add single name
        else:
            print(f"Skipping empty data array with names: {names}")

    if not data_arrays:
        print("No data arrays to combine.")
        return np.array([]), []

    # Check that all arrays have the same x and y dimensions
    first_shape = data_arrays[0].shape[1:]
    if not all(data_array.shape[1:] == first_shape for data_array in data_arrays):
        print("Error: The x/y dimensions of the arrays do not match.")
        return np.array([]), []

    # Concatenate all data arrays along axis=0
    combined_data = np.concatenate(data_arrays, axis=0)
    print(f"Combined array shape (with targets): {combined_data.shape}")
    print(f"Final layer names: {layer_names}")

    if len(layer_names) == combined_data.shape[0]:
        print(f"Layer name mapping successful. Total layers: {len(layer_names)}")
    else:
        print(f"Warning: Mismatch in layers. {len(layer_names)} names for {combined_data.shape[0]} layers.")

    return combined_data, layer_names
