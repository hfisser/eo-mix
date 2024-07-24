import os
import sys
import logging
import numpy as np
import pandas as pd
import rasterio as rio
import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
from datetime import datetime
from rasterio.mask import mask
from shapely.validation import make_valid
from shapely.geometry import box, GeometryCollection, Polygon
from Plots.Map import Map

COLORS_BATHYMETRY = ["#000000", "#15151a", "#262a33", "#3a424d", "#4c5b66", "#607380", "#738c99", "#5c5f55", "#72756b", "#8f9289", "#afb2a8", "#dcddd9", "#edeeeb"]
BOUNDS_BATHYMETRY = [-3000, -2400, -1800, -1200, -600, -200, -50, 0, 0.1, 200, 400, 800, 1200]

dir_out = "/home/henrik/OneDrive/Research/npi_cruise_2024/maps/s1_acquisition_plans"
dir_aois = "/home/henrik/OneDrive/Research/npi_cruise_2023/data/aois"
file_plan = "/media/henrik/DATA/vector/acquisition_plans/S1A_2024/S1A_2024.gpkg"
file_bathymetry = "/home/henrik/OneDrive/Research/npi_cruise_2023/data/for_visuals/bathymetry.tif"
file_latitudes = "/media/henrik/DATA/vector/graticules/natural_earth/ne_110m_graticules_1.shp"
file_longitudes = "/media/henrik/DATA/vector/graticules/natural_earth/ne_110m_graticules_5.shp"
aoi = gpd.read_file(os.path.join(dir_aois, "aoi_fram_strait_large.gpkg")).to_crs("EPSG:3996")
aoi_small = gpd.read_file(os.path.join(dir_aois, "FS23_satsearch_area.geojson")).to_crs("EPSG:3996")
aoi_belgica_bank = gpd.read_file(os.path.join(dir_aois, "FS23_AOI.geojson")).to_crs("EPSG:3996")
#ship_track = gpd.read_file("")
date_start = "2024-08-10"
date_end = "2024-08-12"


