import os
import shutil
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

file_assist = "/khaakon/Arbeidskatalog_tokt/2023007015/sea_ice/ASSIST/Kronprins Haakon-20230830-20230913.csv"


if __name__ == "__main__":
    df = pd.read_csv(file_assist)
    df = df[~np.isnan(df.LAT) * ~np.isnan(df.LON)]
    gdf = gpd.GeoDataFrame(df)
    gdf.geometry = [Point(lon, lat) for lon, lat in zip(df.LON, df.LAT)]
    gdf.crs = "EPSG:4326"
    file_out_tmp = os.path.join(os.getcwd(), "tmp.gpkg")
    gdf.to_file(file_out_tmp)
    shutil.copyfile(file_out_tmp, file_assist.replace(".csv", "_geometry_file.gpkg"))
    os.remove(file_out_tmp)
