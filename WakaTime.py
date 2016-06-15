import bpy
from bpy.app.handlers import persistent
from bpy.props import StringProperty

import json
import os
import sys
import time
import threading
import traceback
from urllib import request
from zipfile import ZipFile
import configparser
from subprocess import Popen, STDOUT, PIPE
from queue import Queue, Empty

__version__ = '1.0.0'

bl_info = \
    {
        "name":        "Wakatime plugin for Blender",
        "category":    "Development",
        "author":      "Allis Tauri <allista@gmail.com>",
        "version":     (1, 0),
        "blender":     (2, 77, 0),
        "description": "Submits your working stats to the Wakatime time tracking service.",
        "warning":     "Beta",
        "tracker_url": "https://github.com/allista/WakatimeBlender/issues",
    }

# globals
HEARTBEAT_FREQUENCY = 2
_heartbeats = Queue()
_hb_processor = None
_last_hb = None
_filename = ''

PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
API_CLIENT_URL = 'https://github.com/wakatime/wakatime/archive/master.zip'
API_CLIENT = os.path.join(PLUGIN_DIR, 'wakatime-master', 'wakatime', 'cli.py')
SETTINGS_FILE = os.path.join(os.path.expanduser('~'), '.wakatime.cfg')
SETTINGS = {}

# Log Levels
DEBUG   = 'DEBUG'
INFO    = 'INFO'
WARNING = 'WARNING'
ERROR   = 'ERROR'


def u(text):
    if text is None: return None
    if isinstance(text, bytes):
        try: return text.decode('utf-8')
        except:
            try: return text.decode(sys.getdefaultencoding())
            except: pass
    try: return str(text)
    except: return text


def log(lvl, message, *args, **kwargs):
    if lvl == DEBUG and not SETTINGS.getboolean('settings', 'debug'): return
    msg = message
    if len(args) > 0: msg = message.format(*args)
    elif len(kwargs) > 0: msg = message.format(**kwargs)
    print('[WakaTime] [{lvl}] {msg}'.format(lvl=lvl, msg=msg))


class API_Key_Dialog(bpy.types.Operator):
    bl_idname = "ui.wakatime_api_key_dialog"
    bl_label = "Enter WakaTime API Key"
    api_key = StringProperty(name="API Key")
    default_key = ''

    def execute(self, context):
        if self.api_key:
            SETTINGS.set('settings', 'api_key', u(self.api_key))
            save_settings()
        return {'FINISHED'}

    def invoke(self, context, event):
        self.api_key = SETTINGS.get('settings', 'api_key', fallback='')
        return context.window_manager.invoke_props_dialog(self)


class HeartbeatsSender(object):
    def __init__(self, heartbeat):
        threading.Thread.__init__(self)
        self.debug   = SETTINGS.getboolean('settings', 'debug')
        self.api_key = SETTINGS.get('settings', 'api_key', fallback='')
        self.ignore  = SETTINGS.get('settings', 'ignore', fallback=[])
        self.heartbeat = heartbeat
        self.has_extra_heartbeats = False
        self.extra_heartbeats = []

    def add_extra_heartbeats(self, extra_heartbeats):
        self.has_extra_heartbeats = len(extra_heartbeats) > 0
        self.extra_heartbeats = extra_heartbeats

    @staticmethod
    def obfuscate_apikey(command_list):
        cmd = list(command_list)
        apikey_index = None
        for num in range(len(cmd)):
            if cmd[num] == '--key':
                apikey_index = num + 1
                break
        if apikey_index is not None and apikey_index < len(cmd):
            cmd[apikey_index] = 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX' + cmd[apikey_index][-4:]
        return cmd

    def send(self):
        ua = 'blender/%s blender-wakatime/%s' % (bpy.app.version_string.split(' ')[0], __version__)
        cmd = [
            bpy.app.binary_path_python,
            API_CLIENT,
            '--entity', self.heartbeat['entity'],
            '--time', str('%f' % self.heartbeat['timestamp']),
            '--plugin', ua,
        ]
        if self.api_key:
            cmd.extend(['--key', str(bytes.decode(self.api_key.encode('utf8')))])
        if self.heartbeat['is_write']:
            cmd.append('--write')
        for pattern in self.ignore:
            cmd.extend(['--ignore', pattern])
        if self.debug:
            cmd.append('--verbose')
        if self.has_extra_heartbeats:
            cmd.append('--extra-heartbeats')
            stdin = PIPE
            extra_heartbeats = json.dumps(self.extra_heartbeats)
        else:
            extra_heartbeats = None
            stdin = None

        log(DEBUG, ' '.join(self.obfuscate_apikey(cmd)))
        try:
            process = Popen(cmd, stdin=stdin, stdout=PIPE, stderr=STDOUT)
            inp = None
            if self.has_extra_heartbeats:
                inp = "{0}\n".format(extra_heartbeats)
                inp = inp.encode('utf-8')
            output, err = process.communicate(input=inp)
            output = u(output)
            retcode = process.poll()
            if (not retcode or retcode == 102) and not output:
                log(DEBUG, 'OK')
            else:
                log(ERROR, 'Error')
            if retcode:
                log(DEBUG if retcode == 102 else ERROR, 'wakatime-core exited with status: {0}'.format(retcode))
            if output:
                log(ERROR, u('wakatime-core output: {0}').format(output))
        except:
            log(ERROR, u(sys.exc_info()[1]))


