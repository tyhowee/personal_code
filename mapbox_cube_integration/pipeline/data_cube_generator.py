import numpy as np
import xarray as xr
import json
import time
import tempfile
from pipeline.cube_generator_utils import (
    compute_grid_size,
    combine_layers,
    flatten_layer_names,
)
from pipeline.cube_processing_function import CubeGeospatialProcessor


def process_data_cube(
    geojson_mask,
    bbox,
    geojson_files,
    line_geojson_files,
    target_files,
    raster_files,
    parquet_files,
):
    """
    Process data cube using the provided GeoJSON mask and input files.

    Args:
        geojson_mask (dict): GeoJSON object defining the mask.
        geojson_files (list): List of GeoJSON polygon files.
        line_geojson_files (list): List of GeoJSON line files.
        target_files (list): List of target files (e.g., points).
        raster_files (list): List of raster files (GeoTIFFs).
        parquet_files (list): List of parquet files.

    Returns:
        str: Output file path for the generated data cube or success message.
    """
    # Define grid size
    short_edge_cells = 100

    # Compute grid size using the mask
    grid_size = compute_grid_size(bbox, short_edge_cells=short_edge_cells)[::-1]
    print(f"Calculated grid size: {grid_size}")

    # Initialize the processor
    processor = CubeGeospatialProcessor(
        grid_size=grid_size, mask_file=geojson_mask, crs="EPSG:3857"
    )

    # Start timing for the entire file processing operation
    overall_start_time = time.time()

    # Process different file types
    print("Processing files...")
    target_data, target_layer_names, _ = processor.process_files(target_files, "target")
    raster_data, raster_names, _ = processor.process_files(raster_files, "raster")
    line_vector_data, line_layer_names, _ = processor.process_files(
        line_geojson_files, "line"
    )
    vector_data, vector_layer_names, vector_feature_mappings = processor.process_files(
        geojson_files, "vector"
    )
    parquet_data, parquet_layer_names, _ = processor.process_files(
        parquet_files, "parquet"
    )

    # Calculate and print the overall processing time
    overall_elapsed_time = time.time() - overall_start_time
    print("------------------------------------")
    print(
        f"Overall processing time for all file types: {overall_elapsed_time:.2f} seconds"
    )

    # Combine layers
    vector_layer_names = flatten_layer_names(vector_layer_names)
    raster_names = flatten_layer_names(raster_names)
    line_layer_names = flatten_layer_names(line_layer_names)
    parquet_layer_names = flatten_layer_names(parquet_layer_names)
    target_layer_names = flatten_layer_names(target_layer_names)

    layers = [
        (vector_data, vector_layer_names),
        (raster_data, raster_names),
        (line_vector_data, line_layer_names),
        (parquet_data, parquet_layer_names),
        (target_data, target_layer_names),
    ]
    combined_data, combined_layer_names = combine_layers(layers)
    print(f"Combined layer names: {combined_layer_names}")

    # Convert to xarray
    mappings_json = json.dumps(vector_feature_mappings)
    x_coords = np.arange(combined_data.shape[2])  # X-coordinates
    y_coords = np.arange(combined_data.shape[1])  # Y-coordinates

    data_xr = xr.DataArray(
        combined_data,
        dims=["layer", "y", "x"],
        coords={"layer": combined_layer_names, "y": y_coords, "x": x_coords},
        name="combined_layers",
    )

    # Add metadata
    data_xr.attrs["vector_feature_mappings"] = mappings_json
    data_xr.attrs["crs"] = "EPSG:3857"
    data_xr.attrs["transform"] = str(processor.common_transform)
    data_xr.attrs["geospatial_bounds"] = (
        f"{processor.minx}, {processor.miny}, {processor.maxx}, {processor.maxy}"
    )

    # Export to NetCDF
    output_file = "output_data_cube.nc"
    data_xr.to_netcdf(output_file)
    print(f"Data successfully exported to {output_file}")
    return f"Data cube processing completed. File saved to {output_file}."
