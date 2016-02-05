from webappbuilder.webbappwidget import WebAppWidget
import os
from PyQt4.QtGui import QIcon

class ExportAsImage(WebAppWidget):

    def write(self, appdef, folder, app, progress):
        app.tools.append("<ul className='pull-right' id='toolbar-export'><ImageExport map={map} /></ul>")
        app.toolsjs.append('''React.createElement("ul", {id: 'toolbar-export', className: 'pull-right'},
                                    React.createElement(ImageExport, {map:map})
                                  )''')
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "export-as-image.png"))

    def description(self):
        return "Export image"