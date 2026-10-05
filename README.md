Various utilities for accessing Copernicus data. Primary purpose is to quickly search and download Sentinel-1 data, using EO2KPH. Note that the code needs updating in terms of the search and download functionalities using CREODIAS or CDSE. Advice: (1) Install https://github.com/DHI-GRAS/creodias-finder, (2) replace the query_sentinel_products by a suitable wrapper around the creodias_finder query function (3) replace download_sentinel_products by a suitable wrapper around the creodias_finder download function.


Requirements: See required Python packages. Running the Sentinel-1 preprocessing requires the SNAP GPT executable in the PATH.
