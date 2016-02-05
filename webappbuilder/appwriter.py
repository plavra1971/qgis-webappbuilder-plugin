import codecs
import os
import shutil
from qgis.core import *
from qgis.utils import iface
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtSvg import *
from utils import *
from settings import *
from olwriter import exportStyles, layerToJavascript
from collections import OrderedDict
import jsbeautifier
from operator import attrgetter

def writeWebApp(appdef, folder, writeLayersData, forPreview, progress):
    progress.setText("Copying resources files")
    progress.setProgress(0)
    dst = os.path.join(folder, "webapp")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    sdkFolder = os.path.join(os.path.dirname(__file__), "websdk_full")
    shutil.copytree(sdkFolder, dst)

    cssFolder = os.path.join(os.path.dirname(__file__), "css")
    shutil.copytree(cssFolder, os.path.join(dst, "css"))
    QDir().mkpath(os.path.join(dst, "data"))
    QDir().mkpath(os.path.join(dst, "resources"))
    layers = appdef["Layers"]
    if writeLayersData:
        exportLayers(layers, dst, progress,
                     appdef["Settings"]["Precision for GeoJSON export"],
                     appdef["Settings"]["App view CRS"], forPreview)

    class App():
        tabs = []
        tabsjs = []
        ol3controls = []
        tools = []
        panels = []
        mappanels = []
        toolsjs = []
        panelsjs = []
        mappanelsjs = []
        variables = []
        scripts = []
        scriptsbody = []
        posttarget = []
        imports = ["import React from 'react';",
                   "import ReactDOM from 'react-dom';",
                    "import ol from 'openlayers';",
                    "import {IntlProvider} from 'react-intl';",
                    "import UI from 'pui-react-buttons';",
                    "import Icon from 'pui-react-iconography';",
                    "import InfoPopup from './node_modules/boundless-sdk/js/components/InfoPopup.jsx';"
                   ]
        def newInstance(self):
            _app = App()
            _app.tabs = list(self.tabs)
            _app.tabsjs = list(self.tabsjs)
            _app.ol3controls = list(self.ol3controls)
            _app.tools = list(self.tools)
            _app.panels = list(self.panels)
            _app.mappanels = list(self.mappanels)
            _app.toolsjs = list(self.toolsjs)
            _app.panelsjs = list(self.panelsjs)
            _app.mappanelsjs = list(self.mappanelsjs)
            _app.variables = list(self.variables)
            _app.scripts = list(self.scripts)
            _app.scriptsbody = list(self.scriptsbody)
            _app.posttarget = list(self.posttarget)
            _app.imports = list(self.imports)
            return _app

    _app = App()
    exportStyles(layers, dst, appdef["Settings"], "timeline" in appdef["Widgets"], _app, progress)
    writeLayersAndGroups(appdef, dst, _app, forPreview, progress)

    widgets = sorted(appdef["Widgets"].values(), key=attrgetter('order'))
    for w in widgets:
        w.write(appdef, dst, _app, progress)

    writeCss(appdef, dst)

    baseTarget = "_self" if appdef["Settings"]["Open hyperlinks in"] == 0 else "_blank"
    _app.scripts.append("<base target='%s'>" % baseTarget)

    if forPreview:
        app = _app.newInstance()
        writeJs(appdef, dst, app, progress)
        app.scriptsbody.extend(['<script src="full-debug.js"></script>',
                                '<script src="app_prebuilt.js"></script>'])
        for layer in appdef["Layers"]:
            if layer.layer.type() == layer.layer.VectorLayer and layer.method == METHOD_FILE:
                app.scriptsbody.append('<script src="./data/lyr_%s.js"></script>' % safeName(layer.layer.name()))
        writeHtml(appdef, dst, app, progress, "index_debug.html")

    else:
        app = _app.newInstance()
        writeJsx(appdef, dst, app, progress)

        app = _app.newInstance()
        app.scriptsbody.extend(['<script src="app.js"></script>'])
        writeHtml(appdef, dst, app, progress, "index_node.html") # with SDK

