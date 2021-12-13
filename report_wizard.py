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
from qgis.PyQt.QtCore import QSize, QSettings, QTranslator, QCoreApplication, QFileInfo, Qt, QByteArray, QBuffer, QIODevice
from qgis.PyQt.QtGui import QIcon, QImage, QPainter, QRegion, QBitmap, QPixmap
from qgis.PyQt.QtWidgets import QAction, QFileDialog

from PyQt5.Qsci import QsciScintilla, QsciLexerHTML, QsciLexerMarkdown

from qgis.gui import QgsMapCanvas
from qgis.core import (
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

from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader
from jinja2 import evalcontextfilter, Markup, escape, meta

from secretary import Renderer

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
        self.exporter = canvas_image_exporter(iface.mapCanvas())
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
        status_tip=None,
        whats_this=None,
        parent=None):
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
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/report_wizard/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u''),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Report wizard'),
                action)
            self.iface.removeToolBarIcon(action)

    def isVector(self,layer):
        return layer["obj"].type() == QgsMapLayerType.VectorLayer

    def isRaster(self,layer):
        return layer["obj"].type() == QgsMapLayerType.RasterLayer

    def run(self):
        """Run method that performs all the real work"""

        mdNameInfo = QFileInfo(QFileDialog.getOpenFileName(
            None,
            "Open a template",
            None,
            "templates(*.md *.odt)")[0]
        )
        dd = mdNameInfo.absoluteDir().absolutePath()
        print (dd)

        if mdNameInfo:
            
            #project_vars = {k: QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable(k) for k in QgsExpressionContextUtils.projectScope(QgsProject.instance()).variableNames()}
            globals = {
                "image": "canvas:"+self.iface.mapCanvas().theme(),
                "project": QgsProject.instance(),
                "mapCanvas": self.iface.mapCanvas(),
                "extent": self.iface.mapCanvas().extent(),
                "box": [
                    self.iface.mapCanvas().extent().xMinimum(),
                    self.iface.mapCanvas().extent().yMinimum(),
                    self.iface.mapCanvas().extent().xMaximum(),
                    self.iface.mapCanvas().extent().yMaximum()
                ],
                "vars":{}
            }

            for k in list(QgsExpressionContextUtils.projectScope(QgsProject.instance()).variableNames())+list(QgsExpressionContextUtils.globalScope().variableNames()):
                if k in ('layers','user_account_name'):
                    continue
                var_value = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable(k)
                globals["vars"][str(k)] =  var_value if isinstance(var_value, str) else str(var_value).replace("\\","/")
            print(globals["vars"])
            globals["themes"] = list(QgsProject.instance().mapThemeCollection().mapThemes())

            globals["bookmarks"] = []
            for bookmark in list(QgsProject.instance().bookmarkManager().bookmarks())+list(QgsApplication.instance().bookmarkManager().bookmarks()):
                bk_def = {
                    "name": bookmark.name(),
                    "id": bookmark.id(),
                    "extent": bookmark.extent(),
                    "box": [
                        bookmark.extent().xMinimum(),
                        bookmark.extent().yMinimum(),
                        bookmark.extent().xMaximum(),
                        bookmark.extent().yMaximum()
                    ]
                }
                globals["bookmarks"].append(bk_def)
            
            layers = []
            for layername,layer in QgsProject.instance().mapLayers().items():

                if  layer.type() == QgsMapLayerType.VectorLayer:
                    type = "vector"
                elif layer.type() == QgsMapLayerType.RasterLayer:
                    type = "raster"
                elif layer.type() == QgsMapLayerType.PluginLayer:
                    type = "plugin"
                elif layer.type() == QgsMapLayerType.MeshLayer:
                    type = "mesh"
                else:
                    type = "unknown"

                fields = []
                geometryType = ""
                if type == 'vector':
                    if  layer.geometryType() ==  QgsWkbTypes.PointGeometry:
                        geometryType = "point"
                    elif layer.geometryType() == QgsWkbTypes.LineGeometry:
                        geometryType = "linestring"
                    elif layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                        geometryType = "polygon"
                    elif layer.geometryType() == QgsWkbTypes.UnknownGeometry:
                        geometryType = "unknown"
                    elif layer.geometryType() == QgsWkbTypes.NullGeometry:
                        geometryType = "nullgeometry"
                    for field in layer.fields().toList():
                        fields.append(field.name())

                layers.append ({
                    "obj":layer,
                    "type": 'layer',
                    "layerType": type,
                    "geometryType": geometryType,
                    "name": layer.name(),
                    "image": "layer:%s" % layer.id(),
                    "id": layername,
                    "source": layer.publicSource(),
                    "extent": layer.extent(),
                    "box": [
                        layer.extent().xMinimum(),
                        layer.extent().yMinimum(),
                        layer.extent().xMaximum(),
                        layer.extent().yMaximum()
                    ],
                    "fields": fields
                })
                
            layouts = []
            for layout in QgsProject.instance().layoutManager().printLayouts():
                layout_def = {
                    "obj": layout,
                    "type": 'layout',
                    "name": layout.name(),
                    "image": "layout:%s" % layout.name(),
                    "atlas": layout.atlas().coverageLayer().id()  if layout.atlas().enabled() else None
                }
                layouts.append (layout_def)

            feat_dicts = []
            print ("ACTIVE LAYER", self.iface.activeLayer())
            if self.iface.activeLayer() and self.iface.activeLayer().type() == QgsMapLayerType.VectorLayer :
                layer = self.iface.activeLayer()
                feats = layer.selectedFeatures()
                if not feats:
                    feats = layer.getFeatures()
                for feat in feats: #Iterator?
                    f_dict = {
                        "id": feat.id(),
                        "type": 'feature',
                        "obj": feat,
                        "geom": feat.geometry(),
                        "image": "feature:%s" % (layer.id())
                    }
                    attributes = {}
                    for field in layer.fields().toList():
                        attributes[field.name()] = feat[field.name()]
                    f_dict["attributes"] = attributes
                    feat_dicts.append(f_dict)
            else:
                feat_dicts = []

            if mdNameInfo.suffix() == 'md':
                env = Environment(
                    loader=FileSystemLoader('/'),
                    autoescape=select_autoescape(['html', 'xml']),
                )
                self.exporter = canvas_image_exporter(self.iface.mapCanvas())
                env.filters["image"] = self.canvas_image
                template = env.get_template(mdNameInfo.absoluteFilePath())
                result = template.render(layers=layers, project=project_vars, globals=global_vars, layer = feat_dicts )
                output = open(os.path.join(dd, 'rendered_document.md'), 'w')
                output.write(result)
                
            elif mdNameInfo.suffix() == 'odt':
                engine = Renderer()
                engine.environment.filters['isVector'] = self.isVector
                engine.environment.filters['isRaster'] = self.isRaster
                
                @engine.media_loader
                def qgis_images_loader(value,dpi=200,box=None,center=None,atlas=None,theme=None,scale_denominator=None,around_border=0.1,mimetype="image/png",filter=None,**kwargs):

                    print ("KWARGS",kwargs)
                    if center and not scale_denominator:
                        raise ("Can't specify center without scale_denominator parameter")   

                    def getFrame(reference_frame):
                        centerxy = center
                        bb = box
                        print ("getFrame", bb, centerxy, scale_denominator, theme )
                        if scale_denominator:
                            if not centerxy:
                                if bb:
                                    centerxy = bb.center()
                                else:
                                    centerxy = reference_frame.center()
                            else:
                                if isinstance(centerxy,str):
                                    coords = centerxy.split(",")
                                    centerxy = QgsPointXY(coords[0],coords[1])
                                elif not isinstance(centerxy,QgsPointXY):
                                    raise ("Malformed center parameter")
                            
                            semiScaledXSize = meterxsize*scale_denominator/2
                            semiScaledYSize = meterysize*scale_denominator/2
                            return QgsRectangle(centerxy.x()-semiScaledXSize, centerxy.y()-semiScaledYSize, centerxy.x()+semiScaledXSize, centerxy.y()+semiScaledYSize)
                        else:
                            if not bb:
                                bb = reference_frame

                            if around_border:
                                if xsize >= ysize:
                                    dim = bb.xMaximum() - bb.xMinimum()
                                else:
                                    dim = bb.yMaximum() - bb.yMinimum()
                                dim = dim*around_border
                                bb.grow(dim)
                            return bb



                    if atlas:
                        image_metadata = ["atlas",atlas]
                    else:
                        image_metadata = value["image"].split(":")
                    print ("image metadata",image_metadata, kwargs.keys())
                    if not 'svg:width' in kwargs['frame_attrs']:
                        print ("NO svg:width!")
                        return

                    units = kwargs['frame_attrs']['svg:width'][-2:]
                    if units == "cm":
                        m_conversion_factor = 0.01
                        reverse_factor = 2.54
                    elif units == "in":
                        m_conversion_factor = 0.01
                        reverse_factor = 1
                    elif units == "mm":
                        m_conversion_factor = 0.001
                        reverse_factor = 25.4
                    
                    xsize = float(kwargs['frame_attrs']['svg:width'][:-2])
                    ysize = float(kwargs['frame_attrs']['svg:height'][:-2])

                    meterxsize = xsize*m_conversion_factor
                    meterysize = ysize*m_conversion_factor

                    width = int(xsize/reverse_factor*dpi)
                    height = int(ysize/reverse_factor*dpi)
                    aspect_ratio = width/height

                    img_temppath = tempfile.NamedTemporaryFile(suffix=".png",delete=False).name
                    
                    if image_metadata[0] == 'canvas':
                        print ("CANVAAS", theme)
                        view_box = getFrame(self.iface.mapCanvas().extent())
                        img = self.canvas_image(box=view_box,width=width,height=height,theme=theme)
                        img.save(img_temppath)

                    elif image_metadata[0] == 'feature':
                        layer = QgsProject.instance().mapLayer(image_metadata[1])
                        feature = layer.getFeature(value['id'])
                        QgsExpressionContextUtils.layerScope(layer).setVariable("atlas_featureid", value['id'])
                        QgsExpressionContextUtils.layerScope(layer).setVariable("atlas_feature", feature)
                        print ("GEOM BOX", feature.geometry().boundingBox().width() )
                        view_box = getFrame(feature.geometry().boundingBox())
                        img = self.canvas_image(box=view_box,width=width,height=height)
                        img.save(img_temppath)
                        
                    elif image_metadata[0] == 'layer':
                        layer = QgsProject.instance().mapLayer(image_metadata[1])
                        view_box = getFrame(layer.extent())
                        img = self.canvas_image(box=view_box,width=width,height=height,theme=layer)
                        img.save(img_temppath)
                        
                    elif image_metadata[0] in ('layout', 'atlas'):
                        #https://anitagraser.com/pyqgis-101-introduction-to-qgis-python-programming-for-non-programmers/pyqgis-101-exporting-layouts/
                        manager = QgsProject.instance().layoutManager()
                        layout = manager.layoutByName(image_metadata[1])
                        if image_metadata[0] == 'atlas': # is atlas
                            layout.atlas().seekTo(value['id'])
                            print ("SEEKto", value['id'])
                            layout.atlas().refreshCurrentFeature()
                        exporter = QgsLayoutExporter(layout)
                        print ("UNITS",layout.pageCollection().page(0).pageSize() )
                        aspect_ratio = layout.pageCollection().page(0).pageSize().width()/layout.pageCollection().page(0).pageSize().height()
                        settings = exporter.ImageExportSettings()
                        print (settings.imageSize)
                        if width > height:
                            height = width*aspect_ratio
                        else:
                            width = height*aspect_ratio
                        settings.imageSize = QSize(width ,height)
                        settings.dpi = dpi
                        settings.cropToContents = False
                        #settings.pages = [0]
                        print ( xsize, ysize, settings.imageSize, settings.dpi)
                        res = exporter.exportToImage(img_temppath, settings)
                        print ("LAYOUT EXPORT RESULT",res, exporter.errorFile())
                    else:
                        raise Exception("Can't export image. Item must be feature, layer or layout.")
                        
                    print (img_temppath)
                    return (open(img_temppath, 'rb'), mimetype)
                        
                result = engine.render(mdNameInfo.absoluteFilePath(), layouts=layouts, layers=layers, globals=globals, features = feat_dicts )

                with open(os.path.join(dd, 'rendered_document.odt'), 'wb') as output:
                    output.write(result)
                    output.flush()

                print ( "VARIABLES", engine.render_vars  )

    def canvas_image(self,box=None,width=150,height=150,theme=None):
        if isinstance(box, QgsRectangle):
            bb = box
        elif isinstance(box, QgsGeometry):
            bb = box.boundingBox()
        else:
            bb = self.iface.mapCanvas().extent()
        img = self.exporter.image_shot(bb,width,height,theme)
        return img


    def canvas_base64_image(self,box=None,xsize=150,ysize=150,theme=None):
        if isinstance(box, QgsRectangle):
            bb = box
        elif isinstance(box, QgsGeometry):
            bb = box.boundingBox()
        else:
            bb = self.iface.mapCanvas().extent()
        base64_img = self.exporter.base64_shot(bb,xsize,ysize,theme)
        #print (str(base64_img))
        return base64_img


