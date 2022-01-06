from . import settings

DEBUG = "DEBUG"
INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"


def log(lvl, message, *args, **kwargs):
    if lvl != DEBUG or settings.debug():
        print(f"[Wakatime] [{lvl}] {message.format(*args, **kwargs)}")
