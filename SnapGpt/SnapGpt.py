import os
import subprocess
import numpy as np
from glob import glob
from xml.etree import ElementTree as ET


class SnapGpt:
    def __init__(self, file_graph) -> None:
        self.file_graph = file_graph
        self._graph = ET.parse(file_graph)
        self._root = self._graph.getroot()
        self._file_graph_tmp = None

    def set_input(self, file_input):
        self._set_io("i", file_input)

    def set_output(self, file_output):
        self._set_io("o", file_output)
    
    def set_output_format(self, format):
        self._set_io("f", format)
    
    def _set_io(self, which, file):
        value = "file" if which in ["i", "o"] else "formatName"
        for node in self._root.findall("node"):
            if node.attrib["id"] == {"i": "Read", "o": "Write", "f": "Write"}[which]:
                file_element = node.findall("parameters")[0].find(value)
                file_element.text = file
                break

    def write_graph(self):
        self._file_graph_tmp = self.file_graph.replace(".xml", "_tmp.xml")
        with open(self._file_graph_tmp, "w") as f:
            self._graph.write(f, encoding="unicode")
           
    def execute(self):
        command = f"gpt {self._file_graph_tmp}"
        subprocess.run(command, shell=True)
        os.remove(self._file_graph_tmp)


if __name__ == "__main__":

    file_graph = "/home/henrik/Code/tools/SnapGpt/graphs/s1_radiometric_calibration.xml"
    file_grpah = "/home/henrik/Code/tools/SnapGpt/graphs/band_math.xml"

    snap_gpt = SnapGpt(file_graph)
    snap_gpt.set_input("/home/henrik/Data/raster/s1/S1A_EW_GRDM_1SDH_20210802T031405_20210802T031509_039045_049B66_E4EE/S1A_EW_GRDM_1SDH_20210802T031405_20210802T031509_039045_049B66_E4EE.SAFE")
    snap_gpt.set_output("/home/henrik/Data/raster/s1/test.tif")
    snap_gpt.set_output_format("GeoTiff")
    snap_gpt.write_graph()
    snap_gpt.execute()
