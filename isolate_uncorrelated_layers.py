import xarray as xr
import pandas as pd
import numpy as np
import random
import os
import shutil

def load_data(file_path: str, nan_threshold: float = 0.9, zero_threshold: float = 0.9) -> pd.DataFrame:
    """
    Loads the NetCDF file, reshapes each layer into a DataFrame, 
    and excludes layers with NaN or zero values exceeding the threshold.
    
    Args:
        file_path (str): Path to the NetCDF file.
        nan_threshold (float): Maximum proportion of NaNs allowed for a layer to be included.
        zero_threshold (float): Maximum proportion of zero values allowed for a layer to be included.

    Returns:
        pd.DataFrame: DataFrame of the selected layers.
        list: List of layer names that meet the NaN and zero value threshold criteria.
    """
    ds = xr.open_dataset(file_path)
    combined_layers = ds["combined_layers"]
    layer_names = combined_layers.layer.values  # Assumes layer names are stored in the 'layer' dimension

    # Convert each layer to a flattened 1D array and store it in a dictionary, applying the NaN and zero filters
    data = {}
    selected_layer_names = []
    for layer_name in layer_names:
        layer_data = combined_layers.sel(layer=layer_name).values.flatten()
        nan_ratio = np.isnan(layer_data).mean()  # Calculate proportion of NaNs
        zero_ratio = (layer_data == 0).mean()     # Calculate proportion of zeros
        if nan_ratio < nan_threshold and zero_ratio < zero_threshold:
            data[layer_name] = layer_data
            selected_layer_names.append(layer_name)
        else:
            print(f"Layer '{layer_name}' excluded due to {nan_ratio:.2%} NaNs and {zero_ratio:.2%} zeros.")

    df = pd.DataFrame(data)
    return df, selected_layer_names


def calculate_correlation(df: pd.DataFrame, samples: int) -> pd.DataFrame:
    """Downsamples the DataFrame and calculates the correlation matrix, handling NaN values."""
    if samples > len(df):
        samples = len(df)  # Adjust sample size if greater than available data
    
    # Sample the DataFrame
    df_sampled = df.sample(n=samples, random_state=42)
    
    # Option 1: Fill NaNs with 0 (or another placeholder) to avoid skewing correlation values
    df_sampled = df_sampled.fillna(0)
    
    # Option 2: Drop rows with NaNs (use this if NaNs are infrequent and you want strict data handling)
    # df_sampled = df_sampled.dropna()
    
    # Calculate the correlation matrix
    correlation_matrix = df_sampled.corr()
    return correlation_matrix


def select_random_lowly_correlated_layers(correlation_matrix: pd.DataFrame, threshold: float = 0.3, target_count: int = 10, max_attempts: int = 1000) -> list:
    """
    Randomly selects a set of layers such that each pair within the set has a correlation below the threshold.
    
    Args:
        correlation_matrix: DataFrame of the correlation matrix.
        threshold: Maximum allowed correlation value for any pair of selected layers.
        target_count: Number of layers to return.
        max_attempts: Maximum number of attempts to find a suitable set.
    
    Returns:
        A list of selected layer names or the highest number of uncorrelated layers found.
    """
    layers = list(correlation_matrix.columns)
    best_selection = []
    
    for attempt in range(max_attempts):
        random.shuffle(layers)  # Randomize layer order each attempt
        selected_layers = []

        # Try to build a selection of target_count layers
        for layer in layers:
            # Check if this layer has correlations below the threshold with all already-selected layers
            if all(abs(correlation_matrix[layer][sel_layer]) < threshold for sel_layer in selected_layers):
                selected_layers.append(layer)
            
            # Stop if we've reached the target count
            if len(selected_layers) >= target_count:
                print(f"Found a set of {target_count} layers on attempt {attempt + 1}")
                return selected_layers
        
        # Update best selection if this attempt yields more uncorrelated layers
        if len(selected_layers) > len(best_selection):
            best_selection = selected_layers
            print(f"New best selection with {len(best_selection)} layers on attempt {attempt + 1}")
        
        # Periodic status update
        if (attempt + 1) % 10 == 0:
            print(f"Attempt {attempt + 1}: Current best selection has {len(best_selection)} layers")

    print(f"Unable to find a set of {target_count} layers with pairwise correlations below {threshold} after {max_attempts} attempts.")
    return best_selection  # Return the best selection found

def select_files(folder_path: str, selected_layers: list, output_folder: str):
    """
    Selects files from a folder that match a list of layer names and copies them to an output folder.
    
    Args:
        folder_path (str): Path to the folder containing the files.
        selected_layers (list): List of layer names to select (without extensions).
        output_folder (str): Path to the output folder where selected files will be copied.
    """
    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)
    
    # Convert selected layers to a set for faster lookups
    selected_layers_set = set(selected_layers)
    
    # Iterate over all files in the folder
    for filename in os.listdir(folder_path):
        # Get the file name without extension
        name_without_extension = os.path.splitext(filename)[0]
        
        # Check if this file matches one of the selected layer names
        if name_without_extension in selected_layers_set:
            # Copy the file to the output folder
            src_path = os.path.join(folder_path, filename)
            dst_path = os.path.join(output_folder, filename)
            shutil.copy2(src_path, dst_path)  # copy2 preserves metadata
            print(f"Copied: {filename}")

def main():
    # File path to the NetCDF file
    #file_path = '/Users/thowe/MinersAI Dropbox/Tyler Howe/ICB_data/testing/all_RS_layers.nc' # Replace with your NetCDF file path
    file_path = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ICB_data\testing\all_RS_layers.nc" 
    
    # Parameters
    samples = 500
    threshold = 0.97  # Maximum allowed correlation between any pair of selected layers
    target_count = 10  # Number of layers to select
    max_attempts = 1000  # Maximum number of attempts to try different random selections
    
    # Load and process data
    df, layer_names = load_data(file_path, nan_threshold=0.995, zero_threshold=0.995)
    correlation_matrix = calculate_correlation(df, samples)
    
    # Attempt to select layers with low correlations with each other
    selected_layers = select_random_lowly_correlated_layers(correlation_matrix, threshold, target_count, max_attempts)
    
    if len(selected_layers) < target_count:
        print(f"\nOnly {len(selected_layers)} layers found that meet the pairwise correlation criterion.")
    else:
        print(f"\nSelected {target_count} layers with pairwise correlations below {threshold}:")
    
    print(selected_layers)

    # Selection function
    #folder_path = '/Users/thowe/MinersAI Dropbox/Tyler Howe/ICB_data/geospatial_data/all_RS_layer'  # Replace with the path to the folder containing your files
    #output_folder = '/Users/thowe/MinersAI Dropbox/Tyler Howe/ICB_data/geospatial_data/uncorrelated_RS'  # Replace with the desired output folder path

    folder_path = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ICB_data\geospatial_data\all_RS_layer"
    output_folder = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ICB_data\geospatial_data\uncorrelated_RS"

    # Run the selection function
    select_files(folder_path, selected_layers, output_folder)

if __name__ == "__main__":
    main()