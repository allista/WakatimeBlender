import json
import os
import sys
import threading
import time
from configparser import ConfigParser
from functools import lru_cache
from queue import Queue, Empty
from subprocess import Popen, STDOUT, PIPE
from urllib import request
from zipfile import ZipFile

import bpy
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, StringProperty)

import ssl
import urllib

__version__ = '1.1.0'

bl_info = \
    {
        "name": "Wakatime plugin for Blender",
        "category": "Development",
        "author": "Allis Tauri <allista@gmail.com>",
        "version": (1, 1, 0),
        "blender": (2, 80, 0),
        "description": "Submits your working stats to the Wakatime time tracking service.",
        "warning": "Beta",
        "tracker_url": "https://github.com/allista/WakatimeBlender/issues",
    }

# globals
HEARTBEAT_FREQUENCY = 2
_heartbeats = Queue()
_hb_processor = None
_last_hb = None
_filename = ''

REGISTERED = False
SHOW_KEY_DIALOG = False
USER_HOME = os.path.expanduser('~')
PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
RESOURCES_DIR = os.path.join(USER_HOME, '.wakatime')
API_CLIENT_URL = 'https://github.com/wakatime/wakatime/archive/master.zip'
API_CLIENT = os.path.join(RESOURCES_DIR, 'wakatime-master', 'wakatime', 'cli.py')
SETTINGS_FILE = os.path.join(USER_HOME, '.wakatime.cfg')
SETTINGS = None
settings = 'settings'

# Log Levels
DEBUG = 'DEBUG'
INFO = 'INFO'
WARNING = 'WARNING'
ERROR = 'ERROR'


def u(text):
    if text is None:
        return None
    if isinstance(text, bytes):
        try:
            return text.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return text.decode(sys.getdefaultencoding())
            except UnicodeDecodeError:
                pass
    try:
        return str(text)
    except Exception:
        return text


def log(lvl, message, *args, **kwargs):
    if lvl != DEBUG or SETTINGS.getboolean(settings, 'debug'):
        print(f'[WakaTime] [{lvl}] {message.format(*args, **kwargs)}')


class API_Key_Dialog(bpy.types.Operator):
    bl_idname = "ui.wakatime_api_key_dialog"
    bl_label = "Enter WakaTime API Key"
    api_key = StringProperty(name="API Key")
    is_shown = False

    @classmethod
    def show(cls):
        global SHOW_KEY_DIALOG
        if not cls.is_shown and REGISTERED:
            cls.is_shown = True
            SHOW_KEY_DIALOG = False
            bpy.ops.ui.wakatime_api_key_dialog('INVOKE_DEFAULT')

    def execute(self, context):
        if self.api_key:
            SETTINGS.set(settings, 'api_key', u(self.api_key))
            save_settings()
        API_Key_Dialog.is_shown = False
        return {'FINISHED'}

    def invoke(self, context, event):
        self.api_key = SETTINGS.get(settings, 'api_key', fallback='')
        return context.window_manager.invoke_props_dialog(self)


# Addon prefs
class WakaTimePreferences(bpy.types.AddonPreferences):
    _default_always_overwrite_projectname = 0
    _default_chars = '1234567890._'
    _default_prefix = ''
    _default_postfix = ''
    _default_use_project_folder = 0
    bl_idname = __name__
    always_overwrite_name: BoolProperty(
        name = "Overwrite project-discovery with the name from below",
        default = _default_always_overwrite_projectname,
        description = f"WakaTime will guess the project-name (e.g. from the git-repo). Checking this box will overwrite this auto-discovered name (with the name according to the rules below).\n\nHint: when not working with git, the project's name will always be set according to the rules below.\n\nDefault: {bool(_default_always_overwrite_projectname)}")
    use_project_folder: BoolProperty(
        name = "Use folder-name as project-name",
        default = _default_use_project_folder,
        description = f"Will use the name of the folder/directory-name as the project-name.\n\nExample: if selected, filename 'birthday_project/test_01.blend' will result in project-name 'birthday_project'\n\nHint: if not activated, the blender-filename without the blend-extension is used.\n\nDefault: {bool(_default_use_project_folder)}")
    truncate_trail: StringProperty(
        name = "Cut trailing characters",
        default = _default_chars,
        description = f"With the project-name extracted (from folder- or filename), these trailing characters will be removed too.\n\nExample: filename 'birthday_01_test_02.blend' will result in project-name 'birthday_01_test'\n\nDefault: {_default_chars or '<empty>'}")
    project_prefix: StringProperty(
        name = "project-name prefix",
        default = _default_prefix,
        description = f"This text will be attached in front of the project-name.\n\nDefault: '{_default_prefix or '<empty>'}'")
    project_postfix: StringProperty(
        name = "project-name postfix",
        default = _default_postfix,
        description = f"This text will be attached at the end of the project-name, after the trailing characters were removed.\n\nDefault: '{_default_postfix or '<empty>'}'")

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "always_overwrite_name")
        col.prop(self, "use_project_folder")
        col.prop(self, "truncate_trail")
        col.prop(self, "project_prefix")
        col.prop(self, "project_postfix")


