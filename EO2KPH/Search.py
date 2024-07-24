import os
import json
import logging
import argparse
import numpy as np
import pandas as pd
import rasterio as rio
import geopandas as gpd
from glob import glob
from osgeo import ogr
from shapely.geometry import shape
from datetime import datetime, timedelta, timezone
from copernicus_finder.S1_search_download import query_sentinel_products

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

parser = argparse.ArgumentParser(prog="Search")
try:
    parser.add_argument("file_aoi", type=str)
    parser.add_argument("dir_data", type=str)
    args = parser.parse_args()
except:
    args = dict()
    args["file_aoi"] = "/media/henrik/DATA/FS_Cruise_2024/aois/aoi.gpkg"
    args["dir_data"] = "/media/henrik/DATA/FS_Cruise_2024/data"


class Search:
    def __init__(self, dir_data) -> None:
        self.time_range = self._get_time_range()
        self.acqs_s1 = None
        self.dir_data = dir_data
        self.dir_s1 = os.path.join(self.dir_data, "s1")
        self.dir_acquisitions = os.path.join(self.dir_data, "acquisition_records")
        self.make_directories()
    
    def make_directories(self):
        for directory in [self.dir_s1, self.dir_acquisitions]:
            try:
                os.mkdir(directory)
            except FileExistsError:
                pass
        
    def search(self, file_aoi):
        file_aoi = self._aoi_to_geojson(file_aoi)
        response = query_sentinel_products("S1", file_aoi, self.time_range[0], self.time_range[1], sensor_mode="EW")
        self.acqs_s1 = gpd.GeoDataFrame()
        if len(response) == 0:
            logging.info("No acquisitions in time range: {0} - {1}".format(self.time_range[0], self.time_range[1]))
        for key, acq in response.items():
            idx = len(self.acqs_s1)
            for property, value in acq["properties"].items():
                try:
                    self.acqs_s1.loc[idx, property] = value
                except ValueError:  # nested dicts, omit this value
                    continue
            self.acqs_s1.loc[idx, "open_id"] = key
        self._filter_duplicates()
        self.acqs_s1 = gpd.GeoDataFrame(self.acqs_s1)
        self.acqs_s1.geometry = [shape(json.loads(ogr.CreateGeometryFromGML(gml).ExportToJson())) for gml in self.acqs_s1["gmlgeometry"]]
        self.acqs_s1.crs = "EPSG:4326"

    def write_acquisitions(self):
        file_out = os.path.join(os.path.join(self.dir_acquisitions, "s1_acquisitions_{0}_{1}.gpkg".format(self.time_range[0].replace(" ", "_"), self.time_range[1].replace(" ", "_")))).replace(":", "")
        drop_idxs = []
        for i, acq in self.acqs_s1.iterrows():
            if input("{}    Keep acquisition? [y/n] ".format(acq["title"])).lower() == "n":
                drop_idxs.append(i)
        for i in drop_idxs:
            self.acqs_s1.drop(index=i, inplace=True)
        self.acqs_s1.index = list(range(len(self.acqs_s1)))
        try:
            del self.acqs_s1["links"]
        except KeyError:
            pass
        self.acqs_s1.to_file(file_out)
        print(f"Acquisition records written to: {file_out}")
    
    def _filter_duplicates(self):
        self.acqs_s1["title_clean"] = ["_".join(title.split("_")[:8]) for title in self.acqs_s1.title]
        self.acqs_s1["keep"] = True
        for i, row_a in self.acqs_s1.iterrows():
            for j, row_b in self.acqs_s1.iterrows():
                if i == j:
                    continue
                if row_a["title_clean"] == row_b["title_clean"]:
                    timeliness_match = ("fast" in row_a["timeliness"].lower() and not "fast" in row_b["timeliness"].lower())
                    self.acqs_s1.loc[i, "keep"] = "COG" not in row_a["title"] and timeliness_match  # either COG or the timeliness
        self.acqs_s1 = self.acqs_s1[self.acqs_s1["keep"]]
        self.acqs_s1.index = list(range(len(self.acqs_s1)))

    @staticmethod
    def _aoi_to_geojson(file_aoi):
        file_aoi_geojson = ".".join([file_aoi.split(".")[0], "geojson"])
        if file_aoi.split(".")[-1] != "geojson":            
            gpd.read_file(file_aoi).to_file(file_aoi_geojson)
        return file_aoi_geojson
    
    @staticmethod
    def _get_time_range():
        t1 = datetime.now(timezone.utc)
        t0 = t1 - timedelta(days=1)
        return t0.strftime(TIME_FORMAT), t1.strftime(TIME_FORMAT)


if __name__ == "__main__":
    searcher = Search(args["dir_data"])
    searcher.search(args["file_aoi"])
    searcher.write_acquisitions()
