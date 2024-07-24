import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from glob import glob
from datetime import datetime

FORMAT_SUFFIXES = ["gpkg", "geojson", "shp"]

dir_data = "/media/henrik/DATA/playground/vector_driver_test"
file_small = os.path.join(dir_data, "small_file.gpkg")
file_large = os.path.join(dir_data, "large_file.gpkg")


def compare_drivers(file_small, file_large):
    driver_comparison = pd.DataFrame()
    for i, format_suffix in enumerate(FORMAT_SUFFIXES):
        driver_comparison.loc[i, "Format"] = format_suffix.upper()
        for data_size, file in zip(["small", "large"], [file_small, file_large]):
            duration = test_duration(file, format_suffix)
            for key, value in duration.items():
                driver_comparison.loc[i, f"{key}_{data_size}"] = value
    dir_plot = os.path.dirname(file_small)
    plot_comparison(driver_comparison, "small", dir_plot)
    plot_comparison(driver_comparison, "large", dir_plot)


def plot_comparison(driver_comparison, data_size, dir_plot):
    ylabel_duration = "ms"
    colors = ["#6fa8e5", "#e5d86f", "#e35d7b"]
    kwargs = dict(width=0.4, color=colors, tick_label=FORMAT_SUFFIXES)
    fig, axes = plt.subplots(1, 3, figsize=(8, 3))
    axes[0].bar(x=[0, 0.5, 1], height=driver_comparison[f"d_write_{data_size}"], **kwargs)
    axes[0].set_ylabel(ylabel_duration)
    axes[0].set_title("Read duration")
    axes[1].bar(x=[2, 2.5, 3], height=driver_comparison[f"d_read_{data_size}"], **kwargs)
    axes[1].set_ylabel(ylabel_duration)
    axes[1].set_title("Write duration")
    axes[2].bar(x=[4, 4.5, 5], height=driver_comparison[f"size_disk_{data_size}"], **kwargs)
    axes[2].set_title("File size")
    axes[2].set_ylabel("MB")
    for ax in axes:
        ax.set_xticklabels([suffix.upper() for suffix in FORMAT_SUFFIXES])
        for location in ["left", "right", "top", "bottom"]:
            ax.spines[location].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(dir_plot, f"vector_driver_comparison_{data_size}_file.png"), dpi=300)


def test_duration(file, format_suffix):
    gdf = gpd.read_file(file)
    file_out = "{0}_TMP.{1}".format(file.split(".")[0], format_suffix)  # temporary file in format to be tested
    d_write = duration_write(gdf, file_out)
    gdf = None  # not necessary, just to make it clear
    d_read, gdf = duration_read(file_out)
    size_disk = file_size(file_out)
    size_memory = sys.getsizeof(gdf) / 1e+6  # in MB
    for file in glob(os.path.join(os.path.dirname(file_out), "*TMP*")):  # for the SHP stuff
        os.remove(file)
    return dict(d_write=d_write, d_read=d_read, size_disk=size_disk, size_memory=size_memory)


def file_size(file):
    size = os.path.getsize(file) / 1e+6  # in MB
    if ".shp" in file:
        size += np.sum([os.path.getsize(file.replace(".shp", f".{suffix}")) / 1e+6 for suffix in ["shx", "prj", "dbf", "cpg"]])  # for the SHP stuff
    return size


def duration_write(gdf, file_out):
    t0 = datetime.now()
    gdf.to_file(file_out)
    return (datetime.now() - t0).total_seconds() * 1000  # miliseconds


def duration_read(file_in):
    t0 = datetime.now()
    gdf = gpd.read_file(file_in)
    return (datetime.now() - t0).total_seconds() * 1000, gdf



if __name__ == "__main__":
    compare_drivers(file_small, file_large)    