def writeJs(appdef, folder, app, progress):
    layers = appdef["Layers"]
    viewCrs = appdef["Settings"]["App view CRS"]
    mapbounds = bounds(appdef["Settings"]["Extent"] == "Canvas extent", layers, viewCrs)
    mapextent = "extent: %s," % mapbounds if appdef["Settings"]["Restrict to extent"] else ""
    maxZoom = int(appdef["Settings"]["Max zoom level"])
    minZoom = int(appdef["Settings"]["Min zoom level"])

    app.variables.append("var view = new ol.View({%s maxZoom: %d, minZoom: %d, projection: '%s'});" % (mapextent, maxZoom, minZoom, viewCrs))
    app.variables.append("var originalExtent = %s;" % mapbounds)

    logoImg = appdef["Settings"]["Logo"].strip()
    if logoImg:
        logo = '<img className="pull-left" style={{margin:"5px",height:"50px"}} src="logo.png"></img>'
        ext = os.path.splitext(logoImg)[1]
        shutil.copyfile(logoImg, os.path.join(folder, "logo" + ext))
    else:
        logo = ""

    variables ="\n".join(app.variables)

    app.mappanelsjs.append('''React.createElement("div", {id: 'popup', className: 'ol-popup'},
                                    React.createElement(InfoPopup, {map: map, hover: %s})
                                  )''' % str(appdef["Settings"]["Show popups on hover"]).lower())

    def join(array):
        if array:
            return ",\n" + ",\n".join(array)
        else:
            return ""
    values = {"@LOGO@": logo,
                "@TABS@": join(app.tabsjs),
                "@OL3CONTROLS@": ",\n".join(app.ol3controls),
                "@TITLE@": appdef["Settings"]["Title"],
                "@PANELS@": join(app.panelsjs),
                "@MAPPANELS@": join(app.mappanelsjs),
                "@TOOLBAR@": join(app.toolsjs),
                "@VARIABLES@": variables,
                "@POSTTARGETSET@": "\n".join(app.posttarget)}

    template = os.path.join(os.path.dirname(__file__), "themes",
                            appdef["Settings"]["Theme"], "app.js")
    js = replaceInTemplate(template, values)
    try:
        js = jsbeautifier.beautify(js)
    except:
        pass #jsbeautifier gives some random errors sometimes due to imports

    jsFilepath = os.path.join(folder, "app_prebuilt.js")
    with open(jsFilepath, "w") as f:
        f.write(js)

def writeJsx(appdef, folder, app, progress):
    imports = app.imports
    layers = appdef["Layers"]
    viewCrs = appdef["Settings"]["App view CRS"]
    mapbounds = bounds(appdef["Settings"]["Extent"] == "Canvas extent", layers, viewCrs)
    mapextent = "extent: %s," % mapbounds if appdef["Settings"]["Restrict to extent"] else ""
    maxZoom = int(appdef["Settings"]["Max zoom level"])
    minZoom = int(appdef["Settings"]["Min zoom level"])

    app.variables.append("var view = new ol.View({%s maxZoom: %d, minZoom: %d, projection: '%s'});" % (mapextent, maxZoom, minZoom, viewCrs))
    app.variables.append("var originalExtent = %s;" % mapbounds)

    permalink = appdef["Settings"]["Add permalink functionality"]
    if permalink:
        permalinkCode = '''var shouldUpdate = true;
        var updatePermalink = function() {
          if (!shouldUpdate) {
            // do not update the URL when the view was changed in the 'popstate' handler
            shouldUpdate = true;
            return;
          }

          var center = view.getCenter();
          var hash = '#map=' +
              view.getZoom() + '/' +
              Math.round(center[0] * 100) / 100 + '/' +
              Math.round(center[1] * 100) / 100 + '/' +
              view.getRotation();
          var state = {
            zoom: view.getZoom(),
            center: view.getCenter(),
            rotation: view.getRotation()
          };
          window.history.pushState(state, 'map', hash);
        };

        map.on('moveend', updatePermalink);

        // restore the view state when navigating through the history, see
        // https://developer.mozilla.org/en-US/docs/Web/API/WindowEventHandlers/onpopstate
        window.addEventListener('popstate', function(event) {
          if (event.state === null) {
            return;
          }
          map.getView().setCenter(event.state.center);
          map.getView().setZoom(event.state.zoom);
          map.getView().setRotation(event.state.rotation);
          shouldUpdate = false;
        });'''
        app.posttarget.append(permalinkCode)

    logoImg = appdef["Settings"]["Logo"].strip()
    if logoImg:
        logo = '<img className="pull-left" style={{margin:"5px",height:"50px"}} src="logo.png"></img>'
        ext = os.path.splitext(logoImg)[1]
        shutil.copyfile(logoImg, os.path.join(folder, "logo" + ext))
    else:
        logo = ""

    variables ="\n".join(app.variables)
    try:
        variables = jsbeautifier.beautify(variables)
    except:
        pass #jsbeautifier gives some random errors sometimes due to imports

    values = {"@LOGO@": logo,
                "@TABS@": "\n".join(app.tabs),
                "@OL3CONTROLS@": ",\n".join(app.ol3controls),
                "@TITLE@": appdef["Settings"]["Title"],
                "@POPUPEVENT@": str(appdef["Settings"]["Show popups on hover"]).lower(),
                "@PANELS@": "\n".join(app.panels),
                "@MAPPANELS@": "\n".join(app.mappanels),
                "@TOOLBAR@": "\n".join(app.tools),
                "@VARIABLES@": variables,
                "@POSTTARGETSET@": "\n".join(app.posttarget),
                "@IMPORTS@": "\n".join(imports)}

    template = os.path.join(os.path.dirname(__file__), "themes",
                            appdef["Settings"]["Theme"], "app.jsx")
    jsx = replaceInTemplate(template, values)

    name = "app.jsx"
    jsxFilepath = os.path.join(folder, name)
    with open(jsxFilepath, "w") as f:
        f.write(jsx)


