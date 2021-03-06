from webappbuilder.webbappwidget import WebAppWidget
import os
from PyQt4.QtGui import QIcon
from webappbuilder.utils import safeName

class AttributesTable(WebAppWidget):

    zoomLevels = list((str(i) for i in xrange(1,33)))

    _parameters = {"Zoom level when zooming to point feature": ("16", zoomLevels),
                   "pageSize": 20,
                   "sortable": True}

    order = 2

    def write(self, appdef, folder, app, progress):
        self.addReactComponent(app, "FeatureTable")
        pointZoom = int(self._parameters["Zoom level when zooming to point feature"][0])
        pageSize = int(self._parameters["pageSize"])
        allowEdit =  str("drawfeature" in appdef["Widgets"]).lower()
        sortable =  str(self._parameters["sortable"]).lower()
        theme = appdef["Settings"]["Theme"]
        if theme == "tabbed":
            idx = len(app.tabs) + 1
            app.tabs.append('''React.createElement(Tab,{key:%i, value:%i, label:"Attributes table"},
                                    React.createElement(FeatureTable, {allowEdit:%s, toggleGroup: 'navigation',
                                                                    ref:"table", pointZoom:%d, map: map,
                                                                    sortable:%s, pageSize:%s})
                                )''' % (idx, idx, allowEdit, pointZoom, sortable, pageSize))
        else:
            app.tools.append("React.createElement(Button, {buttonType: 'Icon', iconClassName: 'headerIcons ms ms-table', tooltip: 'Table', onTouchTap: this._toggleTable.bind(this)})")
            app.panels.append(''' React.createElement("div", {id: 'table-panel', className: 'attributes-table'},
                                          React.createElement(FeatureTable, {allowEdit:%s, toggleGroup: 'navigation',
                                                              ref: 'table', pointZoom:%d, map: map,
                                                              sortable:%s, pageSize:%s})
                                    )''' % (allowEdit, pointZoom, sortable, pageSize))


    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "attribute-table.png"))

    def iconFile(self):
        return os.path.join(os.path.dirname(__file__), "attribute-table.png")

    def description(self):
        return "Attributes table"

    def checkProblems(self, appdef, problems, forPreview):
        layers = appdef["Layers"]
        nonVectorLayers = 0
        for applayer in layers:
            layer = applayer.layer
            if layer.type() != layer.VectorLayer:
                nonVectorLayers += 1

        if nonVectorLayers == len(layers):
            problems.append("Attributes table control has been added, but there are no suitable "
                            "layers to in the web app to be used with it. "
                            "Local vector layers or WFS layers are needed")
