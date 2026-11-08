"""Adwaita application: lifecycle, global actions and file opening."""

from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from . import APP_ID, APP_NAME, __version__  # noqa: E402
from .i18n import _  # noqa: E402
from .ui.window import MainWindow  # noqa: E402


class GLeaksApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.window: MainWindow | None = None
        for name, callback, accel in (
            ("new-profile", lambda *_a: self._main().create_profile(), "<primary>n"),
            ("open-profile", lambda *_a: self._main().choose_profile(), "<primary>o"),
            ("close-profile", lambda *_a: self._main().close_profile(), "<primary>w"),
            ("scan", lambda *_a: self._main().start_scan(), "<primary>r"),
            ("preferences", lambda *_a: self._main().show_preferences(), "<primary>comma"),
            ("about", self._on_about, None),
            ("quit", lambda *_a: self._main().quit_now(), "<primary>q"),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accel:
                self.set_accels_for_action(f"app.{name}", [accel])

    def _main(self) -> MainWindow:
        if self.window is None:
            self.window = MainWindow(application=self)
            self.window.connect("destroy", self._on_window_destroyed)
        return self.window

    def _on_window_destroyed(self, _window):
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_path(str(Path(__file__).parent / "ui" / "style.css"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        self._main().present()

    def do_open(self, files, _n_files, _hint):
        window = self._main()
        window.present()
        if files and files[0].get_path():
            window.request_open(files[0].get_path())

    def _on_about(self, *_args):
        Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=APP_ID,
            developer_name=_("GLeaks contributors"),
            version=__version__,
            website="https://github.com/openapi/gleaks",
            issue_url="https://github.com/openapi/gleaks/issues",
            license_type=Gtk.License.MIT_X11,
            comments=_("Know where your data has leaked.\n\n"
                       "GLeaks is independent and is not affiliated with GNOME, Ubuntu "
                       "or Have I Been Pwned."),
        ).present(self._main())


def main() -> int:
    return GLeaksApp().run(sys.argv)
