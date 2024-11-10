import xarray as xr
import pandas as pd
import numpy as np
import random
import matplotlib.pyplot as plt

def load_data(file_path: str, nan_threshold: float = 0.9, zero_threshold: float = 0.9) -> pd.DataFrame:
    ds = xr.open_dataset(file_path)
    combined_layers = ds["combined_layers"]
    layer_names = combined_layers.layer.values  

    data = {}
    selected_layer_names = []
    for layer_name in layer_names:
        layer_data = combined_layers.sel(layer=layer_name).values.flatten()
        nan_ratio = np.isnan(layer_data).mean()
        zero_ratio = (layer_data == 0).mean()
        if nan_ratio < nan_threshold and zero_ratio < zero_threshold:
            data[layer_name] = layer_data
            selected_layer_names.append(layer_name)
        else:
            print(f"Layer '{layer_name}' excluded due to {nan_ratio:.2%} NaNs and {zero_ratio:.2%} zeros.")
    df = pd.DataFrame(data)
    return df, selected_layer_names

def calculate_correlation(df: pd.DataFrame, samples: int) -> pd.DataFrame:
    if samples > len(df):
        samples = len(df)
    df_sampled = df.sample(n=samples, random_state=42).fillna(0)
    correlation_matrix = df_sampled.corr()
    return correlation_matrix

def select_random_lowly_correlated_layers(correlation_matrix: pd.DataFrame, threshold: float, target_count: int, max_attempts: int = 1000) -> list:
    layers = list(correlation_matrix.columns)
    best_selection = []
    for attempt in range(max_attempts):
        random.shuffle(layers)
        selected_layers = []
        for layer in layers:
            if all(abs(correlation_matrix[layer][sel_layer]) < threshold for sel_layer in selected_layers):
                selected_layers.append(layer)
            if len(selected_layers) >= target_count:
                return selected_layers
        if len(selected_layers) > len(best_selection):
            best_selection = selected_layers
    return best_selection

def main():
    file_path = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ICB_data\testing\all_RS_layers.nc"

    samples = 500
    target_count = 10
    max_attempts = 1000

    df, layer_names = load_data(
        file_path, 
        nan_threshold=0.995, 
        zero_threshold=0.995
    )
    
    correlation_matrix = calculate_correlation(df, samples)
    
    max_threshold = 0.99
    min_threshold = 0.89
    threshold_step = -0.01

    # Iteratively reduce threshold and collect results
    results = []
    for threshold in np.arange(max_threshold, min_threshold, threshold_step):
        selected_layers = select_random_lowly_correlated_layers(correlation_matrix, threshold, target_count, max_attempts)
        results.append({'Threshold': threshold, 'Selected_Layers': len(selected_layers)})
        print(f"Threshold {threshold:.2f}: Selected {len(selected_layers)} layers")

    # Convert results to a DataFrame for easy visualization or analysis
    results_df = pd.DataFrame(results)
    print("\nThreshold vs. Number of Layers Selected:")
    print(results_df)

    # Plotting the results
    plt.figure(figsize=(10, 6))
    plt.plot(results_df['Threshold'], results_df['Selected_Layers'], marker='o')
    plt.xlabel('Correlation Threshold')
    plt.xticks(np.arange(min_threshold, max_threshold + (-threshold_step), -threshold_step))
    plt.ylabel('Number of Selected Layers')
    plt.title('Number of Layers Selected vs Correlation Threshold')
    plt.grid()
    plt.gca().invert_xaxis()
    plt.show()

if __name__ == "__main__":
    main()
