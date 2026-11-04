from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from core import Store
from theme import apply_theme
from clipboard_core import HistoryStore
from clipboard_service import ClipboardService
from twisttype import Events, Window
from win_engine import Engine

app = QApplication([])
apply_theme(app)
store = Store(ROOT / 'snippets.yaml')
store.load()
events = Events()
engine = Engine(store.data, events.event.emit)
history = HistoryStore()
for i in range(20):
    history.add('text', f'Demo note {i + 1}: a useful paragraph saved for later.', 'notepad.exe')
history.add('text', 'Thanks for the update. I will review it this afternoon.', 'outlook.exe')
service = ClipboardService(history, store.data['settings'])
window = Window(store, engine, events, service)
window.show()
out = ROOT / 'replica' / 'clone-screens'
out.mkdir(parents=True, exist_ok=True)
for name, index in [('library', 0), ('clipboard', 3), ('settings', 1), ('help', 2)]:
    window.tabs.setCurrentIndex(index)
    app.processEvents()
    window.grab().save(str(out / (name + '.png')))
window.tabs.setCurrentIndex(1)
app.processEvents()
window.tabs.widget(1).verticalScrollBar().setValue(window.tabs.widget(1).verticalScrollBar().maximum())
app.processEvents()
window.grab().save(str(out / 'clipboard-settings.png'))
window.picker.open_picker()
app.processEvents()
window.picker.grab().save(str(out / 'clipboard-picker.png'))
window.picker.close()
window.timer.stop()
window.tray.hide()
window.quitting = True
window.close()
