import os
import time
from tkinter import simpledialog, messagebox, Label, Button, Tk

import numpy as np
import geopandas as gpd
import rasterio
from shapely.geometry import box
from joblib import Parallel, delayed
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
import scipy.ndimage
from scipy.ndimage import distance_transform_edt


class CubeGeospatialProcessor:
    def __init__(self, grid_size, mask_file, crs="EPSG:3857"):
        self.grid_size = grid_size
        self.mask_file = mask_file
        self.crs = crs
        self.mask_gdf = gpd.read_file(mask_file).to_crs(crs)
        self.minx, self.miny, self.maxx, self.maxy = self.mask_gdf.total_bounds
        self.common_transform = from_bounds(self.minx, self.miny, self.maxx, self.maxy, grid_size[1], grid_size[0])

    def process_files(self, file_list, file_type, vector_features_to_process=None, parquet_features_to_process=None):
        start_time = time.time()
        data = []
        layer_names = []
        feature_mappings = {}  # Initialize a dictionary to store feature mappings
    
        if file_list:
            for file in file_list:
                if file_type == 'target':
                    layer, layer_name = self.process_target(file)
                    mappings = {}  # No mappings for target type
                elif file_type == 'vector':
                    layer, layer_name, mappings = self.process_vector(file, vector_features_to_process)
                    feature_mappings.update(mappings)  # Store the mappings
                elif file_type == 'line':
                    layer, layer_name = self.process_line(file)
                    mappings = {}  # No mappings for line type
                elif file_type == 'raster':
                    layer, layer_name = self.process_raster(file)
                    mappings = {}  # No mappings for raster type
                elif file_type == 'parquet':
                    layer, layer_name = self.process_parquet(file, parquet_features_to_process=parquet_features_to_process)
                    mappings = {}
                else:
                    raise ValueError("Unsupported file type provided.")
    
                if layer is not None:
                    data.append(layer)
                    layer_names.append(layer_name)
                    
            if data:
                data = np.concatenate(data, axis=0)
                print(f"{file_type.capitalize()} data shape: {data.shape}")
            else:
                print(f"No {file_type} data processed.")
        else:
            print(f"No {file_type} files detected.")
    
        elapsed_time = time.time() - start_time
        print(f"Total processing time for {file_type} files: {elapsed_time:.2f} seconds")
        return (np.array([]), [], {}) if len(data) == 0 else (data, layer_names, feature_mappings)
    
    def interpolate_gaps(self, data):
        """
        Interpolates gaps (NaN values) in a rasterized 2D array using nearest-neighbor interpolation.

        Args:
            data (np.ndarray): The input 2D array with NaN gaps.

        Returns:
            np.ndarray: The interpolated 2D array.
        """
        # Create a mask of NaN values
        nan_mask = np.isnan(data)

        # Use nearest-neighbor interpolation to fill NaN values
        interpolated_data = scipy.ndimage.generic_filter(
            data, 
            lambda x: np.nanmean(x) if not np.all(np.isnan(x)) else np.nan,
            size=20,  # nxn window
            mode='mirror'
        )

        # Replace NaN regions with the interpolated values
        data[nan_mask] = interpolated_data[nan_mask]
        return data

    def process_target(self, file):
        # Read and reproject the GeoDataFrame
        target_df = gpd.read_file(file).to_crs(self.crs)
        
        # Check geometry type
        geom_types = target_df.geometry.type.unique()
        
        if 'Point' in geom_types:
            # Process as points with a buffer
            target_buffer_size = self.get_buffer_size()
            target_df['geometry'] = target_df.geometry.buffer(target_buffer_size)
            
            # Rasterize with buffered points
            target_geometry_generator = ((geom, 1) for geom in target_df.geometry)
            target_data = rasterize(
                shapes=target_geometry_generator,
                out_shape=self.grid_size,
                fill=0,
                transform=self.common_transform
            ).astype('float32')

            # Flip the y-axis
            target_data = np.flipud(target_data)
            
        elif 'Polygon' in geom_types or 'MultiPolygon' in geom_types:
            # Process as polygons directly, without buffering
            sindex = target_df.sindex
            x = np.linspace(self.minx, self.maxx, self.grid_size[1] + 1)
            y = np.linspace(self.miny, self.maxy, self.grid_size[0] + 1)
            cells = [box(x[j], y[i], x[j + 1], y[i + 1]) for i in range(self.grid_size[0]) for j in range(self.grid_size[1])]
            
            results = Parallel(n_jobs=-1)(
                delayed(self.process_target_cell)(idx, cell, target_df, sindex) for idx, cell in enumerate(cells)
            )
            
            # Initialize binary grid
            target_data = np.zeros(self.grid_size, dtype='float32')
            for i, j, value in results:
                target_data[i, j] = value
            
        else:
            raise ValueError("Unsupported geometry type in file. Only Point and Polygon geometries are supported.")
        
        # Flip grid to match coordinate system orientation
        target_data_flipped = np.flipud(target_data)
        
        # Add third dimension for consistency
        target_data_3D = np.expand_dims(target_data_flipped, axis=0)
        target_layer_name = f"TARGET_{os.path.basename(file).replace('.geojson', '')}"
    
        return target_data_3D, target_layer_name

    def process_vector(self, file, vector_features_to_process):
        gdf = gpd.read_file(file).to_crs(self.crs)
        feature_columns = [col for _, col in vector_features_to_process if _ == file]
        vector_layers = []
        vector_layer_names = []
        vector_feature_mappings = {}  # Initialize a dictionary to store feature mappings for each layer

        for feature_column in feature_columns:
            unique_categories = gdf[feature_column].unique()
            category_to_int = {cat: i for i, cat in enumerate(unique_categories)}

            # Save mapping in the dictionary
            layer_name = f"{os.path.basename(file).replace('.geojson', '')}_{feature_column}"
            vector_feature_mappings[layer_name] = category_to_int

            # Prepare the shapes and values for rasterization
            shapes = ((geom, category_to_int[attr]) for geom, attr in zip(gdf.geometry, gdf[feature_column]) if attr in category_to_int)

            # Rasterize each feature column into a grid
            rasterized_layer = rasterize(
                shapes=shapes,
                out_shape=self.grid_size,
                fill=np.nan,
                transform=self.common_transform,
                dtype='float32'
            )

            # Add each rasterized layer to the list of layers, expanding the dimensions as needed
            vector_layers.append(np.expand_dims(rasterized_layer, axis=0))
            vector_layer_names.append(layer_name)

        # Concatenate all layers and return them with their names and mappings
        return np.concatenate(vector_layers, axis=0), vector_layer_names, vector_feature_mappings

    def process_line(self, file):
        buffer_lines = self.user_buffer_choice(file)
        buffer_distance_meters = self.get_buffer_distance_meters(file) if buffer_lines else 0
        gdf = gpd.read_file(file).to_crs(self.mask_gdf.crs)
        common_bounds = box(self.minx, self.miny, self.maxx, self.maxy)
        gdf_clipped = gdf[gdf.intersects(common_bounds)]

        if gdf_clipped.empty:
            print(f"Warning: No valid area for line data within the common grid for file {file}. Skipping...")
            raster_map = np.zeros(self.grid_size, dtype=np.float32)
            line_layer_name = f"{os.path.basename(file).replace('.geojson', '')}"
            return np.expand_dims(raster_map, axis=0), line_layer_name

        shapes = [(geom, 1) for geom in gdf_clipped.geometry if geom is not None]
        if shapes:
            binary_grid = rasterize(shapes=shapes, out_shape=self.grid_size, transform=self.common_transform, fill=0, dtype='uint8')
            x_res = self.common_transform[0]
            y_res = abs(self.common_transform[4])
            avg_resolution = (x_res + y_res) / 2
            pixel_distance = int(buffer_distance_meters / avg_resolution)

            if buffer_lines and pixel_distance > 0:
                use_exponential = self.user_decay_choice(file)
                if use_exponential:
                    raster_map = self.calculate_exponential_distance(binary_grid, max_distance=pixel_distance)
                else:
                    raster_map = self.calculate_distance(binary_grid, max_distance=pixel_distance)
            else:
                raster_map = binary_grid.astype(np.float32)
        else:
            print(f"No valid line geometries found in {file}. Skipping...")
            raster_map = np.zeros(self.grid_size, dtype=np.float32)

        line_layer_name = f"{os.path.basename(file).replace('.geojson', '')}"
        return np.expand_dims(raster_map, axis=0), line_layer_name

    def process_raster(self, file):
        if not self.mask_file:
            print("No mask file provided. Skipping raster processing.")
            return None, None

        with rasterio.open(file, 'r') as src:
            print(f"Processing file: {os.path.basename(file)}")
            raster_data_array = np.full(self.grid_size, np.nan, dtype=np.float32)

            # Check for nodata value and set a compatible default if necessary
            if src.nodata is None:
                # Choose a default nodata value within the valid range based on data type
                nodata_value = 0 if src.dtypes[0] == 'uint8' else np.nan
            else:
                nodata_value = src.nodata

            reproject(
                source=rasterio.band(src, 1),
                destination=raster_data_array,
                src_transform=src.transform,
                src_crs=self.crs,
                dst_transform=self.common_transform,
                dst_crs=self.crs,
                resampling=Resampling.nearest,
                src_nodata=nodata_value,   # Set src_nodata to match data type
                dst_nodata=np.nan          # Set dst_nodata to NaN for consistency
            )

        # Optionally replace NaN values with 0 if needed for processing
        raster_data_array = np.nan_to_num(raster_data_array, nan=0.0)  # Replace NaN with 0
        raster_name = os.path.basename(file).replace('.tiff', '').replace('.tif', '')
        return np.expand_dims(raster_data_array, axis=0), raster_name
    
    def process_parquet(self, file, parquet_features_to_process):
        """
        Processes a GeoParquet file, rasterizing selected numerical attributes to the common grid.

        Args:
            file (str): Path to the GeoParquet file.
            parquet_features_to_process (list): List of tuples containing (file, attribute) pairs to process.

        Returns:
            tuple: (rasterized_data, layer_names)
        """
        # Load the GeoParquet file
        gdf = gpd.read_parquet(file).to_crs(self.crs)
        feature_columns = [col for _, col in parquet_features_to_process if _ == file]

        print(f"Processing parquet file: {os.path.basename(file)}")

        # Initialize outputs
        parquet_layers = []
        layer_names = []

        for feature_column in feature_columns:
            # Check if the attribute exists in the GeoParquet file
            if feature_column not in gdf.columns:
                print(f"Warning: Attribute {feature_column} not found in {file}. Skipping...")
                continue

            # Prepare the shapes for rasterization
            shapes = ((geom, value) for geom, value in zip(gdf.geometry, gdf[feature_column]) if geom is not None and not np.isnan(value))

            # Rasterize the shapes
            rasterized_layer = rasterize(
                shapes=shapes,
                out_shape=self.grid_size,
                transform=self.common_transform,
                fill=np.nan,
                dtype='float32'
            )
            
            # Replace 0 or NaN values with the median of the layer
            median_value = np.nanmedian(rasterized_layer[rasterized_layer > 0])  # Exclude 0 from median calculation
            median_filled_layer = np.nan_to_num(rasterized_layer, nan=median_value)
            median_filled_layer[median_filled_layer == 0] = median_value
            
            # Apply filtering to fill gaps using a 50x50 box
            filtered_median = scipy.ndimage.uniform_filter(
                median_filled_layer, size=50, mode='mirror'
            )

            # Apply filtering to fill gaps using a 50x50 box (for original non-median data)
            #filtered_original = scipy.ndimage.uniform_filter(
            #    median_filled_layer, size=50, mode='mirror'
            #)
            
            # Overlay the original non-zero data onto the filtered result
            final_layer = filtered_median.copy()
            
            # Retain original data where it is non-zero
            original_data_mask = rasterized_layer == 0
            final_layer[original_data_mask] = rasterized_layer[original_data_mask]

            #final_layer = filtered_original        #uncomment to bypass median handling; make sure to uncomment filtering above too

            # Add the layer to the list, expanding dimensions for 3D consistency
            parquet_layers.append(np.expand_dims(final_layer, axis=0))
            layer_names.append(f"{os.path.basename(file).replace('.parquet', '')}_{feature_column}")

        # Combine layers into a 3D array if any were processed
        if parquet_layers:
            rasterized_data = np.concatenate(parquet_layers, axis=0)
            print(f"Processed {len(parquet_layers)} layers from {file}.")
        else:
            rasterized_data = np.expand_dims(np.zeros(self.grid_size, dtype='float32'), axis=0)
            print(f"No valid layers processed from {file}.")
            layer_names = []

        # Ensure layer names are flat
        layer_names = [str(name) for name in layer_names]

        if len(layer_names) != rasterized_data.shape[0]:
            raise ValueError(f"Mismatch between layer names and rasterized data layers. {len(layer_names)} names for {rasterized_data.shape[0]} layers.")

        return rasterized_data, list(layer_names)


    def get_buffer_size(self):
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        buffer_size = simpledialog.askinteger("Input", "Enter the target buffer size in meters:", minvalue=1)
        root.destroy()
        return buffer_size
    
    def process_target_cell(self, idx, cell, gdf, sindex):
        # Check if the cell intersects any polygon in the GeoDataFrame
        possible_matches_index = list(sindex.intersection(cell.bounds))
        possible_matches = gdf.iloc[possible_matches_index]
        intersects = possible_matches.intersects(cell).any()
    
        # Return binary value (1 for intersection, 0 otherwise)
        i = idx // self.grid_size[1]
        j = idx % self.grid_size[1]
        return i, j, 1 if intersects else 0

    def calculate_distance(self, arr, max_distance=20, dtype=np.float32):
        arr = np.asarray(arr, dtype=bool)
        dist = distance_transform_edt(~arr)
        normalized_dist = np.clip(1 - dist / max_distance, 0, 1)
        return normalized_dist.astype(dtype)
    
    def calculate_exponential_distance(self, arr, max_distance=20, dtype=np.float32):
        """
        Calculate an exponential decay distance map.

        Args:
            arr (np.ndarray): Binary input array (1 = feature, 0 = no feature).
            max_distance (int): Ground distance at which the value decays to approximately 0.
            dtype (type): Output array data type.

        Returns:
            np.ndarray: Array with exponential decay values between 1 and 0.
        """
        arr = np.asarray(arr, dtype=bool)
        dist = distance_transform_edt(~arr)
        # Calculate exponential decay with a scale factor such that it reaches ~0 at max_distance
        decay = np.exp(-dist / (max_distance / np.log(100)))  # Adjust decay rate
        decay[dist > max_distance] = 0  # Set values beyond max_distance to 0
        return decay.astype(dtype)

    def user_decay_choice(self, file):
        """
        Prompt the user to choose between linear or exponential decay for distance calculation.

        Args:
            file (str): File name to include in the prompt.

        Returns:
            bool: True if exponential decay is selected, False if linear decay is selected.
        """
        choice = {"exponential": None}

        def set_choice_exponential():
            choice["exponential"] = True
            window.destroy()

        def set_choice_linear():
            choice["exponential"] = False
            window.destroy()

        window = Tk()
        window.title("Choose Decay Option")
        label = Label(window, text=f"Choose decay method for {os.path.basename(file)}:")
        label.pack(pady=10)
        exponential_button = Button(window, text="Exponential Decay", command=set_choice_exponential)
        exponential_button.pack(side="left", padx=20, pady=20)
        linear_button = Button(window, text="Linear Decay", command=set_choice_linear)
        linear_button.pack(side="right", padx=20, pady=20)
        window.mainloop()
        return choice["exponential"]

    def user_buffer_choice(self, file):
        choice = {"buffer": None}

        def set_choice_buffer():
            choice["buffer"] = True
            window.destroy()

        def set_choice_rasterize():
            choice["buffer"] = False
            window.destroy()

        window = Tk()
        window.title("Choose Processing Option")
        label = Label(window, text=f"Would you like to buffer the lines (calculate distances) or just rasterize them for {os.path.basename(file)}?")
        label.pack(pady=10)
        buffer_button = Button(window, text="Buffer (Calculate Distance)", command=set_choice_buffer)
        buffer_button.pack(side="left", padx=20, pady=20)
        rasterize_button = Button(window, text="Rasterize Only", command=set_choice_rasterize)
        rasterize_button.pack(side="right", padx=20, pady=20)
        window.mainloop()
        return choice["buffer"]

    def get_buffer_distance_meters(self, file):
        root = Tk()
        root.withdraw()
        buffer_distance = None
        try:
            buffer_distance = simpledialog.askfloat(
                title=f"Input Buffer Distance for {os.path.basename(file)}",
                prompt="Please enter buffer distance in meters:"
            )
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number.")
            buffer_distance = None
        root.destroy()
        return buffer_distance
