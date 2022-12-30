import os
import sys
import shutil
import ssl
import threading
import urllib
import urllib.error
import urllib.request
import traceback
import platform
import subprocess
import configparser
import json
import re

from time import sleep
from typing import NamedTuple, Optional, Tuple
from zipfile import ZipFile
from subprocess import STDOUT, PIPE, Popen

import bpy
from . import settings
from .log import DEBUG, ERROR, INFO, log
from .preferences import WakatimeProjectProperties

"""
Uses lots of code from the Sublime Text addon to add support for the Go wakatime-cli.
Rest of the code is mostly original from allista/WakatimeBlender
"""

GITHUB_RELEASES_STABLE_URL = (
    "https://api.github.com/repos/wakatime/wakatime-cli/releases/latest"
)
GITHUB_DOWNLOAD_PREFIX = "https://github.com/wakatime/wakatime-cli/releases/download"
INTERNAL_CONFIG_FILE = os.path.join(settings.USER_HOME, ".wakatime-internal.cfg")

LATEST_CLI_VERSION = None
WAKATIME_CLI_LOCATION = None

ReportArgs = Tuple[set, str]

is_win = platform.system() == "Windows"


class Status(NamedTuple):
    message: str
    level: str = INFO

    def as_report(self) -> ReportArgs:
        return {self.level or INFO}, self.message


class Popen(subprocess.Popen):
    """Patched Popen to prevent opening cmd window on Windows platform."""

    def __init__(self, *args, **kwargs):
        startupinfo = kwargs.get("startupinfo")
        if is_win or True:
            try:
                startupinfo = startupinfo or subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            except AttributeError:
                pass
        kwargs["startupinfo"] = startupinfo
        super(Popen, self).__init__(*args, **kwargs)


class WakatimeDownloader(threading.Thread):
    """Non-blocking thread for downloading latest wakatime-cli from GitHub."""

    def __init__(self, force=False):
        super().__init__()
        self._force = force

    def run(self):
        log(INFO, "Downloading wakatime-cli...")

        if not os.path.exists(settings.RESOURCES_DIR):
            os.makedirs(settings.RESOURCES_DIR)

        if isCliInstalled():
            if self._force:
                try:
                    os.remove(getCliLocation())
                except:
                    log(DEBUG, traceback.format_exc())
            else:
                log(INFO, "wakatime-cli already installed")
                return

        try:
            url = cliDownloadUrl()
            log(DEBUG, "Downloading wakatime-cli from {url}".format(url=url))
            zip_file = os.path.join(settings.RESOURCES_DIR, "wakatime-cli.zip")
            download(url, zip_file)

            log(INFO, "Extracting wakatime-cli...")
            with ZipFile(zip_file) as zf:
                zf.extractall(settings.RESOURCES_DIR)

            if not is_win:
                os.chmod(getCliLocation(), 509)  # 755

            try:
                os.remove(os.path.join(settings.RESOURCES_DIR, "wakatime-cli.zip"))
            except:
                log(DEBUG, traceback.format_exc())
        except:
            log(DEBUG, traceback.format_exc())

        log(INFO, "Finished extracting wakatime-cli.")


def parseConfigFile(configFile):
    """Returns a configparser.SafeConfigParser instance with configs
    read from the config file. Default location of the config file is
    at ~/.wakatime.cfg.
    """

    configs = configparser.SafeConfigParser()
    try:
        with open(configFile, "r", encoding="utf-8") as fh:
            try:
                configs.readfp(fh)
                return configs
            except configparser.Error:
                log(ERROR, traceback.format_exc())
                return None
    except IOError:
        log(DEBUG, "Error: Could not read from config file {0}\n".format(configFile))
        return configs


def getCliLocation():
    global WAKATIME_CLI_LOCATION

    if not WAKATIME_CLI_LOCATION:
        binary = "wakatime-cli-{osname}-{arch}{ext}".format(
            osname=platform.system().lower(),
            arch=architecture(),
            ext=".exe" if is_win else "",
        )
        WAKATIME_CLI_LOCATION = os.path.join(settings.RESOURCES_DIR, binary)

    return WAKATIME_CLI_LOCATION


def architecture():
    arch = platform.machine() or platform.processor()
    if arch == "armv7l":
        return "arm"
    if arch == "aarch64":
        return "arm64"
    if "arm" in arch:
        return "arm64" if sys.maxsize > 2**32 else "arm"
    return "amd64" if sys.maxsize > 2**32 else "386"


def isCliInstalled():
    return os.path.exists(getCliLocation())


