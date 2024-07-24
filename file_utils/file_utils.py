import os
import shutil
import logging


def remove_file_or_directory(file_or_directory):
    try:
        try:
            os.remove(file_or_directory)
        except IsADirectoryError:
            shutil.rmtree(file_or_directory)
        logging.info(f"Removed: {file_or_directory}")
    except FileNotFoundError:
        pass