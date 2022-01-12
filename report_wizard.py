# -*- coding: utf-8 -*-
"""
/***************************************************************************
 reportWizard
                                 A QGIS plugin
 Quick  markdown and html reports generation 
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-03-21
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Enrico Ferreguti
        email                : enricofer@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from typing import OrderedDict
from qgis.PyQt.QtCore import QSize, QSettings, QTranslator, QCoreApplication, QUrl, QFileInfo, Qt, QByteArray, QBuffer, QIODevice
from qgis.PyQt.QtGui import QIcon, QImage, QPainter, QRegion, QBitmap, QPixmap, QDesktopServices
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QToolButton, QMenu, QLabel, QSizePolicy

from PyQt5.Qsci import QsciScintilla, QsciLexerHTML, QsciLexerMarkdown

from qgis.gui import QgsMapCanvas
from qgis.core import (
    Qgis,
    QgsMapRendererJob,
    QgsWkbTypes,
    QgsMapLayerType,
    QgsPointXY,
    QgsApplication,
    QgsMapRendererParallelJob,
    QgsExpressionContextUtils,
    QgsProject,
    QgsMapLayer,
    QgsVectorLayer,
    QgsRectangle,
    QgsGeometry,
    QgsLayoutExporter,
    QgsUnitTypes
)

import tempfile
import os

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
import os.path

from functools import partial

from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader
from jinja2 import evalcontextfilter, Markup, escape, meta

from processing import execAlgorithmDialog, createAlgorithmDialog
from .report_wizard_provider import ReportWizardProvider

class reportWizard:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'reportWizard_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Report wizard')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        self.toolButton = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('reportWizard', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        toolbutton=None,
        status_tip=None,
        whats_this=None,
        parent=None,
        args=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        if args:
            callback = partial(callback, action, *args)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if toolbutton:
            self.defaultAction = QAction( QIcon(self.main_icon), "Report wizard", parent)
            self.toolButton.setDefaultAction(self.defaultAction)
            self.toolButtonMenu.addAction(action)
                
        else:
            if add_to_toolbar:
                # Adds plugin icon to Plugins toolbar
                self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action
    

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = ReportWizardProvider(self.iface)
        QgsApplication.processingRegistry().addProvider(self.provider)


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.initProcessing()

        self.main_icon = os.path.join(self.plugin_dir, 'support', 'icon.png')
        self.toolButton = QToolButton()
        self.toolButtonMenu = QMenu()
        self.toolButton.setMenu(self.toolButtonMenu)
        self.toolButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.toolBtnAction = self.iface.addToolBarWidget(self.toolButton)

        alg_params = {} 

        sub_actions = [
            {
                "text":"Readme",
                "icon_path":os.path.join(self.plugin_dir, 'support', 'icon.png'),
                "callback": lambda x: QDesktopServices.openUrl(QUrl("https://github.com/enricofer/qgis_report_wizard/blob/master/README.md")),
                "parent": self.iface.mainWindow(),
                "toolbutton": self.toolButton,
            },
            {
                "text":"Sample templates",
                "icon_path":os.path.join(self.plugin_dir, 'support', 'icon.png'),
                "callback": self.open_templates_folder,
                "parent": self.iface.mainWindow(),
                "toolbutton": self.toolButton,
            },
            {
                "text":"Odt report generator",
                "icon_path":os.path.join(self.plugin_dir, 'support', 'icon_odt.png'),
                "args": ["report_wizard:odt_report", alg_params],
                "callback": self.run_alg,
                "parent": self.iface.mainWindow(),
                "toolbutton": self.toolButton,
            },
            {
                "text":"Hypertext report generator",
                "icon_path":os.path.join(self.plugin_dir, 'support', 'icon_md.png'),
                "args": ["report_wizard:hypertext_report", alg_params],
                "callback": self.run_alg,
                "parent": self.iface.mainWindow(),
                "toolbutton": self.toolButton,
            },
        ]

        for action in sub_actions:
            self.add_action(**action)

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        if self.toolButton:
            self.iface.removeToolBarIcon(self.toolBtnAction)
        else:
            for action in self.actions:
                self.iface.removePluginMenu(
                    self.menu,
                    action)
                self.iface.removeToolBarIcon(action)
        try:
            QgsApplication.processingRegistry().removeProvider(self.provider)
        except:
            pass

    
    def open_templates_folder(self):
        templates_folder = os.path.join(self.plugin_dir,"test","templates")
        templates_folder_url = QUrl.fromLocalFile(templates_folder)
        QDesktopServices.openUrl(templates_folder_url)

    def run_alg(self, triggeredAction, alg, alg_params):  
        self.toolButton.setDefaultAction(triggeredAction)      
        dialog = createAlgorithmDialog(alg, alg_params)
        dialog.show()
        dialog.exec_()
        results = dialog.results()
        link = QLabel()
        print (results)
        if "OUTPUT" in results.keys():
            link.setText('<strong>Report wizard: </strong><a href="{OUTPUT}">{OUTPUT}</a>'.format(**results))
            link.linkActivated.connect(lambda path: QDesktopServices.openUrl(QUrl.fromLocalFile(path)))        
            link.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.Maximum)
            item = self.iface.messageBar().pushWidget(link, Qgis.Success, 50)
            item.widget().setAlignment(Qt.AlignLeft)
            dialog.close()
        print("results", results)
