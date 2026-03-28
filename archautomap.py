from __future__ import annotations

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .core.constants import (
    ACTION_OBJECT_NAME,
    DOCK_WIDGET_OBJECT_NAME,
    ICON_FILENAME,
    PLUGIN_NAME,
    TOOLBAR_OBJECT_NAME,
)
from .dock_widget import ArchAutoMapDockWidget


class ArchAutoMap:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.toolbar = None
        self.dock_widget = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), ICON_FILENAME)
        self.action = QAction(
            QIcon(icon_path),
            PLUGIN_NAME,
            self.iface.mainWindow(),
        )
        self.action.setObjectName(ACTION_OBJECT_NAME)
        self.action.setIconVisibleInMenu(True)
        self.action.triggered.connect(self.show_dock)

        self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        self.toolbar.setObjectName(TOOLBAR_OBJECT_NAME)
        self.toolbar.addAction(self.action)
        self.iface.addPluginToMenu(PLUGIN_NAME, self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(PLUGIN_NAME, self.action)
            self.action.deleteLater()
            self.action = None

        if self.toolbar is not None:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None

        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

    def show_dock(self):
        if self.dock_widget is None:
            self.dock_widget = ArchAutoMapDockWidget(self.iface)
            self.dock_widget.setObjectName(DOCK_WIDGET_OBJECT_NAME)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)

        self.dock_widget.show()
        self.dock_widget.raise_()
