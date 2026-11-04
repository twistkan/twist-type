TOKENS = {
    'background': '#FAFAFE', 'surface': '#FFFFFF', 'ink': '#262633',
    'muted': '#565B6D', 'accent': '#37318C', 'accent_hover': '#292467',
    'border': '#AAAAC0', 'selected': '#E8E8FF', 'danger': '#A92336',
    'sidebar': '#E9E9FC', 'card_border': '#DEDEEB', 'blue_card': '#EAF3FA',
    'peach_card': '#FFF0E5', 'mint_card': '#DDF3EE',
    'popup_surface': '#14233B', 'popup_text': '#FFFFFF', 'popup_muted': '#B8C7DA',
    'popup_highlight': '#0066FF', 'popup_border': '#74A7FF', 'popup_font': 15,
    'font': 'Segoe UI', 'body': 14, 'radius': 8, 'space': 12,
}


def apply_theme(app):
    from PySide6.QtGui import QColor, QPalette
    app.setStyle('Fusion')
    palette = QPalette()
    for role, token in ((QPalette.ColorRole.Window, 'background'), (QPalette.ColorRole.Base, 'surface'),
                        (QPalette.ColorRole.Text, 'ink'), (QPalette.ColorRole.WindowText, 'ink'),
                        (QPalette.ColorRole.Button, 'surface'), (QPalette.ColorRole.ButtonText, 'ink'),
                        (QPalette.ColorRole.Highlight, 'popup_highlight'),
                        (QPalette.ColorRole.HighlightedText, 'popup_text'),
                        (QPalette.ColorRole.PlaceholderText, 'muted')):
        palette.setColor(role, QColor(TOKENS[token]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(TOKENS['muted']))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(TOKENS['muted']))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet())


def configure_combo_popup(combo):
    # Qt's default combo delegate may paint like a native menu and bypass
    # item-view stylesheet colors. A styled delegate honors every popup state.
    from PySide6.QtWidgets import QStyledItemDelegate
    combo.setItemDelegate(QStyledItemDelegate(combo))


def stylesheet():
    t = TOKENS
    return f'''
    QWidget {{font-family: "{t['font']}"; font-size: {t['body']}px; color: {t['ink']};}}
    QMainWindow, QDialog {{background: {t['background']};}}
    QFrame#card {{background: {t['surface']}; border: 1px solid {t['card_border']}; border-radius: {t['radius']}px;}}
    QFrame#sidebar {{background: {t['sidebar']}; border-right: 1px solid {t['card_border']};}}
    QListWidget#navigation {{background: {t['sidebar']}; border: 0; padding: 0; font-weight: 600;}}
    QListWidget#navigation::item {{padding: 14px 12px; margin-bottom: 7px; border-radius: 10px;}}
    QListWidget#navigation::item:selected {{background: {t['accent']}; color: {t['surface']};}}
    QFrame#statBlue {{background: {t['blue_card']}; border-radius: 10px;}}
    QFrame#statPeach {{background: {t['peach_card']}; border-radius: 10px;}}
    QFrame#statMint {{background: {t['mint_card']}; border-radius: 10px;}}
    QLabel#metric {{font-size: 24px; font-weight: 650; color: {t['ink']};}}
    QLabel#eyebrow {{font-size: 11px; font-weight: 650; color: {t['muted']};}}
    QScrollArea {{border: 0; background: {t['background']};}}
    QLabel#brand {{font-size: 26px; font-weight: 700;}}
    QLabel#heading {{font-size: 22px; font-weight: 650;}}
    QLabel#muted {{color: {t['muted']};}}
    QLineEdit, QPlainTextEdit, QListWidget, QComboBox {{background: {t['surface']}; border: 1px solid {t['border']}; border-radius: {t['radius']}px; padding: 9px; selection-background-color: {t['accent']}; selection-color: {t['surface']};}}
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QPushButton:focus {{border: 2px solid {t['accent']};}}
    QMenu {{background-color: {t['popup_surface']}; color: {t['popup_text']}; border: 1px solid {t['popup_border']}; padding: 6px; font-size: {t['popup_font']}px; font-weight: 600;}}
    QMenu::item {{background-color: {t['popup_surface']}; color: {t['popup_text']}; padding: 8px 28px 8px 12px; border-radius: 4px;}}
    QMenu::item:selected {{background-color: {t['popup_highlight']}; color: {t['popup_text']};}}
    QMenu::item:disabled {{color: {t['popup_muted']}; background-color: {t['popup_surface']};}}
    QMenu::separator {{height: 1px; background-color: {t['popup_border']}; margin: 5px 8px;}}
    QComboBox QAbstractItemView {{background-color: {t['popup_surface']}; alternate-background-color: {t['popup_surface']}; color: {t['popup_text']}; border: 1px solid {t['popup_border']}; selection-background-color: {t['popup_highlight']}; selection-color: {t['popup_text']}; outline: 0; padding: 4px; font-size: {t['popup_font']}px; font-weight: 600;}}
    QComboBox QAbstractItemView::item {{min-height: 32px; padding: 4px 10px; background-color: {t['popup_surface']}; color: {t['popup_text']};}}
    QComboBox QAbstractItemView::item:selected {{background-color: {t['popup_highlight']}; color: {t['popup_text']};}}
    QComboBox QAbstractItemView::item:disabled {{background-color: {t['popup_surface']}; color: {t['popup_muted']};}}
    QListWidget {{outline: 0;}}
    QListWidget::item {{padding: 12px; border-radius: 6px; margin-bottom: 4px;}}
    QListWidget::item:selected {{background: {t['selected']}; color: {t['ink']};}}
    QPushButton {{background: {t['surface']}; border: 1px solid {t['border']}; border-radius: {t['radius']}px; padding: 9px 16px;}}
    QPushButton:hover {{background: {t['selected']};}}
    QPushButton#primary {{background: {t['accent']}; color: {t['surface']}; border-color: {t['accent']}; font-weight: 600;}}
    QPushButton#primary:hover {{background: {t['accent_hover']};}}
    QPushButton#danger {{color: {t['danger']};}}
    QPushButton:disabled {{color: {t['muted']}; background: {t['background']};}}
    QTabWidget::pane {{border: 0;}}
    QTabBar::tab {{padding: 10px 20px; margin: 0 4px 10px 0; border-bottom: 3px solid transparent;}}
    QTabBar::tab:selected {{border-bottom-color: {t['accent']}; color: {t['accent']}; font-weight: 600;}}
    QCheckBox {{spacing: 8px;}} QStatusBar {{color: {t['muted']};}}
    '''
