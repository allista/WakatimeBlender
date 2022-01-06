import os
import shutil
import ssl
import threading
import urllib
import urllib.error
import urllib.request
from time import sleep
from typing import NamedTuple, Optional, Tuple
from zipfile import ZipFile

import bpy
from . import settings
from .log import ERROR, INFO, log
from .preferences import WakatimeProjectProperties

ReportArgs = Tuple[set, str]


class Status(NamedTuple):
    message: str
    level: str = INFO

    def as_report(self) -> ReportArgs:
        return {self.level or INFO}, self.message


class WakatimeDownloader(threading.Thread):
    """Downloads Wakatime client if it isn't already downloaded."""

    _lock = threading.Lock()

    def __init__(self, force=False) -> None:
        super().__init__()
        self.daemon = True
        self._force = force
        self._status_lock = threading.Lock()
        self._status: Optional[Status] = None

    def _set_status(self, message: str, level: str = INFO) -> None:
        with self._status_lock:
            self._status = Status(message, level)
        log(level, message)
        sleep(0)

    def status(self) -> Optional[ReportArgs]:
        with self._status_lock:
            return self._status.as_report() if self._status else None

    def run(self):
        with self._lock:
            if not os.path.isdir(settings.RESOURCES_DIR):
                # there is no resources directory,
                # attempting to create one
                try:
                    os.mkdir(settings.RESOURCES_DIR)
                except Exception as e:
                    self._set_status(
                        f"Unable to create directory:\n{settings.RESOURCES_DIR}\n{e}",
                        ERROR,
                    )
                    return
            # check if the client is already downloaded,
            # or the downloading is forced
            if not self._force and os.path.isfile(settings.API_CLIENT):
                self._set_status("Found Wakatime client")
                return
            if os.path.isdir(settings.API_CLIENT_DIR):
                # remove wakatime client dir if it is present
                self._set_status("Removing old runtime...")
                shutil.rmtree(settings.API_CLIENT_DIR, ignore_errors=True)
            # there is no Wakatime client present in the directory,
            # or the downloading is forced
            self._set_status("Downloading Wakatime...")
            # the path to the zipped Wakatime client
            zip_file_path = os.path.join(settings.RESOURCES_DIR, "wakatime-master.zip")
            # issue a new request to download said client
            req = urllib.request.Request(settings.API_CLIENT_URL)
            context = ssl._create_unverified_context()
            try:
                # read and save the file to said zip file
                with urllib.request.urlopen(req, context=context) as r, open(
                    zip_file_path, "wb+"
                ) as fo:
                    # as the input file is in bytes, the write mode has
                    # to be bytes as well, that's why it's `wb+`
                    fo.write(r.read())
            except urllib.error.HTTPError as e:
                self._set_status(
                    "Could not download the Wakatime client. There was an HTTP error.",
                    ERROR,
                )
                raise e
            except urllib.error.URLError as e:
                self._set_status(
                    "Could not download the Wakatime client. There was a URL error. "
                    "Maybe there is a problem with your Internet connection?",
                    ERROR,
                )
                raise e
            self._set_status("Extracting Wakatime...")
            with ZipFile(zip_file_path) as zf:
                zf.extractall(settings.API_CLIENT_DIR)
            try:
                os.remove(zip_file_path)
            except Exception:
                self._set_status(
                    "Unable to remove wakatime archive",
                    ERROR,
                )
            self._set_status("Wakatime client downloaded")


class ForceWakatimeDownload(bpy.types.Operator):
    bl_idname = "ui.download_wakatime_client"
    bl_label = "Download wakatime client"
    bl_description = f"Force (re)downloading of the wakatime client runtime from {settings.API_CLIENT_URL}"

    _last_status: Optional[ReportArgs] = None
    _downloader: Optional[WakatimeDownloader] = None

    @classmethod
    def poll(cls, _context):
        return WakatimeProjectProperties.instance() is not None

    def invoke(self, context, _event):
        self._last_status = None
        self._downloader = None
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, _context, _event):
        if self._downloader is None:
            self._downloader = WakatimeDownloader(force=True)
            self._downloader.start()
            return {"PASS_THROUGH"}
        status = self._downloader.status()
        if status and status != self._last_status:
            self._last_status = status
            self.report(*status)
        if self._downloader.is_alive():
            return {"PASS_THROUGH"}
        self._downloader = None
        return {"FINISHED"}