def writeCss(appdef, folder):
    dst = os.path.join(folder, "app.css")
    src = os.path.join(os.path.dirname(__file__), "themes", appdef["Settings"]["Theme"], "app.css")
    shutil.copy(src, dst)

def writeHtml(appdef, folder, app, progress, filename):
    layers = appdef["Layers"]
    viewCrs = appdef["Settings"]["App view CRS"]

    for applayer in layers:
        layer = applayer.layer
        useViewCrs = appdef["Settings"]["Use view CRS for WFS connections"]
        if layer.providerType().lower() == "wfs":
            epsg = layer.crs().authid().split(":")[-1]
            if not useViewCrs and epsg not in ["3857", "4326"]:
                app.scripts.append('<script src="./proj4.js"></script>')
                app.scripts.append('<script src="http://epsg.io/%s.js"></script>' % epsg)

    viewEpsg = viewCrs.split(":")[-1]
    if viewEpsg not in ["3857", "4326"]:
            app.scripts.append('<script src="./proj4.js"></script>')
            app.scripts.append('<script src="http://epsg.io/%s.js"></script>' % viewEpsg)


    values = {"@TITLE@": appdef["Settings"]["Title"],
                "@SCRIPTS@": "\n".join(OrderedDict((item,None) for item in app.scripts).keys()),
                "@SCRIPTSBODY@": "\n".join(OrderedDict((item,None) for item in app.scriptsbody).keys())
            }

    template = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    html = replaceInTemplate(template, values)

    indexFilepath = os.path.join(folder, filename)
    try:
        from bs4 import BeautifulSoup as bs
        soup=bs(html)
        pretty=soup.prettify(formatter='html')
    except:
        pretty = html
    with open(indexFilepath, "w") as f:
        f.write(pretty)