class HeartbeatQueueProcessor(threading.Thread):
    def __init__(self, q):
        super().__init__()
        self.daemon = True
        self._queue = q

    @classmethod
    def send(cls, heartbeat, extra_heartbeats=None):
        global SHOW_KEY_DIALOG
        ua = f'blender/{bpy.app.version_string.split()[0]} blender-wakatime/{__version__}'
        cmd = [
            bpy.app.binary_path_python,
            API_CLIENT,
            '--entity', heartbeat['entity'],
            '--time', f'{heartbeat["timestamp"]:f}',
            '--plugin', ua,
        ]
        blender_settings = bpy.context.preferences.addons[__name__].preferences
        if blender_settings.always_overwrite_name:
            cmd.extend(['--project', heartbeat['project']])
        else:
            cmd.extend(['--alternate-project', heartbeat['project']])
        if heartbeat['is_write']:
            cmd.append('--write')
        for pattern in SETTINGS.get(settings, 'ignore',
                                    fallback=[]):  # or should it be blender-specific?
            cmd.extend(['--ignore', pattern])
        if SETTINGS.getboolean(settings, 'debug'):
            cmd.append('--verbose')
        if extra_heartbeats:
            cmd.append('--extra-heartbeats')
            extra_heartbeats = json.dumps(extra_heartbeats)
            stdin = PIPE
        else:
            extra_heartbeats = None
            stdin = None
        log(DEBUG, ' '.join(cmd))
        try:
            process = Popen(cmd, stdin=stdin, stdout=PIPE, stderr=STDOUT)
            inp = None
            if extra_heartbeats:
                inp = "{0}\n".format(extra_heartbeats)
                inp = inp.encode('utf-8')
            output, err = process.communicate(input=inp)
            output = u(output)
            retcode = process.poll()
            if (not retcode or retcode == 102) and not output:
                log(DEBUG, 'OK')
            elif retcode == 104:  # wrong API key
                log(ERROR, 'Wrong API key. Asking for a new one...')
                SETTINGS.set(settings, 'api_key', '')
                SHOW_KEY_DIALOG = True
            else:
                log(ERROR, 'Error')
            if retcode:
                log(DEBUG if retcode == 102 else ERROR,
                    'wakatime-core exited with status: {}', retcode)
            if output:
                log(ERROR, 'wakatime-core output: {}', u(output))
        except Exception:
            log(ERROR, u(sys.exc_info()[1]))

    def run(self):
        while True:
            time.sleep(1)
            if not SETTINGS.get(settings, 'api_key', fallback=''): continue
            try:
                heartbeat = self._queue.get_nowait()
            except Empty:
                continue
            if heartbeat is None: return
            extra_heartbeats = []
            try:
                while True:
                    extra_heartbeats.append(self._queue.get_nowait())
            except Empty:
                pass
            self.send(heartbeat, extra_heartbeats)


class DownloadWakaTime(threading.Thread):
    '''Downloads WakaTime client if it isn't already downloaded.
    '''
    def __init__(self):
        super().__init__()
        self.daemon = True

    def run(self):
        log(INFO, 'WakatimeBlender is registered')

        if not os.path.isdir(RESOURCES_DIR):
            # there is no resources directory,
            # attempt creating one
            try:
                os.mkdir(RESOURCES_DIR)
            except Exception:
                log(ERROR, 'Unable to create directory:\n{}', RESOURCES_DIR)
                return

        if not os.path.isfile(API_CLIENT):
            # there is no WakaTime client present in the directory
            log(INFO, 'Downloading Wakatime...')
            # the path to the zipped WakaTime client
            zip_file_path = os.path.join(RESOURCES_DIR, 'wakatime-master.zip')
            # issue a new request to download said client
            req = urllib.request.Request(API_CLIENT_URL)
            context = ssl._create_unverified_context()
            try:
                # read and save the file to said zip file
                with urllib.request.urlopen(req, context=context) as r, open(zip_file_path, 'wb+') as fo:
                    # as the input file is in bytes, the write mode has
                    # to be bytes as well, that's why it's `wb+`
                    fo.write(r.read())
            except urllib.error.HTTPError as e:
                log(ERROR,
                    'Could not download the WakaTime client. There was an HTTP error.\n',
                    e.code, '\n', e.msg)
                raise e
            except urllib.error.URLError as e:
                log(ERROR,
                    'Could not download the WakaTime client. There was a URL error. '
                    + 'Maybe there is a problem with your Internet connection?\n',
                    e.reason)
                raise e

            log(INFO, 'Extracting Wakatime...')
            with ZipFile(zip_file_path) as zf:
                zf.extractall(RESOURCES_DIR)
            try:
                os.remove(zip_file_path)
            except Exception:
                pass
            log(INFO, 'Finished extracting Wakatime.')
        else:
            log(INFO, 'Found Wakatime client.')


