import fnmatch
import os
import subprocess
import time
import io
import re
import sys
import logging

from ractl_cmds import (
    attach_image,
    detach_all,
    list_devices,
)
from settings import *


def create_new_image(file_name, type, size):
    if file_name == "":
        file_name = "new_image." + str(int(time.time())) + "." + type
    else:
        file_name = file_name + "." + type

    return subprocess.run(
        ["truncate", "--size", f"{size}m", f"{base_dir}{file_name}"],
        capture_output=True,
    )


def delete_file(file_name):
    if os.path.exists(file_name):
        os.remove(file_name)
        return True
    else:
        return False


def unzip_file(file_name):
    import zipfile

    with zipfile.ZipFile(base_dir + file_name, "r") as zip_ref:
        zip_ref.extractall(base_dir)
        return True


def rascsi_service(action):
    # start/stop/restart
    return (
        subprocess.run(["sudo", "/bin/systemctl", action, "rascsi.service"]).returncode
        == 0
    )


def download_file_to_iso(scsi_id, url):
    import urllib.request

    file_name = url.split("/")[-1]
    tmp_ts = int(time.time())
    tmp_dir = "/tmp/" + str(tmp_ts) + "/"
    os.mkdir(tmp_dir)
    tmp_full_path = tmp_dir + file_name
    iso_filename = base_dir + file_name + ".iso"

    try:
        urllib.request.urlretrieve(url, tmp_full_path)
    except:
        # TODO: Capture a more descriptive error message
        return {"status": False, "msg": "Error loading the URL"}

    # iso_filename = make_cd(tmp_full_path, None, None) # not working yet
    iso_proc = subprocess.run(
        ["genisoimage", "-hfs", "-o", iso_filename, tmp_full_path], capture_output=True
    )
    if iso_proc.returncode != 0:
        return {"status": False, "msg": iso_proc}
    return attach_image(scsi_id, iso_filename, "SCCD")


def download_image(url):
    import urllib.request

    file_name = url.split("/")[-1]
    full_path = base_dir + file_name

    try:
        urllib.request.urlretrieve(url, full_path)
        return {"status": True, "msg": "Downloaded the URL"}
    except:
        # TODO: Capture a more descriptive error message
        return {"status": False, "msg": "Error loading the URL"}


def write_config(file_name):
    from json import dump
    try:
        with open(file_name, "w") as json_file:
            devices = []
            for device in list_devices()[0]:
                device_info = [device["id"], device["un"], device["type"], device["path"], \
                    "".join(device["params"]), device["vendor"], device["product"], \
                    device["revision"], device["block"]]
                # Don't store RaSCSI generated product info
                # It is redundant for all intents and purposes, and may cause trouble down the line
                if device_info[5] == "RaSCSI":
                    device_info[5] = device_info[6] = device_info[7] = None
                # Don't store block size info for CD-ROM devices
                # RaSCSI does not allow attaching a CD-ROM device with custom block size
                if device_info[2] == "SCCD":
                    device_info[8] = None
                devices.append(device_info)
            dump(devices, json_file)
        return {"status": True, "msg": f"Successfully wrote to file: {file_name}"}
    #TODO: better error handling
    except:
        logging.error(f"Could not write to file: {file_name}")
        return {"status": False, "msg": f"Could not write to file: {file_name}"}


def read_config(file_name):
    from json import load
    try:
        with open(file_name) as json_file:
            detach_all()
            devices = load(json_file)
            for row in devices:
                attach_image(row[0], row[2], row[3], int(row[1]), row[4], row[5], row[6], row[7], row[8])
        return {"status": True, "msg": f"Successfully read from file: {file_name}"}
    #TODO: better error handling
    except:
        logging.error(f"Could not read file: {file_name}")
        return {"status": False, "msg": f"Could not read file: {file_name}"}
