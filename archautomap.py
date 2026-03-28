from __future__ import annotations

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .dock_widget import ArchAutoMapDockWidget


class ArchAutoMap:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock_widget = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.action = QAction(QIcon(icon_path), "ArchAutoMap", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dock)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("ArchAutoMap", self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("ArchAutoMap", self.action)
            self.action.deleteLater()
            self.action = None

        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

    def show_dock(self):
        if self.dock_widget is None:
            self.dock_widget = ArchAutoMapDockWidget(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)

        self.dock_widget.show()
        self.dock_widget.raise_()
