import bpy
from bpy.app.handlers import persistent

from .wakatime_blender import settings
from .wakatime_blender.heartbeat_queue import HeartbeatQueue
from .wakatime_blender.log import ERROR, INFO, log
from .wakatime_blender.preferences import (
    PreferencesDialog,
    WakatimeProjectProperties,
)
from .wakatime_blender.wakatime_downloader import (
    # ForceWakatimeDownload
    WakatimeDownloader,
)


bl_info = {
    "name": "WakaTime",
    "category": "Development",
    "author": "Allis Tauri <allista@gmail.com>",
    "version": (2, 0, 1),
    "blender": (3, 3, 0),
    "description": "Submits your working stats to the Wakatime time tracking service.",
    "tracker_url": "https://github.com/allista/WakatimeBlender/issues",
}

__version__ = ".".join((f"{n}" for n in bl_info["version"]))

heartbeat_queue: HeartbeatQueue

REGISTERED = False


def handle_activity(is_write=False):
    if not REGISTERED:
        return
    heartbeat_queue.enqueue(bpy.data.filepath, is_write)
    if not settings.api_key():
        PreferencesDialog.show()


@persistent
def load_handler(_):
    handle_activity()


@persistent
def save_handler(_):
    handle_activity(is_write=True)


@persistent
def activity_handler(_):
    handle_activity()


def menu(self, _context):
    self.layout.operator(PreferencesDialog.bl_idname)
    # self.layout.operator(ForceWakatimeDownload.bl_idname)


def register():
    global REGISTERED, heartbeat_queue
    if REGISTERED:
        return
    try:
        log(INFO, "Initializing Wakatime plugin v{}", __version__)
        WakatimeProjectProperties.load_defaults()
        # bpy.utils.register_class(ForceWakatimeDownload)
        bpy.utils.register_class(WakatimeProjectProperties)
        bpy.utils.register_class(PreferencesDialog)
        bpy.types.TOPBAR_MT_blender_system.append(menu)
        bpy.app.handlers.load_post.append(load_handler)
        bpy.app.handlers.save_post.append(save_handler)
        bpy.app.handlers.depsgraph_update_pre.append(activity_handler)
        try:
            downloader = WakatimeDownloader()
            heartbeat_queue = HeartbeatQueue(__version__)
            downloader.start()
            heartbeat_queue.start()
        except Exception as e:
            log(ERROR, "Unable to start worker threads: {}", e)
    finally:
        REGISTERED = True


def unregister():
    global REGISTERED
    if not REGISTERED:
        return
    try:
        log(INFO, "Unregistering Wakatime plugin v{}", __version__)
        bpy.types.TOPBAR_MT_blender_system.remove(menu)
        bpy.app.handlers.load_post.remove(load_handler)
        bpy.app.handlers.save_post.remove(save_handler)
        bpy.app.handlers.depsgraph_update_pre.remove(activity_handler)
        # bpy.utils.unregister_class(ForceWakatimeDownload)
        bpy.utils.unregister_class(PreferencesDialog)
        heartbeat_queue.shutdown()
        heartbeat_queue.join(heartbeat_queue.POLL_INTERVAL * 3)
        # unregister preferences only after the heartbeat queue has stopped
        bpy.utils.unregister_class(WakatimeProjectProperties)
    finally:
        REGISTERED = False
