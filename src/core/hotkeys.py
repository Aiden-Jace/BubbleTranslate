"""共享的快捷键校验及 Windows / pynput 格式转换。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence


_SPECIAL_KEYS = {
    Qt.Key_Space: (0x20, "<space>"),
    Qt.Key_Tab: (0x09, "<tab>"),
    Qt.Key_Return: (0x0D, "<enter>"),
    Qt.Key_Escape: (0x1B, "<esc>"),
    Qt.Key_Backspace: (0x08, "<backspace>"),
    Qt.Key_Delete: (0x2E, "<delete>"),
    Qt.Key_Insert: (0x2D, "<insert>"),
    Qt.Key_Home: (0x24, "<home>"),
    Qt.Key_End: (0x23, "<end>"),
    Qt.Key_PageUp: (0x21, "<page_up>"),
    Qt.Key_PageDown: (0x22, "<page_down>"),
    Qt.Key_Left: (0x25, "<left>"),
    Qt.Key_Up: (0x26, "<up>"),
    Qt.Key_Right: (0x27, "<right>"),
    Qt.Key_Down: (0x28, "<down>"),
}
_MODIFIERS = (
    (Qt.ControlModifier, 0x0002, "<ctrl>"),
    (Qt.AltModifier, 0x0001, "<alt>"),
    (Qt.ShiftModifier, 0x0004, "<shift>"),
    (Qt.MetaModifier, 0x0008, "<cmd>"),
)


def parse_hotkey(value):
    sequence = QKeySequence.fromString(value, QKeySequence.PortableText)
    if sequence.isEmpty() or sequence.count() != 1:
        raise ValueError("请设置一个按键或组合键，不能留空或使用连续多组按键。")
    combination = sequence[0]
    key = combination.key()
    modifiers = combination.keyboardModifiers()
    allowed = Qt.NoModifier
    windows_modifiers = 0
    pynput_parts = []
    for modifier, windows_flag, pynput_name in _MODIFIERS:
        allowed |= modifier
        if modifiers & modifier:
            windows_modifiers |= windows_flag
            pynput_parts.append(pynput_name)
    if modifiers & ~allowed:
        raise ValueError("此快捷键的修饰键暂不支持。")

    if Qt.Key_F1 <= key <= Qt.Key_F12:
        number = int(key) - int(Qt.Key_F1) + 1
        windows_key, pynput_key = 0x6F + number, f"<f{number}>"
    elif Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
        windows_key, pynput_key = int(key), chr(int(key)).lower()
    elif key in _SPECIAL_KEYS:
        windows_key, pynput_key = _SPECIAL_KEYS[key]
    else:
        raise ValueError("请使用 F1–F12、字母、数字或常用导航键，可搭配 Ctrl、Alt、Shift、Meta。")
    pynput_parts.append(pynput_key)
    return (
        sequence.toString(QKeySequence.PortableText),
        (windows_modifiers, windows_key),
        "+".join(pynput_parts),
    )


def validate_hotkeys(screenshot, text):
    screenshot = parse_hotkey(screenshot)[0]
    text = parse_hotkey(text)[0]
    if screenshot == text:
        raise ValueError("截屏翻译和划词翻译不能使用相同的快捷键。")
    return screenshot, text
