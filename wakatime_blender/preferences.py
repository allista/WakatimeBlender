from typing import Optional

import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_types import PropertyGroup
from . import settings
from .log import ERROR, log
from .utils import u


class WakatimeProjectProperties(PropertyGroup):
    _attr = "wakatime_preferences"
    bl_idname = "preferences.wakatime_preferences"
    bl_label = "Wakatime Operator"

    _default_heartbeat_frequency = 2
    _default_always_overwrite_projectname = False
    _default_use_project_folder = False
    _default_chars = "1234567890._"
    _default_prefix = ""
    _default_postfix = ""

    always_overwrite_name: BoolProperty(
        name="Overwrite project-discovery with the name from below",
        default=_default_always_overwrite_projectname,
        description="Wakatime will guess the project-name (e.g. from the git-repo). Checking this box will overwrite "
        "this auto-discovered name (with the name according to the rules below).\n\nHint: when not "
        "working with git, the project's name will always be set according to the rules "
        f"below.",
    )

    use_project_folder: BoolProperty(
        name="Use folder-name as project-name",
        default=_default_use_project_folder,
        description="Will use the name of the folder/directory-name as the project-name.\n\nExample: if selected, "
        "filename 'birthday_project/test_01.blend' will result in project-name "
        "'birthday_project'\n\nHint: if not activated, the blender-filename without the blend-extension "
        f"is used.",
    )

    truncate_trail: StringProperty(
        name="Cut trailing characters",
        default=_default_chars,
        description="With the project-name extracted (from folder- or filename), these trailing characters will be "
        "removed too.\n\nExample: filename 'birthday_01_test_02.blend' will result in project-name "
        "'birthday_01_test'",
    )

    project_prefix: StringProperty(
        name="Project-name prefix",
        default=_default_prefix,
        description="This text will be attached in front of the project-name.",
    )
    project_postfix: StringProperty(
        name="Project-name postfix",
        default=_default_postfix,
        description="This text will be attached at the end of the project-name, after the trailing characters were "
        "removed.",
    )

    heartbeat_frequency: FloatProperty(
        name="Heartbeat Frequency (minutes)",
        default=_default_heartbeat_frequency,
        min=1,
        max=60,
        description="How often the plugin should send heartbeats to Wakatime server",
    )

    @classmethod
    def register(cls):
        setattr(bpy.types.World, cls._attr, bpy.props.PointerProperty(type=cls))

    @classmethod
    def load_defaults(cls):
        annotation = cls.__annotations__["always_overwrite_name"]
        if isinstance(annotation, tuple):
            keywords = annotation[1]
        else:
            keywords = annotation.keywords
        keywords["default"] = settings.get_bool("always_overwrite_project_name")

    @classmethod
    def reload_defaults(cls):
        try:
            bpy.utils.unregister_class(WakatimeProjectProperties)
        except ValueError:
            pass
        cls.load_defaults()
        bpy.utils.register_class(WakatimeProjectProperties)

    @classmethod
    def instance(cls) -> Optional["WakatimeProjectProperties"]:
        try:
            worlds = bpy.context.blend_data.worlds
            first_world = worlds[0]
            return getattr(first_world, cls._attr)
        except (IndexError, AttributeError, TypeError):
            log(ERROR, "Unable to get WakatimeProjectProperties from the First World")
        return None


class PreferencesDialog(bpy.types.Operator):
    bl_idname = "ui.wakatime_blender_preferences"
    bl_label = "Wakatime Preferences"
    bl_description = "Configure wakatime plugin for blender"

    api_key: StringProperty(
        name="API Key",
        default="",
        description="Wakatime API key from your account",
    )

    always_overwrite_name_default: BoolProperty(
        name="Overwrite project-discovery by default",
        default=False,
        description="Wakatime will guess the project-name (e.g. from the git-repo). "
        "Checking this box will overwrite this auto-discovered name "
        "for new blend files by default.",
    )

    is_shown = False

    @classmethod
    def show(cls):
        if not cls.is_shown:
            cls.is_shown = True
            bpy.ops.ui.wakatime_blender_preferences("INVOKE_DEFAULT")

    @classmethod
    def _hide(cls):
        cls.is_shown = False

    def execute(self, _context):
        settings.set_api_key(u(self.api_key))
        settings.set(
            "always_overwrite_project_name", f"{self.always_overwrite_name_default}"
        )
        WakatimeProjectProperties.reload_defaults()
        self._hide()
        return {"FINISHED"}

    def invoke(self, context, _event):
        self.api_key = settings.api_key()
        self.always_overwrite_name_default = settings.get_bool(
            "always_overwrite_project_name"
        )
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, _context):
        props = WakatimeProjectProperties.instance()
        if props is None:
            return
        layout = self.layout
        col = layout.column()
        col.prop(self, "api_key")
        col.prop(self, "always_overwrite_name_default")
        col.prop(props, "always_overwrite_name")
        col.prop(props, "truncate_trail")
        col.prop(props, "project_prefix")
        col.prop(props, "project_postfix")
        col.prop(props, "use_project_folder")
        col.prop(props, "heartbeat_frequency")
