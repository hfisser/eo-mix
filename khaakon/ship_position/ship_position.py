import os
import shutil
import logging
import numpy as np
import pandas as pd
import geopandas as gpd
from datetime import datetime
from glob import glob
from shapely.geometry import Point, LineString

dir_tracks_in = "/khaakon/S2023007015_PKRONPRINSHAAKON_9566/CRUISE_LOG/TRACK"
dir_tracks_out = "/khaakon/Arbeidskatalog_tokt/2023007015/sea_ice/ship_track"


class ShipTrack:
    def __init__(self, dir_tracks_in, dir_tracks_out) -> None:
        self.dir_tracks_in = dir_tracks_in
        self.dir_tracks_out = dir_tracks_out
        self.files_tracks = []
        self.track = None

    def copy_track_files(self):
        for file_in in glob(os.path.join(dir_tracks_in, "*.csv")):
            file_out = os.path.join(self.dir_tracks_out, os.path.basename(file_in))
            logging.info(f"Copying: {file_in}")
            try:
                os.remove(file_out)
            except FileNotFoundError:
                pass
            shutil.copyfile(file_in, file_out)
            self.files_tracks.append(file_out)

    def extract_track(self):
        tracks = []
        for file in self.files_tracks:
            logging.info(f"Extracting track: {file}")
            tracks.append(self.read_track_date(file))
        self.track = gpd.GeoDataFrame(pd.concat(tracks))
        self.track.geoemtry = self.track.geometry
        self.track.crs = "EPSG:4326"
        self.track = self.track[np.bool8([geom is not None for geom in self.track.geometry])]
            
    def read_track_date(self, file_track):
        track = pd.read_csv(file_track, header=1, sep=",", usecols=["Time", "Air temp", "Longitude", "Latitude"], encoding="latin-1")
        positions = [self.extract_position(lon, lat) for lon, lat in zip(track["Longitude"], track["Latitude"])]
        gdf = gpd.GeoDataFrame(track.iloc[:, [0, -1]], geometry=positions, crs="EPSG:4326")
        date_splitted = os.path.basename(file_track).split(".")[0].replace("pos", "").split("-")        
        gdf["Date"] = "-".join([date_splitted[-1], date_splitted[-2], date_splitted[-3]])
        gdf["Date_Time"] = ["T".join([gdf["Date"].iloc[i], gdf["Time"].iloc[i]]) for i in gdf.index]
        return gdf

    def extract_position(self, lon, lat):
        try:
            return Point([self.format_coordinate(lon, "lon"), self.format_coordinate(lat, "lat")])
        except AttributeError:
            return None

    def downsample_in_time(self, minutes):
        return self.track.iloc[::minutes]

    def write_track(self, track, file_out):
        try:
            os.remove(file_out)
        except FileNotFoundError:
            pass
        file_tmp = "tmp.gpkg"
        track_df = pd.DataFrame(track)
        track_df["Longitude"] = [p.x for p in track.geometry]
        track_df["Latitude"] = [p.y for p in track.geometry]
        track_df.drop("geometry", axis=1)
        track.to_file(file_tmp)
        track_df.to_csv(file_tmp.replace("gpkg", "csv"))
        shutil.copyfile(file_tmp, file_out)
        shutil.copyfile(file_tmp.replace("gpkg", "csv"), file_out.replace("gpkg", "csv"))
        os.remove(file_tmp)
        os.remove(file_tmp.replace("gpkg", "csv"))

    @staticmethod
    def format_coordinate(coordinate, which):
        splitted = coordinate.split(" ")
        coord = splitted[0]
        formatted = np.float32(float(coord[:3]) if which == "lon" else float(coord[:2]))
        formatted += float(coord[3:]) / 60 if which == "lon" else float(coord[2:]) / 60
        return formatted if splitted[1] in ["N", "E"] else -formatted


if __name__ == "__main__":
    ship_track = ShipTrack(dir_tracks_in, dir_tracks_out)
    ship_track.copy_track_files()
    ship_track.extract_track()
    ship_track.write_track(ship_track.track, os.path.join(dir_tracks_out, "fs2023_ship_track_1minute.gpkg"))
    ship_track.write_track(ship_track.downsample_in_time(10), os.path.join(dir_tracks_out, "fs2023_ship_track_10minutes.gpkg"))
    ship_track.write_track(ship_track.downsample_in_time(60), os.path.join(dir_tracks_out, "fs2023_ship_track_60minutes.gpkg"))
