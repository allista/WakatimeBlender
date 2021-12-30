import os
from configparser import ConfigParser
from typing import Any, Callable, Optional, TypeVar

USER_HOME = os.path.expanduser("~")
PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
RESOURCES_DIR = os.path.join(USER_HOME, ".wakatime")
API_CLIENT_DIR = os.path.join(RESOURCES_DIR, "wakatime-runtime")
# using the legacy python client to avoid the need to figure out
# which binary to download for particular platform
API_CLIENT_URL = "https://github.com/wakatime/wakatime/archive/master.zip"
API_CLIENT = os.path.join(
    API_CLIENT_DIR, "legacy-python-cli-master", "wakatime", "cli.py"
)
# default wakatime config for legacy python client
FILENAME = os.path.join(USER_HOME, ".wakatime.cfg")
# default section in wakatime config
_section = "settings"

_cfg = ConfigParser()
_cfg.optionxform = str
if not _cfg.has_section(_section):
    _cfg.add_section(_section)
if not _cfg.has_option(_section, "debug"):
    _cfg.set(_section, "debug", str(False))

_loaded = False


def load():
    global _loaded
    try:
        _cfg.read(FILENAME, "utf-8")
        _loaded = True
    except Exception as e:
        print(f"[Wakatime] [ERROR] Unable to read {FILENAME}\n{repr(e)}")


def save():
    with open(FILENAME, "w") as out:
        _cfg.write(out)


def set(option: str, value: str) -> None:
    _cfg.set(_section, option, value)
    save()


def get(option: str, default: Any = None) -> str:
    if not _loaded:
        load()
    return _cfg.get(_section, option, fallback=default)


def get_bool(option: str) -> bool:
    return get(option, "").lower() in {"y", "yes", "t", "true", "1"}


_T = TypeVar("_T", bound=Any)


def parse(
    option: str, transform: Callable[[str], _T], default: Optional[_T] = None
) -> Optional[_T]:
    try:
        return transform(get(option))
    except Exception:
        return default


def debug() -> bool:
    return get_bool("debug")


def api_key() -> str:
    return get("api_key", "")


def set_api_key(new_key: str) -> None:
    set("api_key", new_key)
