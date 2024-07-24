import os
import numpy as np
import rasterio as rio
import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
from glob import glob
from Plots.Plot import Plot
from shapely.geometry import box, Point, Polygon

EPSG_4326 = "EPSG:4326"
MAX_S2 = 0.3


class Map(Plot):
    def __init__(self, dir_plot, dpi, crs="EPSG:3996") -> None:
        super().__init__(dir_plot, dpi, None)
        self.crs = crs  # polar stereographic
        self.axes = None
        self.extent = None
        self.y_extent = None

    def setup_map(self):
        if self.axes is None:  # else plot on existing ax
            self.create_figure(1, 1, (6, 5))

    def plot_vector_data(self, vector_data, fillcolors, alphas, linewidth=3, plot_limits=None):
        self.setup_map()
        for data, fillcolor, alpha in zip(vector_data, fillcolors, alphas, linewidth):
            self._plot_vectors(data, fillcolor, alpha)
        if plot_limits is not None:
            self.axes.set_ylim(float(plot_limits[1]), float(plot_limits[3]))
            self.axes.set_xlim(float(plot_limits[0]), float(plot_limits[2]))
        self.map_extent()
        #self.add_graticules()
        #self.labels_to_degrees()
        self.fig.tight_layout()

    def plot_polygon_on_raster(self, polygon_data, transform, fillcolor, alpha, linewidth=3):
        #if polygon_data.crs == "EPSG:3996":
            #geoms_reprojected = list(polygon_data.geometry)
        #else:
        geoms_reprojected = []
        for _, geom in polygon_data.to_crs(self.crs).iterrows():
            geoms_reprojected.append(self.project_polygon_on_raster(gpd.GeoSeries(geom["geometry"]), transform))
        self._plot_vectors(gpd.GeoSeries(np.hstack(geoms_reprojected)), fillcolor, alpha, linewidth)  

    def plot_raster_data(self, raster_data, vmin=None, vmax=None, bounds=None, cmap="gray", norm=None, label_raster=None):
        self.setup_map()
        extent = bounds if bounds is None else [bounds.left, bounds.right, bounds.bottom, bounds.top]  # matplotlib bounds: different xy sorting
        ax = self.axes.imshow(raster_data, vmin=vmin, vmax=vmax, extent=extent, cmap=cmap, norm=norm)
        self.map_extent()
        #if len(raster_data.shape) == 2:
            #self.fig.colorbar(ax, shrink=0.5, label=label_raster, orientation="horizontal")
        self.fig.tight_layout()

    def map_extent(self):
        xlim, ylim = self.axes.get_xlim(), self.axes.get_ylim()
        bounding_point = [gpd.GeoDataFrame({"geometry": [p]}, crs=self.crs).to_crs(EPSG_4326).geometry.iloc[0] for p in [Point(xlim[0], ylim[1]), Point(xlim[1], ylim[0])]]
        self.extent = gpd.GeoDataFrame({"geometry": [box(xlim[0], ylim[0], xlim[1], ylim[1])]}, crs=self.crs).to_crs(EPSG_4326)
        self.y_extent = bounding_point[0].y - bounding_point[1].y
        
    def add_graticules(self, file_graticule_dummy):
        spacings_available = np.float32([int(file.split(".shp")[0].split("_")[-1]) for file in glob(file_graticule_dummy.replace("1.shp", "*.shp"))])
        spacings_available_degrees = np.hstack([spacings_available[spacings_available == 1], spacings_available[spacings_available > 1] / 60])  # those provided in arc minutes: to degrees
        spacing = int(spacings_available[np.argmin(np.abs(np.subtract(spacings_available_degrees, self.y_extent / 2)))])
        file_graticules = file_graticule_dummy.replace("1.shp", "{}.shp".format(spacing))
        graticules = gpd.read_file(file_graticules).to_crs(self.crs).clip(self.extent.to_crs(self.crs))
        graticules.plot(ax=self.axes, color="grey")

    def labels_to_degrees(self):
        yticks, xticks = self.axes.get_yticks(), self.axes.get_xticks()
        points_y = gpd.GeoDataFrame({"geometry": [Point(xticks[0], y) for y in yticks]}, crs=self.crs).to_crs(EPSG_4326)
        points_x = gpd.GeoDataFrame({"geometry": [Point(x, yticks[0]) for x in xticks]}, crs=self.crs).to_crs(EPSG_4326)
        self.axes.set_xticklabels(np.round([p.x for p in points_x.geometry], 2))
        self.axes.set_yticklabels(np.round([p.y for p in points_y.geometry], 2))

    def labels_to_degrees_from_aoi(self, aoi):
        nx, ny = len(self.axes.get_xticklabels()), len(self.axes.get_yticklabels())
        xmin, ymin, xmax, ymax = aoi.total_bounds
        xs, ys = np.linspace(xmin, xmax, nx), np.linspace(ymin, ymax, ny)[::-1]
        self.axes.set_xticklabels(np.round(xs, 2))
        self.axes.set_yticklabels(np.round(ys, 2))

    def _plot_vectors(self, data, fillcolor, alpha, linewidth=3):
        facecolor = "none" if alpha == 0 else fillcolor
        alpha = 1 if facecolor == "none" else alpha
        edgecolor = fillcolor
        kwargs = dict(ax=self.axes, facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth, alpha=alpha)
        try:
            data.to_crs(self.crs).geometry.plot(**kwargs)
        except ValueError:
            data.plot(**kwargs)

    @staticmethod
    def prepare_s2_raster_for_plot(data):
        data[data > 1e+4] = 0
        data = np.multiply(np.float32(data), 255 * MAX_S2 * 10 * 1e-4)
        data[data > 255] = 255
        data = data.astype(np.int16).swapaxes(0, 2).swapaxes(0, 1)
        return data

    @staticmethod
    def prepare_s1_raster_for_plot(data):
        data = in2db(data)
        data[~np.isfinite(data)] = np.nan
        return data

    @staticmethod
    def project_polygon_on_raster(polygons, transform):
        polygons_reprojected = []
        for geom in list(polygons.geometry.explode().geometry):
            coords_reprojected = []
            for xy in list(geom.exterior.coords):
                coords_reprojected.append(np.array(rio.transform.rowcol(transform, xy[0], xy[1]))[::-1])
            polygons_reprojected.append(Polygon(coords_reprojected))
        return polygons_reprojected
