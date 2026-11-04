"""Render an original folded T mark into multi-resolution ICO using Qt."""
from pathlib import Path
import struct
import sys

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen


def render(size):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 256, size / 256)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#155E75'))
    painter.drawRoundedRect(8, 8, 240, 240, 55, 55)
    painter.setPen(QPen(QColor('#FFFFFF'), 24, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    mark = QPainterPath()
    mark.moveTo(62, 76)
    mark.lineTo(190, 76)
    mark.moveTo(128, 76)
    mark.lineTo(128, 151)
    mark.cubicTo(128, 190, 181, 190, 181, 151)
    painter.drawPath(mark)
    painter.setPen(QPen(QColor('#88E0D5'), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(67, 164, 90, 187)
    painter.drawLine(90, 187, 67, 210)
    painter.end()
    return image


def main():
    app = QGuiApplication(sys.argv)
    target = Path(__file__).parent
    frames = []
    sizes = [16, 24, 32, 48, 64, 128, 256]
    for size in sizes:
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        render(size).save(buf, 'PNG')
        frames.append(bytes(data))
    offset = 6 + 16 * len(sizes)
    entries = []
    for size, frame in zip(sizes, frames):
        entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(frame), offset))
        offset += len(frame)
    (target / 'twisttype.ico').write_bytes(struct.pack('<HHH', 0, 1, len(sizes)) + b''.join(entries) + b''.join(frames))
    render(256).save(str(target / 'twisttype.png'))


if __name__ == '__main__':
    main()
