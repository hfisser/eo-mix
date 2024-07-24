import os
import sys
import logging
import numpy as np
import pandas as pd
import rasterio as rio
import geopandas as gpd
from glob import glob
from pathlib import Path
from datetime import datetime
from rasterio.mask import mask
from s1denoise import Sentinel1Image
#sys.path.append("./SnapGpt")
from SnapGpt.SnapGpt import SnapGpt
from skimage.morphology import binary_dilation
from geocoding.geocoding import geocode_S1_image_from_GCPS
#sys.path.append("./file_utils")
from file_utils.file_utils import remove_file_or_directory

FILE_CALIBRATION_GRAPH = "/home/henrik/Code/tools/SnapGpt/graphs/s1_radiometric_calibration.xml"  # SNAP GPT graph
FILE_BAND_MATH_GRAPH = "/home/henrik/Code/tools/SnapGpt/graphs/band_math.xml"  # SNAP GPT graph
PROJ_PATH = os.environ["PROJ_LIB"]


class S1Prep:
    def __init__(self, dir_safe=None, dir_out=None) -> None:
        self.dir_safe = dir_safe
        self.dir_out = os.path.dirname(dir_safe) if dir_out is None and dir_safe is not None else dir_out
        self.files_geocoded = dict()
        self.files_calibrated = None
        self.file_noise_removed_hv = None
        self.file_ia_geocoded = None
        self.stack_polarizations = None
        self.ia = None
        self.meta = None
        self.data = dict()

    def geocoded_files_exist(self):
        files_there = glob(os.path.join(self.dir_out, "{}*geocoded.tif".format(os.path.basename(self.dir_safe).split(".")[0])))
        if len(files_there) > 1:
            for file in files_there:
                logging.info(f"Already exists: {file}")
                if "ia_geo" in file:
                    self.file_ia_geocoded = file
                else:
                    self.files_geocoded[file.split("_")[-2]] = file
            return len(files_there) == 3
        else:
            return False

    def remove_noise_nansen_center(self, remove_thermal_noise_hv, remove_texture_noise_hv, use_esa_algorithm=False):
        s1 = Sentinel1Image(self.dir_safe)
        if all([remove_thermal_noise_hv, remove_texture_noise_hv]) or remove_texture_noise_hv:
            print("Remove thermal and texture noise")
            return s1.remove_texture_noise("HV")
        elif remove_thermal_noise_hv and use_esa_algorithm:
            print("Remove thermal noise with ESA algorithm")
            return s1.remove_thermal_noise("HV", algorithm="ESA")
        else:
            print("Remove thermal noise")
            return s1.remove_thermal_noise("HV")

    def calibrate(self, file_calibration_graph, remove_thermal_noise_hv=True, remove_texture_noise_hv=True, use_esa_algorithm=False):
        file_calibrated = self._get_file_name_calibrated(self.dir_safe)
        for file in glob(os.path.join(self.dir_safe, "measurement", "*.tiff")):
            with rio.open(file) as src:
                meta = src.meta
                data = src.read(1)
            #with rio.open(file, "w", **meta) as dst:  # write to ensure it's a GeoTiff (no COG, SNAP cannot handle it)
                #dst.write(data, 1)
        gpt = SnapGpt(file_calibration_graph)
        gpt.set_input(self.dir_safe)
        gpt.set_output(file_calibrated)
        gpt.set_output_format("GeoTiff")
        gpt.write_graph()
        gpt.execute()
        remove_noise = remove_thermal_noise_hv or remove_texture_noise_hv
        if remove_noise:
            try:
                hv = self.remove_noise_nansen_center(remove_thermal_noise_hv, remove_texture_noise_hv, use_esa_algorithm)
            except:
                logging.warning("Nansen noise removal did not work for: {}".format(os.path.basename(self.dir_safe)))
                file_nansen_failed = "nansen_noise_correction_failed.csv"
                log_failure = {"title": [os.path.basename(self.dir_safe)], "file": [self.dir_safe], "processing_date": datetime.now().strftime("%Y-%m-%d")}
                try:
                    nansen_failed = pd.read_csv(file_nansen_failed, index_col=0)
                except FileNotFoundError:
                    nansen_failed = pd.DataFrame(log_failure)
                else:
                    for column, value in log_failure.items():
                        nansen_failed.loc[len(nansen_failed), column] = value
                nansen_failed.to_csv(file_nansen_failed)
                remove_noise = False  # if noise correction fails (should rarely happen) don't do noise correction, but still process it
        with rio.open(file_calibrated) as src:
            meta = src.meta
            hv = hv if remove_noise else src.read(2)
            hh = src.read(1)
        meta.update(count=1)
        self.files_calibrated = self._get_file_names_polarizations(file_calibrated)
        hv[hh < 1e-4] = 0  # edges
        with rio.open(self.files_calibrated["hv"], "w", **meta) as dst:
            dst.write(hv, 1)
        hh[hh < 1e-4] = 0
        with rio.open(self.files_calibrated["hh"], "w", **meta) as dst:
            dst.write(hh, 1)
        os.remove(file_calibrated)
        return 0

    def geocode_backscatter(self, crs, resolution_target):
        for polarization, file_s1 in self.files_calibrated.items():  # by polarization
            self.files_geocoded[polarization] = os.path.join(self.dir_out, os.path.basename(file_s1.replace(".tif", "_geocoded.tif")))
            geocode_S1_image_from_GCPS(file_s1, self.dir_safe, self.files_geocoded[polarization], crs, resolution_target, overwrite=True, resampling="nearest", loglevel="DEBUG")  # Polar Stereographic, 40 m pixel spacing
        for file_s1 in self.files_calibrated.values():
            remove_file_or_directory(file_s1)  # remove calibrated files

    def geocode_incidence_angle(self, file_band_math_graph, crs, resolution_target):
        file_name = os.path.basename(self.dir_safe).replace(".SAFE", "")
        file_ia = os.path.join(self.dir_out, f"{file_name}_ia.tif")
        self.file_ia_geocoded = file_ia.replace(".tif", "_geocoded.tif")
        if os.path.exists(self.file_ia_geocoded):
            logging.info(f"Already exists: {self.file_ia_geocoded}")
        else:
            gpt = SnapGpt(file_band_math_graph)
            gpt.set_input(self.dir_safe)
            gpt.set_output(file_ia)
            gpt.set_output_format("GeoTiff")
            gpt.write_graph()
            gpt.execute()
            geocode_S1_image_from_GCPS(file_ia, self.dir_safe, self.file_ia_geocoded, crs, resolution_target, overwrite=True, resampling="nearest")
            remove_file_or_directory(file_ia)

    def read_s1(self, aoi, crop):
        for polarization, file in self.files_geocoded.items():
            with rio.open(file) as src:
                self.meta = src.meta
                if aoi is None:
                    self.data[polarization] = src.read(1)
                else:
                    self.data[polarization], transform = mask(src, list(aoi.to_crs(self.meta["crs"]).geometry), crop=crop, nodata=-1, indexes=1)  # read in aoi
                    shape = self.data[polarization].shape
                    self.meta.update(height=shape[0], width=shape[1], transform=transform)
        self.data["hh"] = self.data["hh"].astype(np.float32)
        self.data["hv"] = self.data["hv"].astype(np.float32)
        self.data["hh"][self.data["hh"] == -1] = np.nan
        self.data["hv"][self.data["hv"] == -1] = np.nan
        self.meta.update(nodata=np.nan)
        self.stack_polarizations = np.float32([self.data["hh"], self.data["hv"]])
        self.stack_polarizations[self.stack_polarizations == -1] = np.nan
    
    def read_ia(self, aoi, crop):
        with rio.open(self.file_ia_geocoded) as src:
            meta = src.meta
            if aoi is None:
                self.ia = src.read(1)
            else:
                self.ia, transform = margs
        with rio.open(self.file_ia_geocoded, "w", **meta) as dst:
            dst.write(self.ia, 1)

    def write_s1(self, edge_mask_distance=0):
        for polarization, file in self.files_geocoded.items():
            if edge_mask_distance == 0:
                pass
            else:
                dilation_window = np.ones((int(edge_mask_distance * 4), int(edge_mask_distance * 4)))  # for no data mask
                no_data = binary_dilation(self.data[polarization] == 0, dilation_window)  # mask edges with a buffer to exclude residuals from geocoding (why are they there?)
                self.data[polarization][no_data] = 0
            self.meta.update(dtype=self.data[polarization].dtype)
            with rio.open(file, "w", **self.meta) as dst:  # write masked data
                dst.write(self.data[polarization], 1)

    def preprocess_s1(self, crs, resolution_target, remove_thermal_noise_hv=False, remove_texture_noise_hv=False, in_decibels=True):
        self.calibrate(FILE_CALIBRATION_GRAPH, remove_thermal_noise_hv, remove_texture_noise_hv)
        self.geocode_backscatter(crs, resolution_target)
        self.geocode_incidence_angle(FILE_BAND_MATH_GRAPH, crs, resolution_target)
        pols = [pol.upper() for pol in list(self.files_geocoded.keys())]
        file_name = "{0}_{1}_{2}_rm_thermal_noise_hv{3}_rm_texture_noise_hv{4}.tif".format(os.path.basename(self.files_geocoded["hh"].split("_hh")[0]), crs, resolution_target, remove_thermal_noise_hv, remove_texture_noise_hv)
        file_out = os.path.join(self.dir_out, file_name)
        with rio.open(self.files_geocoded["hh"]) as src:
            meta = src.meta
        data = np.full((3, meta["height"], meta["width"]), dtype=np.float32, fill_value=np.nan)
        for i, (_, file) in enumerate(self.files_geocoded.items()):
            with rio.open(file) as src:
                channel = src.read(1)
                data[i] = self.in2db(channel) if in_decibels else channel
        with rio.open(self.file_ia_geocoded) as src:
            data[-1] = src.read(1)
        meta.update(count=data.shape[0])
        with rio.open(file_out, "w", **meta) as dst:
            dst.write(data[0], 1)
            dst.set_band_description(1, "_".join([pols[0], "DB"] if in_decibels else pols[0]))
            dst.write(data[1], 2)
            dst.set_band_description(2, "_".join([pols[1], "DB"] if in_decibels else pols[0]))
            dst.write(data[2], 3)
            dst.set_band_description(3, "incidence_angle")
        return file_out

    def cleanup(self):
        for file in self.files_geocoded.values():
            os.remove(file)
        os.remove(self.file_ia_geocoded)
            
    @staticmethod
    def in2db(a):
        return 10 * np.log10(np.absolute(a))

    @staticmethod
    def _get_file_names_polarizations(file):
        file_base = file.split(".")[0]
        file_hv = f"{file_base}_hv.tif"
        file_hh = file_hv.replace("hv", "hh")
        return {"hv": file_hv, "hh": file_hh}

    @staticmethod
    def _get_file_name_calibrated(dir_safe):
        return os.path.join(str(Path(dir_safe).parent), f"{os.path.basename(dir_safe)}_calibrated.tif")


if __name__ == "__main__":
    dir_data = "/media/henrik/DATA/raster/s1/41XNF/Tracking"
    for file_s1 in glob(os.path.join(dir_data, "*.SAFE")):
        print(file_s1)
        s1_prep = S1Prep(file_s1)
        s1_prep.preprocess_s1(3996, 40, True, True, in_decibels=True)
        s1_prep.cleanup()
