"""Small, consistent action symbols for the native video workflow."""
from PySide6.QtCore import Qt,QByteArray
from PySide6.QtGui import QIcon,QPainter,QPixmap
from PySide6.QtSvg import QSvgRenderer


def action_icon(name,color='#FFFFFF'):
    shapes={
        'start':'<path d="M8 5 L20 12 L8 19 Z" fill="%s"/>'%color,
        'wait':'<circle cx="12" cy="12" r="8"/><path d="M12 7 V12 L16 14"/>',
        'record':'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="5" fill="%s" stroke="none"/>'%color,
        'stop':'<rect x="6" y="6" width="12" height="12" rx="2" fill="%s"/>'%color,
        'preset':'<path d="M8 6 H20 M8 12 H20 M8 18 H20"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
        'update':'<path d="M19 8 A8 8 0 0 0 5 7 M5 7 V3 M5 7 H9 M5 16 A8 8 0 0 0 19 17 M19 17 V21 M19 17 H15"/>',
    }
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">%s</g></svg>'%(color,shapes[name])
    pixmap=QPixmap(24,24);pixmap.fill(Qt.transparent)
    painter=QPainter(pixmap);QSvgRenderer(QByteArray(svg.encode())).render(painter);painter.end()
    icon=QIcon(pixmap);icon.addPixmap(pixmap,QIcon.Disabled)
    return icon
