from __future__ import annotations

from qgis.PyQt.QtCore import QSettings


class PluginSettings:
    PREFIX = "ArchAutoMap/"

    def __init__(self):
        self._settings = QSettings()

    def get(self, key: str, default=None):
        return self._settings.value(f"{self.PREFIX}{key}", default)

    def set(self, key: str, value):
        self._settings.setValue(f"{self.PREFIX}{key}", value)
