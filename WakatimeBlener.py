import bpy
from bpy.api.handlers import persistent
from bpy.props import StringProperty

import json
import os
import sys
import time
import threading
from configparser import ConfigParser
from subprocess import Popen, STDOUT, PIPE
import queue

__version__ = '1.0.0'

bl_info = \
    {
        "name":     "Wakatime plugin for Blender",
        "category": "Development"
    }

# globals
PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
API_CLIENT = os.path.join(PLUGIN_DIR, 'packages', 'wakatime', 'cli.py')
SETTINGS_FILE = 'config.ini'
SETTINGS = None
ActivityHandler = None

# Log Levels
DEBUG   = 'DEBUG'
INFO    = 'INFO'
WARNING = 'WARNING'
ERROR   = 'ERROR'

# add wakatime package to path
sys.path.insert(0, os.path.join(PLUGIN_DIR, 'packages'))
try:
    from wakatime.base import parseConfigFile
except ImportError:
    pass


def u(text):
    if text is None:
        return None
    if isinstance(text, bytes):
        try:
            return text.decode('utf-8')
        except:
            try:
                return text.decode(sys.getdefaultencoding())
            except:
                pass
    try:
        return str(text)
    except:
        return text


def log(lvl, message, *args, **kwargs):
    if lvl == DEBUG and not SETTINGS.get('debug'):
        return
    msg = message
    if len(args) > 0:
        msg = message.format(*args)
    elif len(kwargs) > 0:
        msg = message.format(**kwargs)
    print('[WakaTime] [{lvl}] {msg}'.format(lvl=lvl, msg=msg))


def create_default_config():
    """Creates the .wakatime.cfg INI file in $HOME directory, if it does
    not already exist."""
    if SETTINGS.has_section('settings'): return
    SETTINGS.add_section('settings')
    SETTINGS.set('settings', 'debug', False)
    SETTINGS.set('settings', 'hidefilenames', False)


class API_Key_Dialog(bpy.types.Operator):
    bl_idname = "object.wakatime_api_key_dialog"
    bl_label = "Enter WakaTime API Key"
    api_key = StringProperty(name="API Key")
    default_key = ''

    def execute(self, context):
        if self.api_key:
            SETTINGS.set('settings', 'api_key', str(self.api_key))
            save_settings()
        return {'FINISHED'}

    def invoke(self, context, event):
        self.api_key = SETTINGS.get('settings', 'api_key', fallback='')
        return context.window_manager.invoke_props_dialog(self)


def prompt_api_key():
    create_default_config()
    try:
        configs = parseConfigFile()
        if configs is not None:
            if configs.has_option('settings', 'api_key'):
                API_Key_Dialog.default_key = configs.get('settings', 'api_key')
    except: pass
    if SETTINGS.has_option('settings', 'api_key'): return True
    bpy.ops.object.wakatime_api_key_dialog('INVOKE_DEFAULT')
    return False


def save_settings():
    with open(SETTINGS_FILE, 'w') as out:
        SETTINGS.write(out)


class Heartbeat(object):
    def __init__(self, filename, timestamp, is_write):
        self.filename  = filename
        self.timestamp = timestamp
        self.is_write  = is_write


class SendHeartbeatsThread(threading.Thread):
    """Non-blocking thread for sending heartbeats to api.
    """

    def __init__(self, heartbeat):
        threading.Thread.__init__(self)

        self.debug   = SETTINGS.get('settings', 'debug')
        self.api_key = SETTINGS.get('settings', 'api_key', fallback='')
        self.ignore  = SETTINGS.get('settings', 'ignore', fallback=[])

        self.heartbeat = heartbeat
        self.has_extra_heartbeats = False
        self.extra_heartbeats = []

    def add_extra_heartbeats(self, extra_heartbeats):
        self.has_extra_heartbeats = True
        self.extra_heartbeats = extra_heartbeats

    def run(self):
        """Running in background thread."""
        self.send_heartbeats()

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

    def send_heartbeats(self):
        ua = 'blender/%s blender-wakatime/%s' % (bpy.app.version_string, __version__)
        cmd = [
            sys.executable,
            API_CLIENT,
            '--entity', self.heartbeat.filename,
            '--time', str('%f' % self.heartbeat.timestamp),
            '--plugin', ua,
        ]
        if self.api_key:
            cmd.extend(['--key', str(bytes.decode(self.api_key.encode('utf8')))])
        if self.heartbeat.is_write:
            cmd.append('--write')
        for pattern in self.ignore:
            cmd.extend(['--ignore', pattern])
        if self.debug:
            cmd.append('--verbose')
        if self.has_extra_heartbeats:
            cmd.append('--extra-heartbeats')
            stdin = PIPE
            extra_heartbeats = [self.build_heartbeat(**x) for x in self.extra_heartbeats]
            extra_heartbeats = json.dumps(extra_heartbeats)
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
                log(INFO, 'OK')
            else:
                log(ERROR, 'Error')
            if retcode:
                log(DEBUG if retcode == 102 else ERROR, 'wakatime-core exited with status: {0}'.format(retcode))
            if output:
                log(ERROR, u('wakatime-core output: {0}').format(output))
        except:
            log(ERROR, u(sys.exc_info()[1]))


class WakaStats(object):
    HEARTBEAT_FREQUENCY = 2

    def __init__(self):
        self._heartbeats = queue()
        self._last_hb = None
        self._filename = ''
        bpy.app.handlers.load_post.append(self.load_handler)
        bpy.app.handlers.save_pre.append(self.save_handler)
        bpy.app.handlers.scene_update_post.append(self.activity_handler)

    def __del__(self):
        bpy.app.handlers.load_post.remove(self.load_handler)
        bpy.app.handlers.save_pre.remove(self.save_handler)
        bpy.app.handlers.scene_update_post.remove(self.activity_handler)

    @persistent
    def load_handler(self, dummy):
        self._filename = bpy.data.filepath
        self.handle_activity()

    @persistent
    def save_handler(self, dummy):
        self.handle_activity(is_write=True)

    @persistent
    def activity_handler(self, dummy):
        self.handle_activity()

    def enough_time_passed(self, now, is_write):
        return self._last_hb is None or now - self._last_hb.timestamp > 2 if is_write else self.HEARTBEAT_FREQUENCY * 60

    def handle_activity(self, is_write=False):
        timestamp = time.time()
        last_file = self._last_hb.filename if self._last_hb is not None else ''
        if self._filename != last_file or self.enough_time_passed(timestamp, is_write):
            self._last_hb = Heartbeat(self._filename, timestamp, is_write)
            self._heartbeats.put_nowait(self._last_hb)

    def process_queue(self):
        try:
            heartbeat = self._heartbeats.get_nowait()
        except queue.Empty:
            return

        has_extra_heartbeats = False
        extra_heartbeats = []
        try:
            while True:
                extra_heartbeats.append(self._heartbeats.get_nowait())
                has_extra_heartbeats = True
        except queue.Empty:
            pass

        thread = SendHeartbeatsThread(heartbeat)
        if has_extra_heartbeats:
            thread.add_extra_heartbeats(extra_heartbeats)
        thread.start()


def register():
    global SETTINGS, ActivityHandler
    SETTINGS = ConfigParser.read(os.path.join(PLUGIN_DIR, SETTINGS_FILE))
    log(INFO, 'Initializing WakaTime plugin v%s' % __version__)
    bpy.utils.register_module(__name__)
    bpy.utils.register_class(API_Key_Dialog)
    ActivityHandler = WakaStats()
    prompt_api_key()


def unregister():
    global ActivityHandler
    ActivityHandler = None
    save_settings()