def writeLayersAndGroups(appdef, folder, app, forPreview, progress):
    base = appdef["Base layers"]
    layers = appdef["Layers"]
    deploy = appdef["Deploy"]
    groups = appdef["Groups"]
    widgets = appdef["Widgets"]
    baseJs =[]
    overlaysJs =[]
    for b in base:
        if b in baseLayers:
            baseJs.append(baseLayers[b])
        elif b in baseOverlays:
            overlaysJs.append(baseOverlays[b])
    if baseJs:
        baseLayer = '''var baseLayers = [new ol.layer.Tile({
                        type: 'base',
                        title: 'No base layer'
                    }),%s];''' % ",".join(baseJs)
    else:
        baseLayer = "var baseLayers = [];"

    baseLayer += '''var baseLayersGroup = new ol.layer.Group({showContent: true,'type':
                    'base-group', 'title': 'Base maps', layers: baseLayers});'''

    if overlaysJs:
        overlayLayer = '''var overlayLayers = [%s];''' % ",".join(overlaysJs)
    else:
        overlayLayer = "var overlayLayers = [];"

    overlayLayer += '''var overlaysGroup = new ol.layer.Group({showContent: true, 'title': 'Overlays', layers: overlayLayers});'''

    if "overviewmap" in widgets:
        overviewMapBaseLayerName = widgets["overviewmap"].parameters()["Base layer"]
        if overviewMapBaseLayerName == "Use main map base layer":
            baseLayer += "var overviewMapBaseLayer = baseLayersGroup;"
        else:
            baseLayer += "var overviewMapBaseLayer = %s;" % baseLayers[overviewMapBaseLayerName]

    layerVars = []
    progress.setText("Writing layer definitions")
    for i, layer in enumerate(layers):
        layerTitle = layer.layer.name() if layer.showInControls else None
        layerVars.append(layerToJavascript(layer, appdef["Settings"], deploy, layerTitle, forPreview))
        progress.setProgress(int((i+1)*100.0/len(layers)))
    layerVars = "\n".join(layerVars)
    groupVars = ""
    groupedLayers = {}
    for group, groupDef in groups.iteritems():
        groupLayers = groupDef["layers"]
        groupVars +=  ('''var %s = new ol.layer.Group({
                                layers: [%s],
                                showContent: %s,
                                title: "%s"});\n''' %
                ("group_" + safeName(group), ",".join(["lyr_" + safeName(layer.name()) for layer in groupLayers]),
                str(groupDef["showContent"]).lower(), group))
        for layer in groupLayers:
            groupedLayers[layer.id()] = safeName(group)

    visibility = "\n".join(["lyr_%s.setVisible(%s);" % (safeName(layer.layer.name()),
                                                str(layer.visible).lower()) for layer in layers])
    if baseJs:
        visibility += "for (var i=0;i<baseLayers.length;i++){baseLayers[i].setVisible(false);}"
        visibility += "baseLayers[1].setVisible(true);"

    layersList = []
    usedGroups = []
    for appLayer in layers:
        layer = appLayer.layer
        if layer.id() in groupedLayers:
            groupName = groupedLayers[layer.id()]
            if groupName not in usedGroups:
                layersList.append("group_" + safeName(groupName))
                usedGroups.append(groupName)
        else:
            layersList.append("lyr_" + safeName(layer.name()))



    layersList = "var layersList = [%s];" % (",".join([layer for layer in layersList]))
    groupBaseLayers = appdef["Settings"]["Group base layers"]

    if baseJs:
        if groupBaseLayers:
            layersList += "layersList.unshift(baseLayersGroup);"
        else:
            layersList += "Array.prototype.splice.apply(layersList, [0, 0].concat(baseLayers));"

    if overlaysJs:
        if groupBaseLayers:
            layersList += "layersList.push(overlaysGroup);"
        else:
            layersList += "layersList.push.apply(layersList, overlayLayers);"

    app.variables.append(baseLayer)
    app.variables.append(overlayLayer)
    app.variables.append(layerVars)
    app.variables.append(groupVars)
    app.variables.append(visibility)
    app.variables.append(layersList)


def bounds(useCanvas, layers, crsid):
    extent = None
    if useCanvas:
        canvas = iface.mapCanvas()
        canvasCrs = canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(canvasCrs, QgsCoordinateReferenceSystem(crsid))
        try:
            extent = transform.transform(canvas.extent())
        except:
            extent = None
    if extent is None:
        for layer in layers:
            transform = QgsCoordinateTransform(layer.layer.crs(), QgsCoordinateReferenceSystem(crsid))
            try:
                layerExtent = transform.transform(layer.layer.extent())
                if extent is None:
                    extent = layerExtent
                else:
                    extent.combineExtentWith(layerExtent)
            except QgsCsException:
                pass

    if extent is None:
        extent = QgsRectangle(-180, -90, 180, 90)
        transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem("ESPG:4326"), QgsCoordinateReferenceSystem(crsid))
        extent = transform.transform(extent)

    return "[%f, %f, %f, %f]" % (extent.xMinimum(), extent.yMinimum(),
                                extent.xMaximum(), extent.yMaximum())