def save_settings():
    with open(SETTINGS_FILE, 'w') as out:
        SETTINGS.write(out)


def setup():
    global SETTINGS, _hb_processor
    download = DownloadWakaTime()
    download.start()
    SETTINGS = ConfigParser()
    SETTINGS.read(SETTINGS_FILE)
    # common wakatime settings
    if not SETTINGS.has_section(settings):
        SETTINGS.add_section(settings)
    if not SETTINGS.has_option(settings, 'debug'):
        SETTINGS.set(settings, 'debug', str(False))
    _hb_processor = HeartbeatQueueProcessor(_heartbeats)
    _hb_processor.start()


@persistent
def load_handler(dummy):
    global _filename
    _filename = bpy.data.filepath
    handle_activity()


@persistent
def save_handler(dummy):
    global _filename
    _filename = bpy.data.filepath
    handle_activity(is_write=True)


@persistent
def activity_handler(dummy):
    handle_activity()


def enough_time_passed(now, is_write):
    return (_last_hb is None
            or (now - _last_hb['timestamp'] > (2 if is_write else HEARTBEAT_FREQUENCY * 60)))


@lru_cache(maxsize=128)
def guessProjectName(
    filename,
    truncate_trail,
    use_project_folder,
    project_prefix,
    project_postfix
):
    # project-folder or blend-filename?
    if use_project_folder:
        _name = os.path.basename(os.path.dirname(filename)) # grab the name of the directory
    else:
        _name = os.path.splitext(filename)[0] # cut away the (.blend) extension
        _name = os.path.basename(_name) # remove (the full) path from the filename
    _name = _name.rstrip(truncate_trail) # remove trailing characters (as configured in "Preferences")
    # tune project-name with pre- and postfix
    _name = f"{project_prefix}{_name}{project_postfix}"
    log(INFO, "project-name in WakaTime: {}", _name)
    return _name

def handle_activity(is_write=False):
    global _last_hb
    if SHOW_KEY_DIALOG or not SETTINGS.get(settings, 'api_key', fallback=''):
        API_Key_Dialog.show()
    timestamp = time.time()
    last_file = _last_hb['entity'] if _last_hb is not None else ''
    if _filename and (_filename != last_file or enough_time_passed(timestamp, is_write)):
        blender_settings = bpy.context.preferences.addons[__name__].preferences
        _projectname = guessProjectName(
            _filename,
            blender_settings.truncate_trail,
            blender_settings.use_project_folder,
            blender_settings.project_prefix,
            blender_settings.project_postfix
        )
        _last_hb = {'entity': _filename, 'project': _projectname, 'timestamp': timestamp, 'is_write': is_write}
        _heartbeats.put_nowait(_last_hb)


def register():
    global REGISTERED
    log(INFO, 'Initializing WakaTime plugin v{}', __version__)
    setup()
    bpy.utils.register_class(WakaTimePreferences)
    bpy.utils.register_class(API_Key_Dialog)
    bpy.app.handlers.load_post.append(load_handler)
    bpy.app.handlers.save_post.append(save_handler)
    bpy.app.handlers.depsgraph_update_pre.append(activity_handler)
    REGISTERED = True


def unregister():
    global REGISTERED
    log(INFO, 'Unregistering WakaTime plugin v{}',  __version__)
    save_settings()
    REGISTERED = False
    bpy.app.handlers.load_post.remove(load_handler)
    bpy.app.handlers.save_post.remove(save_handler)
    bpy.app.handlers.depsgraph_update_pre.remove(activity_handler)
    bpy.utils.unregister_class(API_Key_Dialog)
    _heartbeats.put_nowait(None)
    _heartbeats.task_done()
    _hb_processor.join()
    bpy.utils.unregister_class(WakaTimePreferences)


if __name__ == '__main__':
    register()