class Visualizer:
    def __init__(self, file_acquisition_plan) -> None:
        self.plan = gpd.read_file(file_acquisition_plan)
        self.bathymetry = None
        self.meta_bathymetry = None
        self.map = None

    def clean_plan(self):
        self.plan.geometry = [g if g is None else make_valid(g) for g in self.plan.geometry]
        geometry_collections = self.plan[self.plan.geometry.type == "GeometryCollection"]
        if len(geometry_collections) > 0:
            try:
                self.plan.loc[self.plan.geometry.type == "GeometryCollection", "geometry"] = self._unpack_geometry_collection_in_gdf(geometry_collections).geometry
            except:
                logging.info("Could not unpack {} geometries wrapped in GeometryCollections".format(len(geometry_collections)))
        logging.info("Dropping {} invalid geometries".format(np.sum(~self.plan.is_valid)))
        self.plan = self.plan[self.plan.is_valid]

    def subset(self, aoi, aoi_small, start_date, end_date):
        self.plan = self.plan.to_crs(aoi.crs)
        #self.plan = gpd.sjoin(self.plan, aoi_small)
        self.plan.geometry = self.plan.geometry.make_valid()
        self.plan = self.plan.clip(aoi.buffer(-1000, cap_style=3))
        #self.plan = gpd.sjoin(self.plan.to_crs(aoi.crs), aoi, op="intersects")
        dates = [datetime.fromisoformat(date) for date in self.plan.ObservationTimeStart]
        later_than_start = np.float32([(date - datetime.fromisoformat(start_date)).days for date in dates]) >= 0
        earlier_than_end = np.float32([(date - datetime.fromisoformat(end_date)).days for date in dates]) <= 0
        self.plan = self.plan[later_than_start * earlier_than_end]

    def create_map(self, date, aoi_small, aoi_belgica_bank, dir_out, file_longitudes, file_latitudes):
        weekday = datetime.fromisoformat(date).strftime("%A")
        cmap, norm = self.get_bathymetry_colorbar()
        plan_date = self.plan[np.array(self.plan.date) == date]
        plan_date.to_file(os.path.join(dir_out, "{0}_{1}_s1_acquisitions.gpkg".format(date, weekday)))
        if len(plan_date) == 0:
            return
        self.map = Map(dir_out, 400)
        self.map.plot_raster_data(self.bathymetry, cmap=cmap, norm=norm, label_raster="Bathymetry & Elevation (m)")
        self.map.plot_polygon_on_raster(plan_date, self.meta_bathymetry["transform"], "#0e7d73", 0.6)
        for i, acquisition in plan_date.iterrows():
            coords = np.float32([[x, y] for x, y in acquisition["geometry"].exterior.coords])
            argmax = np.argmax(coords[:, 1])
            x, y = np.array(rio.transform.rowcol(self.meta_bathymetry["transform"], acquisition["geometry"].centroid.x, coords[argmax, 1]))[::-1]
            txt = "\n".join([
                acquisition["Mode"],
                acquisition["ObservationTimeStart"].split("T")[1], 
                acquisition["ObservationTimeStop"].split("T")[1],
                "(UTC)"])
            self.map.axes.text(np.clip(x, 0, self.bathymetry.shape[-1] - 600), y + 800, txt, fontsize=14, weight="bold")
        self.map.axes.set_title("Sentinel-1, {0}, {1}".format(weekday, date), fontsize=18)
        self.map.axes.set_xticklabels([])
        self.map.axes.set_xticks([])
        self.map.axes.set_yticklabels([])
        self.map.axes.set_yticks([])        
        for file in [file_latitudes, file_longitudes]:
            graticules = gpd.read_file(file).to_crs(self.map.crs).clip(aoi)
            graticules.geometry = graticules.buffer(1e-6)
            keep = np.bool8(["E" in value or "W" in value for value in graticules.display])
            keep = ~keep if file == file_latitudes else keep
            graticules = graticules[keep]
            self.map.plot_polygon_on_raster(graticules, self.meta_bathymetry["transform"], "grey", 1, 0.4)
        y = self.map.axes.get_ylim()[0] + 30
        self.map.axes.text(450, y, "-15°", fontsize=12)
        self.map.axes.text(850, y, "-10°", fontsize=12)
        self.map.axes.text(1200, y, "-5°", fontsize=12)
        self.map.axes.text(1550, y, "0°", fontsize=12)
        self.map.axes.text(1900, y, "5°", fontsize=12)
        self.map.axes.text(2250, y, "10°", fontsize=12)
        x = self.map.axes.get_xlim()[1] - 100
        self.map.axes.text(x, 200, "81°", fontsize=12)
        self.map.axes.text(x, 500, "80°", fontsize=12)
        self.map.axes.text(x, 800, "79°", fontsize=12)
        self.map.axes.text(x, 1100, "78°", fontsize=12)
        #self.map.plot_polygon_on_raster(aoi_small, self.meta_bathymetry["transform"], "#ef7327", 0)
        #self.map.plot_polygon_on_raster(aoi_belgica_bank, self.meta_bathymetry["transform"], "#efb527", 0)
        self.map.minimalistic_layout(self.map.axes)
        self.map.fig.savefig(os.path.join(dir_out, "{0}_{1}_s1_acquisitions.png".format(date, weekday)), dpi=300)
        self.map.fig.savefig(os.path.join(dir_out, "{0}_{1}_s1_acquisitions.pdf".format(date, weekday)), dpi=300)
        plt.close(self.map.fig)
        
    def get_dates(self):
        return visualizer.plan.ObservationTimeStart

    def add_dates_without_time(self):
        self.plan.date = [date.split("T")[0] for date in self.get_dates()]

    def read_bathymetry(self, file_bathymetry):
        with rio.open(file_bathymetry) as src:
            self.bathymetry = src.read(1)
            self.meta_bathymetry = src.meta

    def get_bathymetry_colorbar(self):
        cmap = mpl.colors.ListedColormap(COLORS_BATHYMETRY)
        bounds = BOUNDS_BATHYMETRY
        norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
        return cmap, norm

    def _unpack_geometry_collection_in_gdf(self, gdf):
        geoms_unpacked = []
        for geom in gdf.geometry:
            if isinstance(geom, GeometryCollection):
                unpacked = self._unpack_geometry_collection(geom)
                if len(unpacked) > 0:
                    geoms_unpacked.append(unpacked)
            else:
                geoms_unpacked.append(geom)
        return gpd.GeoDataFrame({"geometry": np.hstack(geoms_unpacked)}, crs=gdf.crs)

    @staticmethod
    def _unpack_geometry_collection(collection):
        geoms = []
        for geom in collection.geoms:
            if isinstance(geom, Polygon):
                geoms.append(geom)
        return geoms


if __name__ == "__main__":
    visualizer = Visualizer(file_plan)
    visualizer.clean_plan()
    visualizer.subset(aoi, aoi_small, date_start, date_end)
    visualizer.add_dates_without_time()
    visualizer.read_bathymetry(file_bathymetry)
    for date in np.unique(visualizer.plan.date):
        visualizer.create_map(date, aoi_small, aoi_belgica_bank, dir_out, file_longitudes, file_latitudes)
    