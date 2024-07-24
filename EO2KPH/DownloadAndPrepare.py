import os
import sys
import shutil
import argparse
import geopandas as gpd
from glob import glob
#sys.path.append("./S1Prep")
from S1Prep.S1Prep import S1Prep
from copernicus_finder.S1_search_download import download_sentinel_products

USR = "henrik.fisser@uit.no"
PW = "ImmAdibUiT@Tm2022"
SECRET = "HA4W WT2I PIZD OULQ NQ2D KN3U ONUF C3CK"

#parser = argparse.ArgumentParser(prog="DownloadAndPrepare")
#try:
#    parser.add_argument("file_acquisitions", type=str)
#    parser.add_argument("dir_data_s1", type=str)
#    args = parser.parse_args()
#except:
args = dict()
args["file_acquisitions"] = "/media/henrik/DATA/FS_Cruise_2024/data/acquisition_records/s1_acquisitions_2024-07-23_122930_2024-07-24_122930.gpkg"
args["dir_data_s1"] = "/media/henrik/DATA/FS_Cruise_2024/data/s1"


class DownloadAndPrepare:
    def __init__(self, file_acquisitions) -> None:
        self.acqs = gpd.read_file(file_acquisitions)
        self.file_acquisitions = file_acquisitions

    def download_and_prepare(self, dir_data_s1):
        for i, acq in self.acqs.iterrows():
            dir_unzip = os.path.join(dir_data_s1, acq["title"])
            dir_zip = os.path.join(dir_data_s1, "{}.zip".format(acq["open_id"]))
            file_exists = self._exists(acq, dir_unzip)
            if file_exists[-1]:  # output exists                
                file_geocoded = glob(os.path.join(self._get_dir_out(dir_unzip), "*{}*".format(acq["title"])))[0]
                print("Already exists:", file_geocoded)
            elif file_exists[0]:  # ZIP exists
                print("ZIP folder exists:", dir_zip)
                shutil.unpack_archive(dir_zip, dir_unzip)
            else:
                download_sentinel_products({acq["open_id"] : acq["title"]}, dir_data_s1, USR, PW, SECRET)  # then download data
                shutil.unpack_archive(dir_zip, dir_unzip)  # now ZIP exists
            if not file_exists[1]:  # if output doesn't exists, prepare data
                file_geocoded = self.prepare(dir_unzip)
            self.acqs.loc[i, "file_geocoded"] = file_geocoded
        self.acqs.to_file(self.file_acquisitions)
        
    def _exists(self, acq, dir_unzip):
        do = self._get_dir_out(dir_unzip)
        zip_exists = len(glob(os.path.join(do, "*{}*.zip".format(acq["open_id"])))) > 0
        #safe_exists = os.path.exists(dir_unzip)
        output_exists = len(glob(os.path.join(do, "{}*.tif".format(acq["title"].split(".")[0])))) > 0
        return zip_exists, output_exists

    @staticmethod
    def _get_dir_out(dir_unzip):
        return os.path.dirname(dir_unzip)
    
    def prepare(self, dir_unzip):
        dir_safe = glob(os.path.join(dir_unzip, "*.SAFE"))[0]
        s1_prep = S1Prep(dir_safe, self._get_dir_out(dir_unzip))
        file_geocoded = s1_prep.preprocess_s1(3996, 40, False, False, in_decibels=True)
        s1_prep.cleanup()
        return file_geocoded


if __name__ == "__main__":
    dp = DownloadAndPrepare(args["file_acquisitions"])
    dp.download_and_prepare(args["dir_data_s1"])