class canvas_image_exporter:

    def __init__(self, main_canvas):
        self.main_canvas = main_canvas
        self.canvas = QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.white)
        self.canvas.setLayers(self.main_canvas.mapSettings().layers())
        self.canvas.refresh()
        self.canvas.update()
        self.settings = self.main_canvas.mapSettings()

    def image_shot(self, extent, xsize, ysize,theme):
        #self.canvas.resize(xsize,ysize) #QSize(xsize,ysize)
        if theme:
            if isinstance(theme, str):
                self.canvas.setTheme(theme)
            elif issubclass(type(theme),QgsMapLayer):
                self.canvas.setLayers([theme])
            else:
                self.canvas.setLayers(self.main_canvas.layers())
        
        self.canvas.setExtent(extent)
        self.canvas.refresh()
        self.canvas.update()
        print ("export settings2:", extent,"xsize:", extent.xMaximum() - extent.xMinimum(),xsize,"ysize:", extent.yMaximum() - extent.yMinimum(),ysize )
        mapSettings = self.canvas.mapSettings()
        mapSettings.setOutputSize( QSize(xsize,ysize ) )
        job = QgsMapRendererParallelJob(mapSettings)
        job.start()
        job.waitForFinished()
        image = job.renderedImage()
        return image

    def base64_shot(self, extent, xsize, ysize, theme, around_border):
        image = self.image_shot(extent,xsize,ysize,theme,around_border)

        #canvas_image = QImage(image.width(), image.height(), QImage.Format_ARGB32)
        #canvas_image.fill(Qt.transparent)
        #p = QPainter(canvas_image)
        #mask = image.createMaskFromColor(QColor(255, 255, 255).rgb(), Qt.MaskInColor)
        #p.setClipRegion(QRegion(QBitmap(QPixmap.fromImage(mask))))
        #p.drawPixmap(0, 0, QPixmap.fromImage(image))
        #p.end()

        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, 'PNG')
        base64_data = ba.toBase64().data()

        return "data:image/png;base64," + str(base64_data, 'UTF-8')
