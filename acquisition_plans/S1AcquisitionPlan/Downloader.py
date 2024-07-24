import os
import shutil
import zipfile
import logging
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
from glob import glob
from tqdm import tqdm
from osgeo import ogr
from shapely import wkt
from datetime import datetime
from shapely.geometry import Polygon

DRIVER_LIBKML = ogr.GetDriverByName("LIBKML")
FIELD_NAMES = {"SatelliteId": 11, "Mode": 13, "Swath": 14, "Polarization": 15, "ObservationTimeStart": 16, "ObservationTimeStop": 17, "ObservationDuration": 18, "OrbitAbsolute": 19, "OrbitRelative": 20}

#urls = pd.DataFrame(dict(satellite="S1A", year="2023", url="https://sentinels.copernicus.eu/documents/d/sentinel/s1a_mp_user_20230823t174000_20230912t194000"), index=[0])
urls = pd.DataFrame(dict(satellite="S1A", year="2024", url="https://sentinel.esa.int/documents/d/sentinel/s1a_mp_user_20240724t174000_20240813t194000"), index=[0])

dir_plans = "/media/henrik/DATA/vector/acquisition_plans"
sensors = ["S1A"]


class Downloader():
    def __init__(self, directory) -> None:
        self._directory = directory
        self._files_plans = None
        self._file_plans_gpkg = None
        self._plans = None

    def download_plan(self, sensor, year, urls):
        folder = os.path.join(self._directory, "_".join([sensor, str(year)]))
        self._file_plans_gpkg = os.path.join(folder, "{}.gpkg".format(os.path.basename(folder)))
        if os.path.exists(self._file_plans_gpkg):
            logging.info("Already exists: {}".format(self._file_plans_gpkg))
            return 0
        try:
            os.mkdir(folder)
        except FileExistsError:
            if len(os.listdir(folder)) > 0:
                logging.info("Already exists: {}. Please check if all files are there".format(folder))
                self._files_plans = glob(os.path.join(folder, "*.kml"))
                return 1
        try:
            url = urls[(urls["year"] == str(year)) & (urls["satellite"] == sensor)]["url"].iloc[0]
        except IndexError:
            logging.info("No url for sensor {0} and year {1}".format(sensor, year))
            return None
        file = os.path.join(self._directory, url.split("/")[-1])  # file out
        req = requests.get(url, verify=False)  # verify=False, otherwise SSL error (but verification would be safer)
        with open(file, "wb") as f:
            f.write(req.content)
        try:
            self._extract(file, folder)
        except zipfile.BadZipFile:  # it's KML already, not a ZIP that includes several KMLs
            shutil.copyfile(file, os.path.join(folder, ".".join([os.path.basename(file), "kml"])))
        print("Downloaded: {} files".format(len(os.listdir(folder))))
        os.remove(file)  # remove original KML or ZIP
        self._files_plans = glob(os.path.join(folder, "*.kml"))  # KML files
        return 1

    def plans_to_gpkg(self):
        if self._files_plans is None or len(self._files_plans) == 0:
            raise ValueError("No acquisition plan files on disk")
        else:
            self._plans = [DRIVER_LIBKML.Open(file_plan) for file_plan in self._files_plans]
        acquisitions = gpd.GeoDataFrame()
        for i in tqdm(range(len(self._plans))):
            for layer in self._plans[i]:
                crs = "EPSG:{}".format(layer.GetSpatialRef().GetAuthorityCode(None))
                for feature in layer:
                    idx_row = len(acquisitions)
                    acquisitions.loc[idx_row, "geometry"] = Polygon(wkt.loads(feature.GetGeometryRef().ExportToWkt()))  # Linearring to Polygon
                    for key, idx_field in FIELD_NAMES.items():
                        acquisitions.loc[idx_row, key] = feature[idx_field]
        acquisitions = gpd.GeoDataFrame(acquisitions, geometry=acquisitions.buffer(1e-12), crs=crs)
        acquisitions.to_file(self._file_plans_gpkg, driver="GPKG")
        print("Saved:", self._file_plans_gpkg)

    @staticmethod
    def _extract(file, folder):
        with zipfile.ZipFile(file, "r") as zip:
            zip.extractall(folder)  # contains the KML files-
            folders = glob(os.path.join(folder, "*{}".format(os.sep)))
            if len(folders) > 0:  # it's a folder: sensor-specific folder structure from 2017
                for f in glob(os.path.join(folders[0], "*.kml")):  # all kml files
                    shutil.copyfile(f, os.path.join(folder, os.path.basename(f)))  # same structure for all years by copying
                shutil.rmtree(folders[0])


if __name__ == "__main__":
    for sensor in sensors:
        for year in range(2024, 2025):
            logging.info(" ".join([str(sensor), str(year)]))
            downloader = Downloader(dir_plans)
            return_code = downloader.download_plan(sensor, year, urls)
            if return_code:  # GPKG doesn't exist yet
                downloader.plans_to_gpkg()
            else:
                print("Already there:", downloader._file_plans_gpkg)