class HeartbeatQueueProcessor(threading.Thread):
    def __init__(self, q):
        threading.Thread.__init__(self)
        self.daemon = True
        self._queue = q

    def run(self):
        while True:
            time.sleep(1)
            if not SETTINGS.has_option('settings', 'api_key'): continue
            try: heartbeat = self._queue.get_nowait()
            except Empty: continue
            if heartbeat is None: return
            has_extra_heartbeats = False
            extra_heartbeats = []
            try:
                while True:
                    extra_heartbeats.append(self._queue.get_nowait())
                    has_extra_heartbeats = True
            except Empty: pass
            sender = HeartbeatsSender(heartbeat)
            if has_extra_heartbeats:
                sender.add_extra_heartbeats(extra_heartbeats)
            sender.send()


class DownloadWakatime(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        log(INFO, 'WakatimeBlender is registered')
        if not os.path.isfile(API_CLIENT):
            log(INFO, 'Downloading Wakatime...')
            zip_file = os.path.join(PLUGIN_DIR, 'wakatime-master.zip')
            request.urlretrieve(API_CLIENT_URL, zip_file)
            log(INFO, 'Extracting Wakatime...')
            with ZipFile(zip_file) as zf: zf.extractall(PLUGIN_DIR)
            try: os.remove(zip_file)
            except: pass
            log(INFO, 'Finished extracting Wakatime.')
        else: log(INFO, 'Found Wakatime client')


def save_settings():
    with open(SETTINGS_FILE, 'w') as out:
        SETTINGS.write(out)


def setup():
    global SETTINGS, _hb_processor
    download = DownloadWakatime()
    download.start()
    try:
        SETTINGS = parseConfigFile(configFile=SETTINGS_FILE)
    except: pass
    if SETTINGS is not None and SETTINGS.has_option('settings', 'api_key'):
        API_Key_Dialog.default_key = SETTINGS.get('settings', 'api_key')
        log(INFO, 'Found default API key.')
    if not SETTINGS.get('settings', 'api_key'):
        # TODO: prompt for api key
        # API_Key_Dialog()
        pass
    _hb_processor = HeartbeatQueueProcessor(_heartbeats)
    _hb_processor.start()


def parseConfigFile(configFile=None):
    """Returns a configparser.SafeConfigParser instance with configs
    read from the config file. Default location of the config file is
    at ~/.wakatime.cfg.
    """

    if not configFile:
        configFile = os.path.join(os.path.expanduser('~'), '.wakatime.cfg')

    configs = configparser.SafeConfigParser()
    try:
        with open(configFile, 'r', encoding='utf-8') as fh:
            try:
                configs.readfp(fh)
            except configparser.Error:
                print(traceback.format_exc())
                return None
    except IOError:
        print(u('Error: Could not read from config file {0}').format(u(configFile)))
    return configs


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
    return _last_hb is None or (now - _last_hb['timestamp'] > (2 if is_write else HEARTBEAT_FREQUENCY * 60))


def handle_activity(is_write=False):
    global _last_hb
    timestamp = time.time()
    last_file = _last_hb['entity'] if _last_hb is not None else ''
    if _filename and (_filename != last_file or enough_time_passed(timestamp, is_write)):
        _last_hb = {'entity':_filename, 'timestamp':timestamp, 'is_write':is_write}
        _heartbeats.put_nowait(_last_hb)


def register():
    log(INFO, 'Initializing WakaTime plugin v%s' % __version__)
    bpy.utils.register_module(__name__)
    bpy.app.handlers.load_post.append(load_handler)
    bpy.app.handlers.save_post.append(save_handler)
    bpy.app.handlers.scene_update_post.append(activity_handler)
    setup()


def unregister():
    save_settings()
    log(INFO, 'Unregistering WakaTime plugin v%s' % __version__)
    _heartbeats.put_nowait(None)
    _heartbeats.task_done()
    _hb_processor.join()
    bpy.app.handlers.load_post.remove(load_handler)
    bpy.app.handlers.save_post.remove(save_handler)
    bpy.app.handlers.scene_update_post.remove(activity_handler)
    bpy.utils.unregister_module(__name__)


if __name__ == '__main__':
    register()