def isCliLatest():
    if not isCliInstalled():
        return False

    args = [getCliLocation(), "--version"]
    try:
        stdout, stderr = Popen(args, stdout=PIPE, stderr=PIPE).communicate()
    except:
        return False
    stdout = (stdout or b"") + (stderr or b"")
    localVer = extractVersion(stdout.decode("utf-8"))
    if not localVer:
        log(DEBUG, "Local wakatime-cli version not found.")
        return False

    log(INFO, "Current wakatime-cli version is %s" % localVer)
    log(INFO, "Checking for updates to wakatime-cli...")

    remoteVer = getLatestCliVersion()

    if not remoteVer:
        return True

    if remoteVer == localVer:
        log(INFO, "wakatime-cli is up to date.")
        return True

    log(INFO, "Found an updated wakatime-cli %s" % remoteVer)
    return False


def getLatestCliVersion():
    global LATEST_CLI_VERSION

    if LATEST_CLI_VERSION:
        return LATEST_CLI_VERSION

    configs, last_modified, last_version = None, None, None
    try:
        configs = parseConfigFile(INTERNAL_CONFIG_FILE)
        if configs:
            if configs.has_option("internal", "cli_version"):
                last_version = configs.get("internal", "cli_version")
            if last_version and configs.has_option(
                "internal", "cli_version_last_modified"
            ):
                last_modified = configs.get("internal", "cli_version_last_modified")
    except:
        log(DEBUG, traceback.format_exc())

    try:
        headers, contents, code = request(
            GITHUB_RELEASES_STABLE_URL, last_modified=last_modified
        )

        log(DEBUG, "GitHub API Response {0}".format(code))

        if code == 304:
            LATEST_CLI_VERSION = last_version
            return last_version

        data = json.loads(contents.decode("utf-8"))

        ver = data["tag_name"]
        log(DEBUG, "Latest wakatime-cli version from GitHub: {0}".format(ver))

        if configs:
            last_modified = headers.get("Last-Modified")
            if not configs.has_section("internal"):
                configs.add_section("internal")
            configs.set("internal", "cli_version", ver)
            configs.set("internal", "cli_version_last_modified", last_modified)
            with open(INTERNAL_CONFIG_FILE, "w", encoding="utf-8") as fh:
                configs.write(fh)

        LATEST_CLI_VERSION = ver
        return ver
    except:
        log(DEBUG, traceback.format_exc())
        return None


def extractVersion(text):
    pattern = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)")
    match = pattern.search(text)
    if match:
        return "v{ver}".format(ver=match.group(1))
    return None


def cliDownloadUrl():
    osname = platform.system().lower()
    arch = architecture()

    validCombinations = [
        "darwin-amd64",
        "darwin-arm64",
        "freebsd-386",
        "freebsd-amd64",
        "freebsd-arm",
        "linux-386",
        "linux-amd64",
        "linux-arm",
        "linux-arm64",
        "netbsd-386",
        "netbsd-amd64",
        "netbsd-arm",
        "openbsd-386",
        "openbsd-amd64",
        "openbsd-arm",
        "openbsd-arm64",
        "windows-386",
        "windows-amd64",
        "windows-arm64",
    ]
    check = "{osname}-{arch}".format(osname=osname, arch=arch)
    if check not in validCombinations:
        reportMissingPlatformSupport(osname, arch)

    version = getLatestCliVersion()

    return "{prefix}/{version}/wakatime-cli-{osname}-{arch}.zip".format(
        prefix=GITHUB_DOWNLOAD_PREFIX,
        version=version,
        osname=osname,
        arch=arch,
    )


def reportMissingPlatformSupport(osname, arch):
    url = "https://api.wakatime.com/api/v1/cli-missing?osname={osname}&architecture={arch}&plugin=sublime".format(
        osname=osname,
        arch=arch,
    )
    request(url)


def request(url, last_modified=None):
    proxy = False  # TODO: Support for Proxy (?)
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(
                {
                    "http": proxy,
                    "https": proxy,
                }
            )
        )
    else:
        opener = urllib.request.build_opener()

    headers = [("User-Agent", "github.com/wakatime/sublime-wakatime")]
    if last_modified:
        headers.append(("If-Modified-Since", last_modified))

    opener.addheaders = headers

    urllib.request.install_opener(opener)

    try:
        resp = urllib.request.urlopen(url)
        headers = resp.headers
        return headers, resp.read(), resp.getcode()
    except urllib.error.HTTPError as err:
        if err.code == 304:
            return None, None, 304
        log(DEBUG, err.read().decode())
        raise
    except IOError:
        raise


def download(url, filePath):
    proxy = False  # TODO: Support for Proxy (?)
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(
                {
                    "http": proxy,
                    "https": proxy,
                }
            )
        )
    else:
        opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "github.com/wakatime/sublime-wakatime")]

    urllib.request.install_opener(opener)

    try:
        urllib.request.urlretrieve(url, filePath)
    except IOError:
        raise


# Removed force downloader. Addon still checks on each startup.
