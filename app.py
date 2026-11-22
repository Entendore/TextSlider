"""
Slider Text Studio 6.0
======================
TWO TABS, 66 sliders — with a fully animated Generate tab.

TAB 1 — Transform (37 sliders)      TAB 2 — Generate (29 sliders)

New animation system for the Generate tab
-----------------------------------------
* ⏵ Animate (F5, contextual): generator sliders ride sine waves — prose
  rewrites itself, patterns boil, invented words churn. Speed adjusts live.
* 🔁 Evolve: the seed ticks forward continuously; the text mutates forever.
  Evolve rate follows the Speed slider.
* Text FX: generated text animates into the preview instead of snapping —
  Decode (Matrix-style scramble resolve), Typewriter, Wave (center-out),
  Cascade (line by line), or Instant. Scramble charset adapts to the engine
  (block glyphs for Pattern, letters for Prose/Syllables).
* 🎲 Animated dice roll: the seed slider glides to its new value with the
  selected easing curve — F6 rolls with animation too.
* One Speed slider drives wave speed, evolve rate and FX speed together.
* Layout-stable reveal: spaces and newlines hold their positions so the
  text resolves without jumping around.
* Perf guards: previews over 30 000 chars animate instantly instead of
  per-character, and the preview keeps its scroll position while animating.
"""

import json
import math
import random
import sys
import time
import zlib
from collections import deque
from pathlib import Path

from PySide6.QtCore import (
    QObject, QEvent, QEasingCurve, QPropertyAnimation, QPoint, QPointF,
    QRectF, Qt, QTimer, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QImage, QPainter, QPen, QPolygonF, QCursor,
    QKeySequence, QShortcut, QTransform, QGraphicsBlurEffect,
    QGraphicsDropShadowEffect, QTextBlockFormat, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGraphicsScene,
    QGraphicsTextItem, QGraphicsView, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMenu, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QTabWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

PRESET_FILE = Path.home() / ".slider_text_studio_presets.json"
STATE_FILE = Path.home() / ".slider_text_studio_state.json"
MAX_CHARS = 500_000
WRAP_WIDTH = 900
LEET = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7", "b": "8", "g": "9"}
NOISE = "*#~^!@"

SAMPLE_TEXT = (
    "The quick brown fox jumps over the lazy dog.\n"
    "Sixty-six sliders, two tabs, one studio.\n"
    "The Generate tab now boils: F5 makes its sliders dance,\n"
    "Evolve mutates the text forever, and every result\n"
    "resolves in with a scramble-decode flourish.\n"
)

# ---------------------------------------------------------------------------
# TAB 1 — transform slider registry
# ---------------------------------------------------------------------------
SLIDER_SPECS = [
    ("trim",     "content", "Keep only the first … of the text",      5, 100, 100, "%",  "Truncate the tail"),
    ("trimstart","content", "Cut away the first … of the text",       0,  95,   0, "%",  "Truncate the head"),
    ("drop",     "content", "Delete every Nth char (0 = off)",        0,  20,   0, "",   "Thin out characters; newlines survive"),
    ("upper",    "content", "UPPERCASE the first … of letters",       0, 100,   0, "%",  ""),
    ("sponge",   "content", "sPoNgEcAsE intensity",                   0, 100,   0, "%",  "Chaotic alternating case"),
    ("leet",     "content", "L33T-SPEAK intensity",                   0, 100,   0, "%",  "a→4 e→3 i→1 o→0 s→5 t→7 b→8 g→9"),
    ("vowel",    "content", "Drp th vwls ntnsty",                     0, 100,   0, "%",  "Delete vowels"),
    ("noise",    "content", "Sprinkle noise characters",              0,  40,   0, "%",  "Injects * # ~ ^ ! @"),
    ("gap",      "content", "Spaces between letters",                 0,  10,   0, "",   ""),
    ("wgap",     "content", "Extra spaces between words",             0,  10,   0, "",   ""),
    ("wpl",      "content", "Words per line (0 = keep lines)",        0,  40,   0, "",   "Re-wrap the text"),
    ("blank",    "content", "Blank lines between lines",              0,   5,   0, "",   ""),
    ("indent",   "content", "Indent every line by",                   0,  20,   0, "sp", ""),
    ("number",   "content", "Zero-padded line numbers (0 = off)",     0,   8,   0, "",   "Prefix 01, 02, 03 …"),
    ("sort",     "content", "Sort the first … of lines",              0, 100,   0, "%",  ""),
    ("reverse",  "content", "Reverse the first … of lines",           0, 100,   0, "%",  ""),
    ("shuffle",  "content", "Shuffle words in the first … of lines",  0, 100,   0, "%",  "Deterministic (no flicker)"),
    ("repeat",   "content", "Repeat the whole text",                  1,  50,   1, "x",  ""),
    ("size",   "font", "Font size",        6,  72, 14,  "pt", ""),
    ("lspace", "font", "Letter spacing",   0,  20,  0,  "px", ""),
    ("wspace", "font", "Word spacing",     0,  40,  0,  "px", ""),
    ("lineh",  "font", "Line height",      50, 250, 100,"%",  "100 % = single spacing"),
    ("weight", "font", "Font weight",      100, 900, 400, "", "100 thin … 900 black"),
    ("stretch","font", "Font stretch",     50, 200, 100,"%",  "Condensed … expanded"),
    ("red",       "colour", "Red",                   0, 255,  30, "",  ""),
    ("green",     "colour", "Green",                 0, 255,  30, "",  ""),
    ("blue",      "colour", "Blue",                  0, 255,  30, "",  ""),
    ("opacity",   "colour", "Text opacity",          5, 100, 100, "%", ""),
    ("bg_hue",    "colour", "Background hue",        0, 359,   0, "°", ""),
    ("bg_sat",    "colour", "Background saturation", 0, 100,   0, "%", ""),
    ("bg_bright", "colour", "Background brightness", 0, 100, 100, "%", ""),
    ("blur",      "effect", "Blur",                  0,  12,   0, "px", ""),
    ("glow",      "effect", "Glow",                  0,  30,   0, "px", "Drop-shadow radius, tinted with the text colour"),
    ("shadowoff", "effect", "Glow offset",           0,  20,   3, "px", ""),
    ("rotation",  "effect", "Rotation",              -180, 180, 0, "°", ""),
    ("zoom",      "effect", "Zoom",                  10, 300, 100, "%", "Ctrl+wheel also zooms"),
    ("skew",      "effect", "Skew",                  -60,  60,  0, "°", "Italic shear"),
]

GROUP_ORDER = ("content", "font", "colour", "effect")
GROUP_TITLES = {
    "content": "1  Content — rewrites the text (saved to file)",
    "font":    "2  Font — preview only",
    "colour":  "3  Colour — preview only",
    "effect":  "4  Effects — preview only",
}
DEFAULTS = {s[0]: s[5] for s in SLIDER_SPECS}

ACCENTS = {
    "content": "#ffb454",
    "font":    "#4da3ff",
    "colour":  "#ff5f9e",
    "effect":  "#b58cff",
}
GEN_ACCENTS = {
    "style":     "#2ec4b6",
    "Prose":     "#ffb454",
    "Syllables": "#7ddf64",
    "Pattern":   "#ff5f9e",
    "seed":      "#8fd0ff",
    "blend":     "#8fd0ff",
}

BUILTIN_PRESETS = {
    "Hacker":    {"leet": 55, "red": 0, "green": 255, "blue": 90, "bg_bright": 4, "glow": 12, "weight": 700, "size": 16},
    "Zine":      {"size": 26, "upper": 100, "rotation": -6, "zoom": 118, "lineh": 90, "weight": 800,
                  "red": 214, "green": 31, "blue": 140, "bg_hue": 48, "bg_sat": 90, "bg_bright": 96,
                  "lspace": 1, "blank": 1},
    "Ghost":     {"opacity": 22, "blur": 3, "glow": 6, "bg_bright": 25, "size": 20, "weight": 300,
                  "red": 220, "green": 225, "blue": 255},
    "Blueprint": {"bg_hue": 210, "bg_sat": 75, "bg_bright": 28, "red": 190, "green": 225, "blue": 255,
                  "skew": 7, "lspace": 2, "size": 15, "weight": 500},
    "Ransom":    {"shuffle": 35, "sort": 25, "noise": 8, "sponge": 30, "leet": 15, "gap": 1, "blank": 1,
                  "size": 18, "weight": 600, "rotation": -3, "red": 40, "green": 40, "blue": 40, "bg_bright": 92},
    "Sideways":  {"rotation": 90, "zoom": 90, "wpl": 6, "size": 14, "lspace": 2},
}

EASINGS = {
    "Linear":       QEasingCurve.Type.Linear,
    "Out Cubic":    QEasingCurve.Type.OutCubic,
    "In-Out Cubic": QEasingCurve.Type.InOutCubic,
    "Out Elastic":  QEasingCurve.Type.OutElastic,
    "Out Bounce":   QEasingCurve.Type.OutBounce,
}

# ---------------------------------------------------------------------------
# TAB 2 — generator slider registries
# ---------------------------------------------------------------------------
GEN_SEED_SPEC = ("gseed", "Seed", 1, 999, 42, "",
                 "Same seed + same sliders = same text. 🎲 / F6 rolls a new one — animated.")

GEN_STYLE_SPECS = [
    ("gsize",  "Font size",   6,  48,  14, "pt", ""),
    ("glh",    "Line height", 50, 250, 110, "%",  ""),
    ("gred",   "Red",         0, 255,  30, "",   ""),
    ("ggreen", "Green",       0, 255,  30, "",   ""),
    ("gblue",  "Blue",        0, 255,  30, "",   ""),
]
PROSE_SPECS = [
    ("g_words",   "Total words",                        10, 800, 120, "",  ""),
    ("g_sentlen", "Avg words per sentence",              3,  40,  12, "",  ""),
    ("g_adj",     "Adjective density",                   0, 100,  55, "%", ""),
    ("g_adv",     "Adverb density",                      0, 100,  30, "%", ""),
    ("g_comma",   "Comma / connector frequency",         0, 100,  25, "%", ""),
    ("g_par",     "Sentences per paragraph (0 = block)", 0,  12,   0, "",  ""),
    ("g_rich",    "Vocabulary richness",                 2, 100,  70, "%", "Low = the same few words, over and over"),
    ("g_repeat",  "Verbatim sentence repetition",        0,  60,   0, "%", "Reuses earlier sentences — hypnotic loops"),
]
SYLL_SPECS = [
    ("s_words", "Word count",              5, 600,  80, "",  ""),
    ("s_syl",   "Syllables per word",      1,   6,   3, "",  ""),
    ("s_onset", "Consonant onset chance",  0, 100,  85, "%", ""),
    ("s_coda",  "Consonant coda chance",   0, 100,  30, "%", ""),
    ("s_dbl",   "Double-letter chance",    0,  60,   8, "%", ""),
    ("s_caps",  "Capitalized words",       0, 100,   8, "%", ""),
    ("s_wpl",   "Words per line (0 = flow)", 0, 30,  0, "",  ""),
]
PAT_SPECS = [
    ("p_rule",   "Cellular rule (0–255)",   0, 255,  90, "",  "Try 30, 90, 110, 184!"),
    ("p_width",  "Width (columns)",        16, 140,  72, "",  ""),
    ("p_height", "Height (rows)",           6,  90,  36, "",  ""),
    ("p_dens",   "First-row live cells",    0, 100,  25, "%", ""),
    ("p_noise",  "Static noise overlay",    0,  30,   0, "%", ""),
    ("p_set",    "Character set",           0,   5,   0, "",  ""),
    ("p_wrap",   "Wrap edges (1 = yes)",    0,   1,   1, "",  ""),
    ("p_inv",    "Invert live/dead (1 = yes)", 0, 1,  0, "",  ""),
]
GEN_ALL_COUNT = 1 + len(GEN_STYLE_SPECS) + len(PROSE_SPECS) + len(SYLL_SPECS) + len(PAT_SPECS)
GEN_STYLE_KEYS = {"gsize", "glh", "gred", "ggreen", "gblue"}
MODE_SALT = {"Prose": 11, "Syllables": 23, "Pattern": 37}

NOUNS = ("river lantern city forest engine window storm thread harbor shadow "
         "garden signal desert compass echo prism valley machine moon fox wire "
         "ocean cave mirror clock key bridge field arrow").split()
ADJECTIVES = ("silent golden broken endless distant electric velvet forgotten "
              "luminous tangled hollow ancient restless crimson narrow frozen "
              "quiet bright patient crooked copper stubborn weightless").split()
VERBS = ("drifts hums unravels remembers dissolves trembles awakens cascades "
         "whispers collapses blooms echoes burns gathers waits turns listens "
         "folds wanders wakes settles glows").split()
ADVERBS = "softly slowly always never gently wildly quietly suddenly endlessly barely elsewhere".split()
CONNECTORS = "and but while because although until yet so".split()
ENDERS = ("again forever tonight somehow at last without a sound one more time").split()
ONSETS = ("b c d f g h k l m n p r s t v w z br cr dr fl gl gr kl pl pr st tr "
          "ch sh th sp sn sw tw sk").split()
CODAS = "n m r l s t d k ng nt st sh th rk lm".split()
VOWELS = "a e i o u ai ea ee oo ou ia io au ei".split()
CHARSETS = (("░", "█"), (" ", "▓"), (" ", "#"), (".", "@"), ("0", "1"), ("·", "*"))

DARK_QSS = """
QWidget { background-color:#23262e; color:#e6e6e6; }
QGroupBox { border:1px solid #3a3f4b; border-radius:8px; margin-top:12px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; color:#8fd0ff; }
QSlider::groove:horizontal { height:5px; background:#3a3f4b; border-radius:2px; }
QPushButton, QToolButton, QComboBox, QLineEdit, QSpinBox {
    background:#2e3340; border:1px solid #3a3f4b; border-radius:5px; padding:5px 10px; }
QPushButton:hover, QToolButton:hover, QComboBox:hover, QLineEdit:hover, QSpinBox:hover {
    border-color:#5a87b8; }
QPushButton:checked, QToolButton:checked { background:#2b5d8f; }
QComboBox QAbstractItemView { background:#2e3340; selection-background-color:#2b5d8f; }
QMenu { background:#2e3340; border:1px solid #3a3f4b; }
QMenu::item:selected { background:#2b5d8f; }
QStatusBar { background:#1c1f26; }
QScrollBar:vertical { background:#23262e; width:10px; }
QScrollBar::handle:vertical { background:#3a3f4b; border-radius:5px; min-height:20px; }
QScrollBar:horizontal { background:#23262e; height:10px; }
QScrollBar::handle:horizontal { background:#3a3f4b; border-radius:5px; min-width:20px; }
QSplitter::handle { background:#3a3f4b; width:2px; }
QTabWidget::pane { border:1px solid #3a3f4b; }
QTabBar::tab { background:#2e3340; padding:6px 18px; border:1px solid #3a3f4b; }
QTabBar::tab:selected { background:#2b5d8f; }
"""


# ---------------------------------------------------------------------------
def style_slider(sl: QSlider, accent: str):
    handle = QColor(accent).lighter(150).name()
    hover = QColor(accent).lighter(185).name()
    sl.setStyleSheet(
        f"QSlider::groove:horizontal {{ height:5px; background:#3a3f4b; border-radius:2px; }}"
        f"QSlider::sub-page:horizontal {{ background:{accent}; border-radius:2px; }}"
        f"QSlider::handle:horizontal {{ width:14px; margin:-6px 0; border-radius:7px; "
        f"background:{handle}; }}"
        f"QSlider::handle:horizontal:hover {{ background:{hover}; }}")


class Sparkline(QWidget):
    def __init__(self, mn, mx, default, accent, parent=None):
        super().__init__(parent)
        self.mn, self.mx, self.default = mn, mx, default
        self.accent = QColor(accent)
        self.hist = deque(maxlen=64)
        self.setFixedSize(56, 16)
        self.setToolTip("Last 64 values — dashed line = default.\n"
                        "Run auto-animate (F5) and watch the wave draw itself.")

    def push(self, v):
        self.hist.append(v)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -2, -2)
        span = max(1, self.mx - self.mn)

        if self.mn <= self.default <= self.mx:
            y = r.bottom() - (self.default - self.mn) / span * r.height()
            p.setPen(QPen(QColor(128, 128, 128, 130), 1, Qt.PenStyle.DashLine))
            p.drawLine(r.left(), int(y), r.right(), int(y))

        if len(self.hist) >= 2:
            pts = QPolygonF()
            n = len(self.hist)
            for i, v in enumerate(self.hist):
                x = r.left() + i / (n - 1) * r.width()
                y = r.bottom() - (v - self.mn) / span * r.height()
                pts.append(QPointF(x, y))
            p.setPen(QPen(self.accent, 1.4))
            p.drawPolyline(pts)
        p.end()


class Collapsible(QFrame):
    def __init__(self, title, accent="", parent=None):
        super().__init__(parent)
        self.title, self.accent, self.badge = title, accent, 0
        self.setFrameShape(QFrame.Shape.NoFrame)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        self.row = QHBoxLayout()
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(2)
        self.fold = QToolButton()
        self.fold.setCheckable(True)
        self.fold.setChecked(True)
        self.fold.setCursor(Qt.CursorShape.PointingHandCursor)
        self.row.addWidget(self.fold, 1)
        v.addLayout(self.row)
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 2, 0, 4)
        self.body_lay.setSpacing(6)
        v.addWidget(self.body)
        self.fold.toggled.connect(self._fold)
        self._anim = QPropertyAnimation(self.body, b"maximumHeight", self)
        self._anim.setDuration(170)
        self._anim.finished.connect(self._anim_done)
        self._refresh_text()

    def add_corner(self, w):
        self.row.addWidget(w)

    def set_badge(self, n):
        if n != self.badge:
            self.badge = n
            self._refresh_text()

    def _refresh_text(self):
        arrow = "▾" if self.fold.isChecked() else "▸"
        b = f"   ·  {self.badge} modified" if self.badge else ""
        self.fold.setText(f"{arrow}  {self.title}{b}")
        color = f"color:{self.accent};" if self.accent else ""
        self.fold.setStyleSheet(
            "QToolButton{border:none;text-align:left;font-weight:600;"
            "padding:3px 2px;" + color + "}")

    def _fold(self, checked):
        self._refresh_text()
        self._anim.stop()
        self._anim.setStartValue(self.body.height())
        self._anim.setEndValue(self.body.sizeHint().height() if checked else 0)
        self._anim.start()

    def _anim_done(self):
        if self.fold.isChecked():
            self.body.setMaximumHeight(16777215)


# ---------------------------------------------------------------------------
class LabeledSlider(QWidget):
    valueChanged = Signal(int)
    resetOne = Signal(object)
    lockChanged = Signal(object)

    def __init__(self, caption, mn, mx, default, suffix="", tip="",
                 accent="#4da3ff", lockable=True, parent=None):
        super().__init__(parent)
        self.caption, self.default, self.suffix = caption, default, suffix
        self.key, self.accent, self.lockable = None, accent, lockable
        self.locked = False
        self._popup = None
        base = (tip + "\n" if tip else "")
        self.setToolTip(base + "Shift+wheel ±1 · Ctrl+wheel ±10 · PgUp/PgDn ±10\n"
                               "double-click / middle-click: reset · right-click: menu")

        self.caption_label = QLabel(caption)
        self.spark = Sparkline(mn, mx, default, accent)
        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setMinimumWidth(64)
        self.value_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.value_label.setToolTip("Double-click to type an exact value")

        top = QHBoxLayout()
        top.addWidget(self.caption_label)
        top.addStretch(1)
        top.addWidget(self.spark)
        top.addWidget(self.value_label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(mn, mx)
        self.slider.setValue(default)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(10)
        self.slider.valueChanged.connect(self._changed)
        self.slider.installEventFilter(self)
        self.value_label.installEventFilter(self)
        style_slider(self.slider, accent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(0)
        lay.addLayout(top)
        lay.addWidget(self.slider)
        self._update_label(default)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if obj is self.slider:
            if t == QEvent.Type.MouseButtonDblClick:
                self.resetOne.emit(self)
                return True
            if t == QEvent.Type.MouseButtonPress and \
                    ev.button() == Qt.MouseButton.MiddleButton:
                self.resetOne.emit(self)
                return True
            if t == QEvent.Type.ContextMenu:
                self._menu()
                return True
            if t == QEvent.Type.Wheel:
                m = ev.modifiers()
                if m & (Qt.KeyboardModifier.ControlModifier |
                        Qt.KeyboardModifier.ShiftModifier):
                    d = 1 if ev.angleDelta().y() > 0 else -1
                    step = 10 if m & Qt.KeyboardModifier.ControlModifier else 1
                    self.slider.setValue(self.slider.value() + d * step)
                    return True
        elif obj is self.value_label and t == QEvent.Type.MouseButtonDblClick:
            self._edit_value()
            return True
        return super().eventFilter(obj, ev)

    def contextMenuEvent(self, e):
        self._menu()

    def mouseDoubleClickEvent(self, event):
        self.resetOne.emit(self)
        super().mouseDoubleClickEvent(event)

    def _menu(self):
        m = QMenu(self)
        m.addAction("↺  Reset to default", lambda: self.resetOne.emit(self))
        m.addAction("⌨  Set exact value…", self._edit_value)
        m.addAction("⧉  Copy value",
                    lambda: QApplication.clipboard().setText(str(self.slider.value())))
        m.addAction("🎲  Randomize this slider", self._randomize)
        if self.lockable:
            m.addSeparator()
            m.addAction("🔓  Unlock" if self.locked else "🔒  Lock", self._toggle_lock)
        m.exec(QCursor.pos())

    def _randomize(self):
        self.slider.setValue(random.randint(self.slider.minimum(), self.slider.maximum()))

    def _toggle_lock(self):
        self.locked = not self.locked
        self.caption_label.setText(("🔒 " if self.locked else "") + self.caption)
        self.lockChanged.emit(self)

    def _edit_value(self):
        if self._popup is not None:
            self._popup.close()
            self._popup = None
        pop = QFrame(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        pop.setStyleSheet("QFrame { background: palette(window); "
                          "border:1px solid palette(mid); border-radius:6px; }")
        lay = QVBoxLayout(pop)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        t = QLabel(self.caption)
        t.setStyleSheet("font-weight:600; border:none;")
        spin = QSpinBox()
        spin.setRange(self.slider.minimum(), self.slider.maximum())
        spin.setValue(self.slider.value())
        spin.setAccelerated(True)
        hint = QLabel("typing previews live · Enter / Esc closes")
        hint.setStyleSheet("color:#888; border:none;")
        lay.addWidget(t)
        lay.addWidget(spin)
        lay.addWidget(hint)
        pop.setFixedWidth(180)
        spin.valueChanged.connect(self.slider.setValue)
        spin.editingFinished.connect(pop.close)
        self._popup = pop
        pop.move(self.value_label.mapToGlobal(QPoint(0, self.value_label.height() + 2)))
        pop.show()
        spin.setFocus()
        spin.selectAll()

    def _update_label(self, v):
        self.value_label.setText(f"{v}{self.suffix}")
        mod = v != self.default
        self.value_label.setStyleSheet(
            f"color:{'#ffb454' if mod else '#35d68f'}; font-weight:bold;")

    def _changed(self, v):
        self._update_label(v)
        self.spark.push(v)
        self.valueChanged.emit(v)

    def set_value_silent(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(v)
        self.slider.blockSignals(False)
        self._update_label(v)
        self.spark.push(v)

    def set_highlight(self, on):
        self.caption_label.setStyleSheet(
            f"font-weight:700; color:{self.accent};" if on else "")


class PreviewView(QGraphicsView):
    zoomRequested = Signal(int)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoomRequested.emit(6 if e.angleDelta().y() > 0 else -6)
            e.accept()
            return
        super().wheelEvent(e)


# ---------------------------------------------------------------------------
class Animator(QObject):
    """tween: eased glide to a target. wave: continuous sine auto-animate."""
    values = Signal(dict)
    stateChanged = Signal(str)
    finished = Signal()

    def __init__(self, sliders):
        super().__init__()
        self.sliders = sliders
        self.mode = ""
        self.speed = 1.0
        self.sweep = 0.6
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def is_running(self):
        return bool(self.mode)

    def set_speed(self, s):
        self.speed = max(0.05, float(s))

    def set_sweep(self, s):
        self.sweep = min(1.0, max(0.05, float(s)))

    def stop(self, commit=True):
        if not self.mode:
            return
        self.mode = ""
        self.timer.stop()
        self.stateChanged.emit("")
        if commit:
            self.finished.emit()

    def start_tween(self, target, duration=900, easing="Out Cubic"):
        self.stop()
        self.mode = "tween"
        self.t0 = time.monotonic()
        self.duration = max(0.05, duration / 1000.0)
        self.curve = QEasingCurve(EASINGS.get(easing, QEasingCurve.Type.OutCubic))
        self.start_vals = {k: s.slider.value() for k, s in self.sliders.items()}
        self.target = {k: int(v) for k, v in target.items() if k in self.sliders}
        self.stateChanged.emit("tween")
        self.timer.start()

    def start_wave(self, params):
        self.stop()
        if not params:
            return
        self.mode = "wave"
        self.params = params
        self.tanim = 0.0
        self.last = time.monotonic()
        self.stateChanged.emit("wave")
        self.timer.start()

    def _tick(self):
        if self.mode == "tween":
            t = (time.monotonic() - self.t0) / self.duration
            p = self.curve.valueForProgress(min(1.0, t))
            vals = {}
            for k, a in self.start_vals.items():
                b = self.target.get(k, a)
                vals[k] = int(round(a + (b - a) * p))
            self.values.emit(vals)
            if t >= 1.0:
                self.stop()
        elif self.mode == "wave":
            now = time.monotonic()
            dt = min(0.1, now - self.last)
            self.last = now
            self.tanim += dt * self.speed
            ramp = min(1.0, self.tanim / 0.8)
            vals = {}
            for k, (c, mn, mx, f, ph) in self.params.items():
                if self.sliders[k].slider.isSliderDown():
                    continue
                amp = (mx - mn) / 2 * self.sweep
                v = c + amp * ramp * math.sin(2 * math.pi * f * self.tanim + ph)
                vals[k] = int(round(max(mn, min(mx, v))))
            self.values.emit(vals)


# ---------------------------------------------------------------------------
class TextFX(QObject):
    """
    Animated text transitions for the Generate preview.

    Instead of snapping new generated text into place, the preview fills
    with scrambled characters that resolve into the target. Spaces and
    newlines hold their positions so layout never jumps. Scramble charset
    adapts to the engine (block glyphs for Pattern, letters for prose).

    Modes: Instant · Decode · Typewriter · Wave · Cascade
    """
    MODES = ("Instant", "Decode", "Typewriter", "Wave", "Cascade")
    SCRAMBLE = {
        "Prose":     "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLM"
                     "NOPQRSTUVWXYZ.,;",
        "Syllables": "abcdefghijklmnopqrstuvwxyz",
        "Pattern":   "░▒▓█#@*·01",
    }
    LIMIT = 30_000          # above this, set instantly (perf guard)
    STEP = 0.033            # nominal seconds per tick

    def __init__(self, edit: QTextEdit):
        super().__init__(edit)
        self.edit = edit
        self.fx = "Decode"
        self.speed = 1.0
        self._target = ""
        self._slots = []
        self._t = 0.0
        self._dur = 0.55        # seconds for a full reveal at speed 1.0
        self._tickn = 0
        self._kind = "Prose"
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def set_fx(self, name):
        self.fx = name if name in self.MODES else "Decode"

    def set_speed(self, s):
        self.speed = min(3.0, max(0.2, float(s)))

    @staticmethod
    def _h(i, salt):
        return ((i + 1) * 2654435761 + salt * 40503) % 99991 / 99991.0

    # ------------------------------------------------------------ public
    def show(self, text: str, kind: str):
        self._kind = kind
        if (self.fx == "Instant" or len(text) < 2 or len(text) > self.LIMIT
                or not self.edit.isVisible()):
            self.timer.stop()
            self._set_text(text)
            return
        self._target = text
        self._slots = self._build_slots(text)
        self._t = 0.0
        self._tickn = 0
        self.timer.start()
        self._tick()

    def stop(self):
        self.timer.stop()

    # ------------------------------------------------------------ internals
    def _build_slots(self, text):
        """Per-character reveal time in [0, 1), ordered by the chosen FX."""
        n = len(text)
        if self.fx == "Typewriter":
            return [i / n for i in range(n)]
        if self.fx == "Wave":
            mid = max(1.0, n / 2)
            return [min(0.95, abs(i - mid) / mid * 0.9 + self._h(i, 3) * 0.1)
                    for i in range(n)]
        if self.fx == "Cascade":
            bounds = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]
            if bounds[-1] != n:
                bounds.append(n)
            slots = [0.0] * n
            nl = len(bounds) - 1
            for li in range(nl):
                a, b = bounds[li], bounds[li + 1]
                base = li / max(1, nl)
                for i in range(a, b):
                    f = (i - a) / max(1, b - a)
                    slots[i] = min(0.98, base * 0.6 + f * 0.4)
            return slots
        # Decode: mostly left-to-right with jitter
        return [(i / n) * 0.65 + self._h(i, 11) * 0.35 for i in range(n)]

    def _scr(self, i):
        table = self.SCRAMBLE.get(self._kind, self.SCRAMBLE["Prose"])
        return table[int(self._h(i, self._tickn * 7 + 1) * len(table)) % len(table)]

    def _tick(self):
        self._t += self.STEP * self.speed / self._dur
        self._tickn += 1
        if self._t >= 1.0:
            self.timer.stop()
            self._set_text(self._target)
            return
        t = self._t
        tgt, slots = self._target, self._slots
        typewriter = self.fx == "Typewriter"
        out = []
        for i, ch in enumerate(tgt):
            if t >= slots[i]:
                out.append(ch)
            elif typewriter:
                out.append("")
            elif ch in "\n ":
                out.append(ch)          # hold layout stable
            else:
                out.append(self._scr(i))
        self._set_text("".join(out))

    def _set_text(self, s):
        sb = self.edit.verticalScrollBar()
        v = sb.value()
        self.edit.setPlainText(s)
        sb.setValue(v)


# ---------------------------------------------------------------------------
class TextStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_path = None
        self.raw_text = SAMPLE_TEXT
        self.transformed = ""
        self.generated = ""
        self.sliders = {}
        self.gsliders = {}
        self.groups = {}
        self.gen_groups = {}
        self._undo, self._redo = [], []
        self._committed = dict(DEFAULTS)
        self._compare = False
        self.stateA = None
        self.stateB = None
        self.base_family = QApplication.font().family()
        self.user_presets = self._load_user_presets()

        self.setWindowTitle(f"Slider Text Studio ({len(SLIDER_SPECS) + GEN_ALL_COUNT} sliders)")
        self.resize(1350, 820)
        self.setAcceptDrops(True)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.refresh)

        self.gen_timer = QTimer(self)
        self.gen_timer.setSingleShot(True)
        self.gen_timer.setInterval(60)
        self.gen_timer.timeout.connect(self.gen_refresh)

        self._build_menus()
        self._build_tabs()

        # one animator per tab; F5 routes to the visible tab
        self.animator = Animator(self.sliders)
        self.animator.values.connect(self._apply_animated)
        self.animator.finished.connect(self._checkpoint)
        self.animator.stateChanged.connect(self._on_anim_state)

        self.gen_animator = Animator(self.gsliders)
        self.gen_animator.values.connect(self._apply_gen_animated)
        self.gen_animator.stateChanged.connect(self._on_gen_anim_state)

        # evolve: seed ticks forward, text mutates forever
        self.evolve_timer = QTimer(self)
        self.evolve_timer.timeout.connect(self._evolve_step)

        QShortcut(QKeySequence("F5"), self, self._f5_route)

        self._repopulate_presets(select="Factory reset")
        self._gen_mode_changed(self.gen_combo.currentText())
        if self._restore_session():
            self.statusBar().showMessage(
                "Previous session restored (slider values + theme).", 5000)
        self.refresh()
        self.gen_refresh()
        self.view.centerOn(self._content_rect().center())

    # ================================================================ menus
    def _build_menus(self):
        m = self.menuBar().addMenu("&File")
        self._act(m, "📂 &Open…", QKeySequence.StandardKey.Open, self.open_file)
        self._act(m, "💾 &Save", QKeySequence.StandardKey.Save, self.save_file)
        self._act(m, "Save &As…", "Ctrl+Shift+S", self.save_file_as)
        m.addSeparator()
        self._act(m, "⧉ &Copy result", "Ctrl+Shift+C", self.copy_text)
        self._act(m, "🖼 Export &PNG…", "Ctrl+E", self.export_png)
        self._act(m, "🎞 Export &frames…", "Ctrl+Shift+E", self.export_frames)
        m.addSeparator()
        self.autosave_act = QAction("&Auto-save to file", self, checkable=True)
        m.addAction(self.autosave_act)
        m.addSeparator()
        self._act(m, "E&xit", QKeySequence.StandardKey.Quit, self.close)

        m = self.menuBar().addMenu("&Edit")
        a = self._act(m, "↶ &Undo", QKeySequence.StandardKey.Undo, self.undo)
        a.setShortcuts([QKeySequence.StandardKey.Undo, QKeySequence("Ctrl+Y")])
        self._act(m, "↷ &Redo", QKeySequence.StandardKey.Redo, self.redo)
        m.addSeparator()
        self._act(m, "🎲 &Randomize all", "Ctrl+R", self.randomize_all)
        self._act(m, "↺ Reset &all", "Ctrl+0", self.reset_all)
        self._act(m, "🔓 &Unlock all sliders", "Ctrl+L", self.unlock_all)
        self._act(m, "🎲 New &generate seed", "F6", self._gen_new_seed)

        m = self.menuBar().addMenu("&View")
        self.dark_act = QAction("&Dark theme", self, checkable=True, shortcut="Ctrl+D")
        self.dark_act.toggled.connect(
            lambda on: QApplication.instance().setStyleSheet(DARK_QSS if on else ""))
        m.addAction(self.dark_act)
        self.transitions_act = QAction("&Animated transitions", self,
                                      checkable=True, shortcut="Ctrl+T")
        self.transitions_act.setChecked(True)
        self.transitions_act.setToolTip("Presets and resets morph smoothly instead of snapping")
        m.addAction(self.transitions_act)
        self._act(m, "⌖ &Center preview", "Ctrl+G",
                  lambda: self.view.centerOn(self._content_rect().center()))

    @staticmethod
    def _act(menu, text, key, slot):
        a = QAction(text, menu)
        if key:
            a.setShortcut(key)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    # ================================================================== tabs
    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_transform_tab(), "🔀  Transform")
        self.tabs.addTab(self._build_generate_tab(), "✨  Generate")
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tabs)
        self.setCentralWidget(wrap)

    # ================================================== TAB 1: transform UI
    def _build_transform_tab(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        bar1 = QHBoxLayout()
        for text, slot, tip in (
            ("📂 Open", self.open_file, "Open a text file (or drag & drop it here)"),
            ("💾 Save", self.save_file, "Write the transformed text to the current file"),
            ("Save As…", self.save_file_as, ""),
            ("⧉ Copy", self.copy_text, "Copy the transformed text to the clipboard"),
            ("🖼 PNG", self.export_png, "Export the preview as a PNG image"),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            bar1.addWidget(b)

        self.autosave_btn = QToolButton()
        self.autosave_btn.setText("⏏ Auto-save")
        self.autosave_btn.setCheckable(True)
        self.autosave_btn.setToolTip("Rewrite the file automatically on every slider change")
        bar1.addWidget(self.autosave_btn)
        bar1.addStretch(1)
        root.addLayout(bar1)

        bar2 = QHBoxLayout()
        bar2.addWidget(QLabel("Presets:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        bar2.addWidget(self.preset_combo)
        for text, slot, tip in (
            ("➕", self._save_preset, "Save current slider values as a preset"),
            ("🗑", self._delete_preset, "Delete the selected user preset"),
        ):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            bar2.addWidget(b)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("🔍 filter sliders…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMaximumWidth(200)
        self.filter_edit.textChanged.connect(self._filter_sliders)
        self.filter_edit.setToolTip("Filter sliders — also limits which ones auto-animate.\n"
                                    "Matches light up in the group colour.")
        bar2.addWidget(self.filter_edit)

        self.mod_btn = QToolButton()
        self.mod_btn.setText("◐ Modified")
        self.mod_btn.setCheckable(True)
        self.mod_btn.setToolTip("Show only sliders whose value differs from default")
        self.mod_btn.toggled.connect(
            lambda _: self._filter_sliders(self.filter_edit.text()))
        bar2.addWidget(self.mod_btn)
        bar2.addStretch(1)

        rnd = QPushButton("🎲 Randomize")
        rnd.setShortcut("Ctrl+R")
        rnd.setToolTip("Randomize all sliders — locked ones are skipped")
        rnd.clicked.connect(self.randomize_all)
        rst = QPushButton("↺ Reset all")
        rst.setShortcut("Ctrl+0")
        rst.clicked.connect(self.reset_all)
        bar2.addWidget(rnd)
        bar2.addWidget(rst)
        root.addLayout(bar2)

        # --- A/B crossfade master row --------------------------------------
        row3 = QHBoxLayout()
        t = QLabel("⇄  A/B crossfade")
        t.setStyleSheet("font-weight:600;")
        row3.addWidget(t)
        self.btn_a = QPushButton("Set A")
        self.btn_a.setToolTip("Capture the current slider values as state A")
        self.btn_a.clicked.connect(self._capture_a)
        self.btn_b = QPushButton("Set B")
        self.btn_b.setToolTip("Capture the current slider values as state B")
        self.btn_b.clicked.connect(self._capture_b)
        self.play_ab = QPushButton("▶ A→B")
        self.play_ab.setToolTip("Play the whole A→B morph with the chosen easing curve")
        self.play_ab.clicked.connect(self._play_blend)
        self.blend_slider = QSlider(Qt.Orientation.Horizontal)
        self.blend_slider.setRange(0, 100)
        self.blend_slider.setValue(50)
        self.blend_slider.setMaximumWidth(300)
        style_slider(self.blend_slider, GEN_ACCENTS["blend"])
        self.blend_slider.setSingleStep(1)
        self.blend_slider.setPageStep(10)
        self.blend_slider.valueChanged.connect(self._blend_changed)
        self.blend_slider.sliderPressed.connect(
            lambda: self.animator.stop(commit=False))
        self.blend_slider.sliderReleased.connect(self._checkpoint)
        self.blend_label = QLabel("—")
        self.blend_label.setToolTip("Drag to blend between the two captured states")
        for w in (self.btn_a, self.btn_b, self.play_ab):
            row3.addWidget(w)
        row3.addWidget(self.blend_slider, 1)
        row3.addWidget(self.blend_label)
        root.addLayout(row3)

        # --- animation row --------------------------------------------------
        anim = QHBoxLayout()
        self.animate_btn = QToolButton()
        self.animate_btn.setText("⏵ Animate")
        self.animate_btn.setCheckable(True)
        self.animate_btn.setToolTip(
            "Auto-animate the Transform sliders (F5 when this tab is active).\n"
            "Use the filter box to animate just a subset.")
        self.animate_btn.toggled.connect(self._toggle_wave)
        anim.addWidget(self.animate_btn)

        anim.addWidget(QLabel("Speed"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(20, 300)
        self.speed_slider.setValue(100)
        self.speed_slider.setMaximumWidth(130)
        style_slider(self.speed_slider, ACCENTS["font"])
        self.speed_slider.valueChanged.connect(self._speed_changed)
        self.speed_label = QLabel("x1.00")
        anim.addWidget(self.speed_slider)
        anim.addWidget(self.speed_label)

        anim.addWidget(QLabel("Sweep"))
        self.sweep_slider = QSlider(Qt.Orientation.Horizontal)
        self.sweep_slider.setRange(10, 100)
        self.sweep_slider.setValue(60)
        self.sweep_slider.setMaximumWidth(130)
        style_slider(self.sweep_slider, ACCENTS["effect"])
        self.sweep_slider.valueChanged.connect(self._sweep_changed)
        self.sweep_label = QLabel("60%")
        self.sweep_slider.setToolTip("How far the sliders swing each cycle")
        anim.addWidget(self.sweep_slider)
        anim.addWidget(self.sweep_label)

        anim.addWidget(QLabel("Easing"))
        self.easing_combo = QComboBox()
        self.easing_combo.addItems(EASINGS)
        self.easing_combo.setCurrentText("Out Cubic")
        self.easing_combo.setToolTip("Easing for preset morphs, ▶ A→B and animated seed rolls")
        anim.addWidget(self.easing_combo)

        frames_btn = QToolButton()
        frames_btn.setText("🎞 Frames")
        frames_btn.setToolTip("Export one full animation cycle as numbered PNG frames")
        frames_btn.clicked.connect(self.export_frames)
        anim.addWidget(frames_btn)
        anim.addStretch(1)
        root.addLayout(anim)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._make_slider_panel())
        splitter.addWidget(self._make_preview())
        splitter.setSizes([390, 960])
        root.addWidget(splitter, 1)

        self.file_label = QLabel("(new unsaved text — use Save As)")
        self.stats_label = QLabel()
        self.mod_label = QLabel()
        self.statusBar().addPermanentWidget(self.mod_label)
        self.statusBar().addPermanentWidget(self.file_label)
        self.statusBar().addPermanentWidget(self.stats_label)
        self.statusBar().showMessage(
            "F5 animates the active tab · right-click sliders for menus · F6 rolls the seed.")
        return central

    def _make_slider_panel(self):
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setSpacing(8)

        for key in GROUP_ORDER:
            sec = Collapsible(GROUP_TITLES[key], ACCENTS[key])
            dice = QToolButton()
            dice.setText("🎲")
            dice.setToolTip(f"Randomize the {key} sliders (locked ones are skipped)")
            dice.clicked.connect(lambda _, k=key: self.randomize_group(k))
            sec.add_corner(dice)
            outer.addWidget(sec)
            self.groups[key] = {"sec": sec, "body": sec.body_lay, "sliders": []}

        for key, grp, caption, mn, mx, df, suffix, tip in SLIDER_SPECS:
            s = LabeledSlider(caption, mn, mx, df, suffix, tip,
                              ACCENTS[grp], lockable=True)
            s.key = key
            s.valueChanged.connect(self._schedule_refresh)
            s.slider.sliderReleased.connect(self._checkpoint)
            s.slider.sliderPressed.connect(self._cancel_tween)
            s.resetOne.connect(self._reset_one)
            s.lockChanged.connect(self._lock_changed)
            self.groups[grp]["body"].addWidget(s)
            self.groups[grp]["sliders"].append(s)
            self.sliders[key] = s

        self.swatch = QFrame()
        self.swatch.setFixedHeight(16)
        self.groups["colour"]["body"].addWidget(self.swatch)

        outer.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(390)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    def _make_preview(self):
        holder = QWidget()
        v = QVBoxLayout(holder)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        bar = QHBoxLayout()
        self.wrap_btn = QToolButton()
        self.wrap_btn.setText("Wrap")
        self.wrap_btn.setCheckable(True)
        self.wrap_btn.setChecked(True)
        self.wrap_btn.toggled.connect(lambda _: self.refresh())
        self.mono_btn = QToolButton()
        self.mono_btn.setText("Monospace")
        self.mono_btn.setCheckable(True)
        self.mono_btn.setChecked(True)
        self.mono_btn.toggled.connect(lambda _: self.refresh())
        center_btn = QToolButton()
        center_btn.setText("⌖ Center")
        center_btn.clicked.connect(
            lambda: self.view.centerOn(self._content_rect().center()))
        self.compare_btn = QPushButton("👁 Hold: original")
        self.compare_btn.setToolTip("Press and hold to see the untransformed text")
        self.compare_btn.pressed.connect(self._compare_on)
        self.compare_btn.released.connect(self._compare_off)
        for wdg in (self.wrap_btn, self.mono_btn, center_btn, self.compare_btn):
            bar.addWidget(wdg)
        bar.addStretch(1)
        v.addLayout(bar)

        self.scene = QGraphicsScene(self)
        self.glow_item = QGraphicsTextItem()
        self.text_item = QGraphicsTextItem()
        self.glow_item.setZValue(-1)
        self.glow_item.hide()
        self.scene.addItem(self.glow_item)
        self.scene.addItem(self.text_item)
        self.glow_item.setGraphicsEffect(QGraphicsDropShadowEffect(self.glow_item))

        self.view = PreviewView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.zoomRequested.connect(self._ctrl_wheel_zoom)
        v.addWidget(self.view, 1)
        return holder

    # ================================================== TAB 2: generate UI
    def _build_generate_tab(self):
        page = QWidget()
        h = QVBoxLayout(page)
        h.setContentsMargins(6, 6, 6, 6)
        h.setSpacing(4)

        # --- animation row (NEW in 6.0) --------------------------------------
        arow = QHBoxLayout()
        self.gen_animate_btn = QToolButton()
        self.gen_animate_btn.setText("⏵ Animate")
        self.gen_animate_btn.setCheckable(True)
        self.gen_animate_btn.setToolTip(
            "Auto-animate the visible Generate sliders (F5 when this tab is active).\n"
            "Prose rewrites itself, patterns boil, words churn.")
        self.gen_animate_btn.toggled.connect(self._toggle_gen_wave)
        arow.addWidget(self.gen_animate_btn)

        self.evolve_btn = QToolButton()
        self.evolve_btn.setText("🔁 Evolve")
        self.evolve_btn.setCheckable(True)
        self.evolve_btn.setToolTip(
            "Tick the seed forward continuously — the text mutates forever.\n"
            "Rate follows the Speed slider.")
        self.evolve_btn.toggled.connect(self._toggle_evolve)
        arow.addWidget(self.evolve_btn)

        arow.addWidget(QLabel("Speed"))
        self.gen_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.gen_speed_slider.setRange(20, 300)
        self.gen_speed_slider.setValue(100)
        self.gen_speed_slider.setMaximumWidth(140)
        style_slider(self.gen_speed_slider, GEN_ACCENTS["seed"])
        self.gen_speed_slider.setToolTip(
            "One dial for everything: wave speed · evolve rate · FX speed")
        self.gen_speed_slider.valueChanged.connect(self._gen_speed_changed)
        self.gen_speed_label = QLabel("x1.00")
        arow.addWidget(self.gen_speed_slider)
        arow.addWidget(self.gen_speed_label)

        arow.addWidget(QLabel("Text FX"))
        self.gen_fx_combo = QComboBox()
        self.gen_fx_combo.addItems(TextFX.MODES)
        self.gen_fx_combo.setCurrentText("Decode")
        self.gen_fx_combo.setToolTip(
            "How new generated text appears: scrambled chars resolve into place.\n"
            "The scramble alphabet adapts to the engine (blocks for Pattern).")
        self.gen_fx_combo.currentTextChanged.connect(
            lambda m: self.textfx.set_fx(m))
        arow.addWidget(self.gen_fx_combo)
        arow.addStretch(1)
        h.addLayout(arow)

        # --- splitter: sliders | preview -------------------------------------
        split = QSplitter(Qt.Orientation.Horizontal)

        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setSpacing(8)

        intro = QLabel(
            "These sliders WRITE text from nothing. Same seed = stable while you "
            "drag; 🎲 / F6 rolls a new one — animated. Evolve keeps mutating it. "
            "Send the result to the Transform tab to mangle and save it.")
        intro.setWordWrap(True)
        pv.addWidget(intro)

        row = QHBoxLayout()
        row.addWidget(QLabel("Mode:"))
        self.gen_combo = QComboBox()
        self.gen_combo.addItems(list(MODE_SALT))
        self.gen_combo.currentTextChanged.connect(self._gen_mode_changed)
        row.addWidget(self.gen_combo)
        row.addStretch(1)
        pv.addLayout(row)

        seed_sl = LabeledSlider(GEN_SEED_SPEC[1], GEN_SEED_SPEC[2], GEN_SEED_SPEC[3],
                                GEN_SEED_SPEC[4], GEN_SEED_SPEC[5], GEN_SEED_SPEC[6],
                                GEN_ACCENTS["seed"], lockable=False)
        seed_sl.valueChanged.connect(self._schedule_gen)
        seed_sl.resetOne.connect(self._gen_reset_one)
        srow = QHBoxLayout()
        srow.addWidget(seed_sl, 1)
        dice = QToolButton()
        dice.setText("🎲")
        dice.setToolTip("Roll a new seed — animated (F6)")
        dice.clicked.connect(self._gen_new_seed)
        srow.addWidget(dice)
        pv.addLayout(srow)

        for key, title in (("style",    "Style — preview only"),
                           ("Prose",    "Prose — story machine"),
                           ("Syllables","Syllables — invented words"),
                           ("Pattern",  "Pattern — cellular automaton")):
            sec = Collapsible(title, GEN_ACCENTS[key])
            pv.addWidget(sec)
            self.gen_groups[key] = sec

        self.gsliders["gseed"] = seed_sl

        def group_of(k):
            return ("style" if k in GEN_STYLE_KEYS
                    else "Prose" if k.startswith("g_")
                    else "Syllables" if k.startswith("s_")
                    else "Pattern")

        for spec in GEN_STYLE_SPECS + PROSE_SPECS + SYLL_SPECS + PAT_SPECS:
            key, cap, mn, mx, df, suf, tip = spec
            gname = group_of(key)
            s = LabeledSlider(cap, mn, mx, df, suf, tip,
                              GEN_ACCENTS[gname], lockable=False)
            s.valueChanged.connect(self._schedule_gen)
            s.resetOne.connect(self._gen_reset_one)
            self.gen_groups[gname].body_lay.addWidget(s)
            self.gsliders[key] = s

        self.gswatch = QFrame()
        self.gswatch.setFixedHeight(14)
        self.gen_groups["style"].body_lay.addWidget(self.gswatch)

        pv.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(390)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        split.addWidget(scroll)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(4)
        bar = QHBoxLayout()
        for text, slot, tip in (
            ("→ Send to Transform", self.gen_send,
             "Load the generated text into the Transform tab as raw text"),
            ("⧉ Copy", self.gen_copy, "Copy the generated text to the clipboard"),
            ("💾 Save As…", self.gen_save_as, "Save the generated text to a .txt file"),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch(1)
        rv.addLayout(bar)

        self.gen_preview = QTextEdit()
        self.gen_preview.setReadOnly(True)
        self.gen_preview.setPlaceholderText("Generated text appears here…")
        rv.addWidget(self.gen_preview, 1)
        self.gen_stats = QLabel()
        rv.addWidget(self.gen_stats)
        split.addWidget(right, 1)
        h.addWidget(split, 1)

        self.textfx = TextFX(self.gen_preview)
        return page

    # ================================================== content transforms
    @staticmethod
    def _h(i, salt):
        return ((i + 1) * 2654435761 + salt * 40503) % 99991 / 99991.0

    def transform_text(self, raw: str) -> str:
        s, text = self.sliders, raw

        if (v := s["trimstart"].value()):
            text = text[int(len(text) * v / 100):]
        if (v := s["trim"].value()) < 100:
            text = text[:max(1, int(len(text) * v / 100))]

        if (nth := s["drop"].value()) >= 2:
            out, count = [], 0
            for ch in text:
                if ch == "\n":
                    out.append(ch)
                    continue
                count += 1
                if count % nth:
                    out.append(ch)
            text = "".join(out)

        if (up := s["upper"].value()):
            idx = [i for i, ch in enumerate(text) if ch.isalpha()]
            chars = list(text)
            for i in idx[: int(len(idx) * up / 100)]:
                chars[i] = chars[i].upper()
            text = "".join(chars)

        if (p := s["sponge"].value() / 100):
            text = "".join(
                ch.upper() if ch.isalpha() and self._h(i, 7) < p else ch.lower()
                for i, ch in enumerate(text))

        if (p := s["leet"].value() / 100):
            text = "".join(
                LEET[ch.lower()] if ch.lower() in LEET and self._h(i, 13) < p else ch
                for i, ch in enumerate(text))

        if (p := s["vowel"].value() / 100):
            text = "".join(ch for i, ch in enumerate(text)
                           if ch == "\n" or ch.lower() not in "aeiou" or self._h(i, 21) >= p)

        if (p := s["noise"].value() / 100):
            out = []
            for i, ch in enumerate(text):
                out.append(ch)
                if ch != "\n" and self._h(i, 33) < p:
                    out.append(NOISE[int(self._h(i, 44) * len(NOISE)) % len(NOISE)])
            text = "".join(out)

        if (g := s["gap"].value()):
            text = "\n".join((" " * g).join(list(ln)) for ln in text.split("\n"))
        if (wg := s["wgap"].value()):
            text = text.replace(" ", " " * (1 + wg))
        if (wpl := s["wpl"].value()) >= 1:
            words = text.split()
            text = "\n".join(" ".join(words[i:i + wpl])
                             for i in range(0, len(words), wpl))
        if (b := s["blank"].value()):
            text = ("\n" * (b + 1)).join(text.split("\n"))
        if (ind := s["indent"].value()):
            pad = " " * ind
            text = "\n".join(pad + ln if ln else ln for ln in text.split("\n"))
        if (w := s["number"].value()):
            text = "\n".join(f"{i + 1:0{w}d}  {ln}"
                             for i, ln in enumerate(text.split("\n")))

        lines = text.split("\n")
        if (v := s["sort"].value()):
            k = int(len(lines) * v / 100)
            lines[:k] = sorted(lines[:k])
        if (v := s["reverse"].value()):
            k = int(len(lines) * v / 100)
            lines[:k] = lines[:k][::-1]
        if (v := s["shuffle"].value()):
            rng = random.Random(0xC0FFEE)
            k = int(len(lines) * v / 100)
            for i in range(k):
                wds = lines[i].split(" ")
                rng.shuffle(wds)
                lines[i] = " ".join(wds)
        text = "\n".join(lines)

        if (rep := s["repeat"].value()) > 1:
            text = "\n\n".join([text] * rep)

        return text[:MAX_CHARS]

    # ==================================================== display / preview
    def _paint_item(self, item, text, cfmt, bfmt, font):
        doc = item.document()
        doc.setDefaultFont(font)
        doc.setPlainText(text)
        cur = QTextCursor(doc)
        cur.select(QTextCursor.SelectionType.Document)
        cur.mergeCharFormat(cfmt)
        cur.mergeBlockFormat(bfmt)

    def apply_display(self, text: str):
        s = self.sliders
        sv = sb = 0
        if hasattr(self, "view"):
            sv, sb = (self.view.verticalScrollBar().value(),
                      self.view.horizontalScrollBar().value())

        font = QFont("Consolas" if self.mono_btn.isChecked() else self.base_family)
        if self.mono_btn.isChecked():
            font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(s["size"].value())
        font.setWeight(s["weight"].value())
        font.setStretch(s["stretch"].value())
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,
                              float(s["lspace"].value()))

        colour = QColor(s["red"].value(), s["green"].value(), s["blue"].value())
        colour.setAlpha(int(s["opacity"].value() * 255 / 100))

        cfmt = QTextCharFormat()
        cfmt.setFont(font)
        cfmt.setForeground(colour)
        if hasattr(cfmt, "setFontWordSpacing"):
            cfmt.setFontWordSpacing(float(s["wspace"].value()))

        bfmt = QTextBlockFormat()
        try:
            lh = int(QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        except Exception:
            lh = 1
        bfmt.setLineHeight(float(s["lineh"].value()), lh)

        wrap_w = WRAP_WIDTH if self.wrap_btn.isChecked() else -1
        self.text_item.setTextWidth(wrap_w)
        self.glow_item.setTextWidth(wrap_w)
        self._paint_item(self.text_item, text, cfmt, bfmt, font)

        glow = s["glow"].value()
        if glow:
            self.glow_item.show()
            self._paint_item(self.glow_item, text, cfmt, bfmt, font)
            eff = self.glow_item.graphicsEffect()
            eff.setBlurRadius(float(glow))
            off = s["shadowoff"].value()
            eff.setOffset(float(off), float(off))
            sc = QColor(s["red"].value(), s["green"].value(), s["blue"].value())
            sc.setAlpha(200)
            eff.setColor(sc)
        else:
            self.glow_item.hide()

        blur = s["blur"].value()
        if blur:
            eff = self.text_item.graphicsEffect()
            if not isinstance(eff, QGraphicsBlurEffect):
                eff = QGraphicsBlurEffect(self.text_item)
                self.text_item.setGraphicsEffect(eff)
            eff.setBlurRadius(float(blur))
        else:
            self.text_item.setGraphicsEffect(None)

        t = QTransform()
        t.rotate(float(s["rotation"].value()))
        z = s["zoom"].value() / 100
        t.scale(z, z)
        t.shear(s["skew"].value() / 100, 0)
        self.text_item.setTransform(t)
        self.glow_item.setTransform(t)

        bg = QColor.fromHsl(s["bg_hue"].value(),
                            int(s["bg_sat"].value() * 2.55),
                            int(s["bg_bright"].value() * 2.55))
        self.scene.setBackgroundBrush(bg)
        self.view.setBackgroundBrush(bg)
        self.view.setStyleSheet(f"QGraphicsView {{ background:{bg.name()}; border:none; }}")

        rect = self._content_rect()
        self.scene.setSceneRect(rect.adjusted(-300, -300, 300, 300))
        self.view.verticalScrollBar().setValue(sv)
        self.view.horizontalScrollBar().setValue(sb)

        self.swatch.setStyleSheet(
            f"background-color: rgb({s['red'].value()},{s['green'].value()},{s['blue'].value()});"
            f"border: 1px solid #888;")

    def _content_rect(self) -> QRectF:
        rect = QRectF()
        for it in (self.glow_item, self.text_item):
            if it.isVisible():
                rect = rect.united(it.mapRectToScene(it.boundingRect()))
        return rect if not rect.isNull() else QRectF(0, 0, 600, 400)

    def _ctrl_wheel_zoom(self, d):
        z = self.sliders["zoom"].slider
        z.setValue(max(z.minimum(), min(z.maximum(), z.value() + d)))

    # ==================================================== generators (TAB 2)
    def _gen_prose(self, v, rng):
        rich = max(0.02, v["g_rich"] / 100)
        pools = {}
        for name, bank in (("n", NOUNS), ("a", ADJECTIVES), ("v", VERBS), ("d", ADVERBS)):
            pools[name] = rng.sample(bank, max(2, int(len(bank) * rich)))
        adjp, advp = v["g_adj"] / 100, v["g_adv"] / 100
        comma_p, repeat_p = v["g_comma"] / 100, v["g_repeat"] / 100

        def np():
            n = rng.choice(pools["n"])
            if rng.random() < adjp:
                return f"{rng.choice(pools['a'])} {n}"
            return n

        def vp():
            s = rng.choice(pools["v"])
            if rng.random() < advp:
                return f"{s} {rng.choice(pools['d'])}"
            return s

        openers = (
            lambda: f"the {np()} {vp()}",
            lambda: f"{np()} {vp()}",
            lambda: f"every {np()} {vp()}",
            lambda: f"no {np()} {vp()}",
            lambda: f"one {np()} {vp()}",
        )

        def sentence(made):
            if made and rng.random() < repeat_p:
                return rng.choice(made)
            s = rng.choice(openers)()
            if rng.random() < comma_p:
                s += f", {rng.choice(CONNECTORS)} the {np()} {vp()}"
            if rng.random() < comma_p * 0.6:
                s += f" {rng.choice(ENDERS)}"
            return s[0].upper() + s[1:] + "."

        sents, made, count = [], [], 0
        total = v["g_words"]
        guard = total * 4 + 200
        while count < total and guard > 0:
            guard -= 1
            st = sentence(made)
            made.append(st)
            if len(made) > 24:
                made.pop(0)
            sents.append(st)
            count += len(st.split())

        if count > total:
            over = count - total
            words = sents[-1][:-1].split()
            if len(words) > over:
                sents[-1] = " ".join(words[: len(words) - over]) + "."

        per = v["g_par"]
        if per >= 1:
            return "\n\n".join(" ".join(sents[i:i + per])
                               for i in range(0, len(sents), per))
        return " ".join(sents)

    def _gen_syll(self, v, rng):
        onset_p, coda_p = v["s_onset"] / 100, v["s_coda"] / 100
        dbl_p, caps_p = v["s_dbl"] / 100, v["s_caps"] / 100
        out = []
        for _ in range(v["s_words"]):
            n = v["s_syl"] + (rng.choice((-1, 0, 0, 1)) if v["s_syl"] > 1 else 0)
            w = ""
            for _ in range(max(1, n)):
                on = rng.choice(ONSETS) if rng.random() < onset_p else ""
                vo = rng.choice(VOWELS)
                co = rng.choice(CODAS) if rng.random() < coda_p else ""
                w += on + vo + co
            if rng.random() < dbl_p and len(w) > 2:
                i = rng.randrange(len(w) - 1)
                w = w[:i] + w[i] * 2 + w[i + 1:]
            if rng.random() < caps_p:
                w = w.capitalize()
            out.append(w)
        if (wpl := v["s_wpl"]) >= 1:
            return "\n".join(" ".join(out[i:i + wpl])
                             for i in range(0, len(out), wpl))
        return " ".join(out)

    def _gen_pattern(self, v, rng):
        rule, width, height = v["p_rule"], v["p_width"], v["p_height"]
        dens, noise = v["p_dens"] / 100, v["p_noise"] / 100
        wrap, inv = bool(v["p_wrap"]), bool(v["p_inv"])
        dead, alive = CHARSETS[v["p_set"] % len(CHARSETS)]
        if inv:
            dead, alive = alive, dead

        row = [1 if rng.random() < dens else 0 for _ in range(width)]
        lines = []
        for _ in range(height):
            chars = []
            for c in row:
                r = rng.random()
                ch = alive if c else dead
                if r < noise:
                    ch = dead if c else alive
                chars.append(ch)
            lines.append("".join(chars))
            nxt = []
            for x in range(width):
                if wrap:
                    l, r2 = row[x - 1], row[(x + 1) % width]
                else:
                    l = row[x - 1] if x > 0 else 0
                    r2 = row[x + 1] if x < width - 1 else 0
                nxt.append((rule >> ((l << 2) | (row[x] << 1) | r2)) & 1)
            row = nxt
        return "\n".join(lines)

    def gen_refresh(self):
        vals = {k: s.value() for k, s in self.gsliders.items()}
        mode = self.gen_combo.currentText()
        rng = random.Random(vals["gseed"] * 1013 + MODE_SALT[mode])
        if mode == "Prose":
            text = self._gen_prose(vals, rng)
        elif mode == "Syllables":
            text = self._gen_syll(vals, rng)
        else:
            text = self._gen_pattern(vals, rng)
        self.generated = text
        self.gen_preview.setLineWrapMode(
            QTextEdit.LineWrapMode.NoWrap if mode == "Pattern"
            else QTextEdit.LineWrapMode.WidgetWidth)
        self._apply_gen_style()
        self.textfx.show(text, mode)          # animated entrance (6.0)
        self.gen_stats.setText(
            f"{len(text):,} chars · {len(text.split()):,} words · {text.count(chr(10)) + 1:,} lines")

    def _apply_gen_style(self):
        r, g, b = (self.gsliders["gred"].value(), self.gsliders["ggreen"].value(),
                   self.gsliders["gblue"].value())
        self.gen_preview.setStyleSheet(
            f"QTextEdit {{ color: rgb({r},{g},{b}); "
            f"font-family:'Consolas','Courier New',monospace; "
            f"font-size:{self.gsliders['gsize'].value()}pt; }}")
        cur = QTextCursor(self.gen_preview.document())
        cur.select(QTextCursor.SelectionType.Document)
        bf = QTextBlockFormat()
        try:
            lh = int(QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        except Exception:
            lh = 1
        bf.setLineHeight(float(self.gsliders["glh"].value()), lh)
        cur.mergeBlockFormat(bf)
        self.gswatch.setStyleSheet(f"background-color: rgb({r},{g},{b}); border:1px solid #888;")

    def _schedule_gen(self):
        self.gen_timer.start()

    def _gen_mode_changed(self, mode):
        for k, sec in self.gen_groups.items():
            sec.setVisible(k in (mode, "style"))
        if self.gen_animator.mode == "wave":          # re-target live
            self.gen_animator.start_wave(self._gen_wave_params(self._gen_wave_keys()))
        self._schedule_gen()

    def _gen_reset_one(self, s):
        s.slider.setValue(s.default)

    # --------------------------------------------- generate animation (6.0)
    def _gen_wave_keys(self):
        """Visible sliders of the active generator mode + style + seed."""
        mode = self.gen_combo.currentText()
        keys = []
        for k in self.gsliders:
            grp = "seed" if k == "gseed" else ("style" if k in GEN_STYLE_KEYS else mode)
            sec = self.gen_groups.get(grp)
            if sec is not None and sec.isVisible() and sec.fold.isChecked():
                keys.append(k)
        return keys

    def _gen_wave_params(self, keys):
        params = {}
        for k in keys:
            sl = self.gsliders[k].slider
            mn, mx = sl.minimum(), sl.maximum()
            crc = zlib.crc32(k.encode())
            f = 0.12 + (crc % 100) / 100 * 0.18
            ph = (crc % 628) / 100.0
            params[k] = (sl.value(), mn, mx, f, ph)
        return params

    def _toggle_gen_wave(self, on):
        if on:
            params = self._gen_wave_params(self._gen_wave_keys())
            if not params:
                self.gen_animate_btn.setChecked(False)
                self.statusBar().showMessage("Nothing visible to animate.", 3000)
                return
            self.gen_animator.start_wave(params)
        elif self.gen_animator.mode == "wave":
            self.gen_animator.stop(commit=False)

    def _apply_gen_animated(self, vals):
        for k, v in vals.items():
            s = self.gsliders.get(k)
            if s:
                s.set_value_silent(v)
        self.gen_refresh()               # direct: keep the cauldron boiling

    def _on_gen_anim_state(self, mode):
        self.gen_animate_btn.setChecked(mode == "wave")
        self.gen_animate_btn.setText("⏸ Stop" if mode == "wave" else "⏵ Animate")
        if mode == "wave":
            self.statusBar().showMessage(
                "Generator wave — the text is alive. F5 to stop.", 5000)

    def _gen_speed_changed(self, v):
        sp = v / 100
        self.gen_animator.set_speed(sp)
        self.textfx.set_speed(sp)
        if self.evolve_timer.isActive():          # evolve rate follows too
            self.evolve_timer.setInterval(self._evolve_interval())
        self.gen_speed_label.setText(f"x{sp:.2f}")

    def _toggle_evolve(self, on):
        if on:
            self.evolve_timer.setInterval(self._evolve_interval())
            self.evolve_timer.start()
            self.statusBar().showMessage(
                "Evolve: the seed ticks forward — the text mutates forever.", 5000)
        else:
            self.evolve_timer.stop()

    def _evolve_interval(self):
        return int(max(40, 160 / self.textfx.speed))

    def _evolve_step(self):
        sl = self.gsliders["gseed"].slider
        sl.setValue(sl.value() % 999 + 1)         # wraps 1..999, fires refresh

    def _gen_new_seed(self):
        """Animated dice roll: the seed slider glides to its new value."""
        sl = self.gsliders["gseed"].slider
        target = random.randint(1, 999)
        anim = QVariantAnimation(self)
        anim.setStartValue(sl.value())
        anim.setEndValue(target)
        anim.setDuration(650)
        anim.setEasingCurve(QEasingCurve(
            EASINGS.get(self.easing_combo.currentText(),
                        QEasingCurve.Type.OutCubic)))
        anim.valueChanged.connect(sl.setValue)    # fires gen refresh each frame
        self._seed_anim = anim                    # keep a reference
        anim.start()
        self.statusBar().showMessage(f"Rolled seed → {target}", 2500)

    # ------------------------------------------------ generate file actions
    def gen_send(self):
        if not self.generated:
            return
        self.raw_text = self.generated
        self.file_path = None
        self.file_label.setText("(generated text — use Save As)")
        self.tabs.setCurrentIndex(0)
        self.refresh()
        self.statusBar().showMessage("Generated text loaded into the Transform tab", 4000)

    def gen_copy(self):
        QApplication.clipboard().setText(self.generated)
        self.statusBar().showMessage("Generated text copied to clipboard", 3000)

    def gen_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save generated text", "generated.txt",
            "Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            Path(path).write_text(self.generated, "utf-8")
        except OSError as e:
            self.statusBar().showMessage(f"Could not save: {e}", 5000)
            return
        self.statusBar().showMessage(f"Saved {len(self.generated):,} chars to {path}", 5000)

    # ============================================================= animation
    def _f5_route(self):
        """F5 animates whichever tab is visible."""
        if self.tabs.currentIndex() == 0:
            self.animate_btn.toggle()
        else:
            self.gen_animate_btn.toggle()

    def _wave_keys(self):
        return [k for k, s in self.sliders.items() if not s.isHidden()]

    def _wave_params(self, keys):
        params = {}
        for k in keys:
            sl = self.sliders[k]
            if sl.locked:
                continue
            s = sl.slider
            mn, mx = s.minimum(), s.maximum()
            crc = zlib.crc32(k.encode())
            f = 0.12 + (crc % 100) / 100 * 0.18
            ph = (crc % 628) / 100.0
            params[k] = (s.value(), mn, mx, f, ph)
        return params

    def _toggle_wave(self, on):
        if on:
            params = self._wave_params(self._wave_keys())
            if not params:
                self.animate_btn.setChecked(False)
                self.statusBar().showMessage(
                    "All visible sliders are locked or filtered out.", 3000)
                return
            self.animator.start_wave(params)
        elif self.animator.mode == "wave":
            self.animator.stop()

    def _speed_changed(self, v):
        self.animator.set_speed(v / 100)
        self.speed_label.setText(f"x{v / 100:.2f}")

    def _sweep_changed(self, v):
        self.animator.set_sweep(v / 100)
        self.sweep_label.setText(f"{v}%")

    def _on_anim_state(self, mode):
        self.animate_btn.setChecked(mode == "wave")
        self.animate_btn.setText("⏸ Stop" if mode == "wave" else "⏵ Animate")
        if mode == "wave":
            self.statusBar().showMessage(
                "Auto-animate — F5 to stop. Watch the sparklines trace the waves.", 6000)
        elif mode == "tween":
            self.statusBar().showMessage("Morphing sliders…", 2000)
        elif mode == "":
            self.statusBar().showMessage("Animation stopped", 2500)

    def _apply_animated(self, vals):
        for k, v in vals.items():
            s = self.sliders.get(k)
            if s:
                s.set_value_silent(v)
        self.refresh()

    def _cancel_tween(self):
        if self.animator.mode == "tween":
            self.animator.stop(commit=False)

    def _reset_one(self, s):
        if s.key is None:
            s.slider.setValue(s.default)
            return
        if self.transitions_act.isChecked() and not self.animator.is_running():
            self.animator.start_tween({s.key: s.default}, 350,
                                      self.easing_combo.currentText())
        else:
            s.slider.setValue(s.default)
            self._checkpoint()

    def _morph_to(self, state):
        if self.animator.mode == "wave":
            self.animator.stop()
        if self.transitions_act.isChecked() and not self.animator.is_running():
            self.animator.start_tween(state, 900, self.easing_combo.currentText())
        else:
            self._apply_and_commit(state)

    # ------------------------------------------------------- A/B crossfade
    def _capture_a(self):
        self.stateA = self._snapshot()
        self._update_ab_buttons()
        self.statusBar().showMessage(f"State A captured ({len(self.stateA)} sliders)", 3000)

    def _capture_b(self):
        self.stateB = self._snapshot()
        self._update_ab_buttons()
        self.statusBar().showMessage(f"State B captured ({len(self.stateB)} sliders)", 3000)

    def _update_ab_buttons(self):
        self.btn_a.setText("A ✓" if self.stateA else "Set A")
        self.btn_b.setText("B ✓" if self.stateB else "Set B")

    def _blended(self, t):
        a, b = self.stateA or {}, self.stateB or {}
        out = {}
        for k, sl in self.sliders.items():
            av = a.get(k, sl.default)
            bv = b.get(k, sl.default)
            out[k] = int(round(av + (bv - av) * t))
        return out

    def _blend_changed(self, pos):
        if not (self.stateA and self.stateB):
            self.blend_label.setText("set A & B first")
            return
        self.blend_label.setText(f"A↔B {pos}%")
        for k, v in self._blended(pos / 100).items():
            self.sliders[k].set_value_silent(v)
        self.refresh()

    def _play_blend(self):
        if not (self.stateA and self.stateB):
            self.statusBar().showMessage("Capture both A and B first.", 3000)
            return
        self.animator.stop(commit=False)
        anim = QVariantAnimation(self)
        anim.setStartValue(0)
        anim.setEndValue(100)
        anim.setDuration(1400)
        anim.setEasingCurve(QEasingCurve(
            EASINGS.get(self.easing_combo.currentText(), QEasingCurve.Type.OutCubic)))
        anim.valueChanged.connect(self.blend_slider.setValue)
        anim.finished.connect(self._checkpoint)
        self._blend_anim = anim
        anim.start()

    # ================================================== undo / redo / commit
    def _snapshot(self):
        return {k: s.slider.value() for k, s in self.sliders.items()}

    def _set_values(self, state):
        self.animator.stop(commit=False)
        for k, v in state.items():
            if k in self.sliders:
                self.sliders[k].set_value_silent(v)
        self.refresh()

    def _checkpoint(self):
        cur = self._snapshot()
        if cur != self._committed:
            self._undo.append(self._committed)
            self._redo.clear()
            if len(self._undo) > 60:
                self._undo.pop(0)
            self._committed = cur

    def _apply_and_commit(self, state):
        self._undo.append(self._committed)
        self._redo.clear()
        self._committed = dict(state)
        self._set_values(state)

    def undo(self):
        if not self._undo:
            return
        self._redo.append(self._committed)
        self._committed = self._undo.pop()
        self._set_values(self._committed)

    def redo(self):
        if not self._redo:
            return
        self._undo.append(self._committed)
        self._committed = self._redo.pop()
        self._set_values(self._committed)

    # =============================================================== presets
    def _load_user_presets(self):
        try:
            return json.loads(PRESET_FILE.read_text("utf-8"))
        except Exception:
            return {}

    def _save_user_presets(self):
        try:
            PRESET_FILE.write_text(json.dumps(self.user_presets, indent=2), "utf-8")
        except OSError as e:
            self.statusBar().showMessage(f"Could not save presets: {e}", 5000)

    def _repopulate_presets(self, select=None):
        cb = self.preset_combo
        cb.blockSignals(True)
        cb.clear()
        cb.addItems(["Factory reset"] + list(BUILTIN_PRESETS) + list(self.user_presets))
        if select:
            cb.setCurrentText(select)
        cb.blockSignals(False)

    def _apply_preset(self, name):
        if name == "Factory reset":
            state = dict(DEFAULTS)
        elif name in BUILTIN_PRESETS:
            state = {**DEFAULTS, **BUILTIN_PRESETS[name]}
        elif name in self.user_presets:
            state = {**DEFAULTS, **self.user_presets[name]}
        else:
            return
        self._morph_to(state)
        self.statusBar().showMessage(f"Preset applied: {name}", 3000)

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        if ok and name.strip():
            self.user_presets[name.strip()] = self._snapshot()
            self._save_user_presets()
            self._repopulate_presets(select=name.strip())

    def _delete_preset(self):
        name = self.preset_combo.currentText()
        if name in self.user_presets:
            del self.user_presets[name]
            self._save_user_presets()
            self._repopulate_presets(select="Factory reset")
            self.statusBar().showMessage(f"Deleted preset: {name}", 3000)
        else:
            self.statusBar().showMessage("Built-in presets can't be deleted.", 3000)

    # ============================================================ randomize
    def randomize_all(self):
        self.animator.stop(commit=False)
        n = 0
        for s in self.sliders.values():
            if s.locked:
                continue
            s.slider.setValue(random.randint(s.slider.minimum(), s.slider.maximum()))
            n += 1
        self._checkpoint()
        self.statusBar().showMessage(f"Randomized {n} sliders (locked skipped)", 3000)

    def randomize_group(self, key):
        self.animator.stop(commit=False)
        for s in self.groups[key]["sliders"]:
            if not s.locked:
                s.slider.setValue(random.randint(s.slider.minimum(), s.slider.maximum()))
        self._checkpoint()

    def reset_all(self):
        self._morph_to(dict(DEFAULTS))

    def unlock_all(self):
        n = 0
        for s in self.sliders.values():
            if s.locked:
                s.locked = False
                s.caption_label.setText(s.caption)
                n += 1
        if n:
            self.statusBar().showMessage(f"Unlocked {n} sliders", 3000)

    # --------------------------------------------------------------- filter
    def _filter_sliders(self, query):
        q = query.lower().strip()
        mod_only = self.mod_btn.isChecked()
        for s in self.sliders.values():
            vis = (q in s.caption.lower()) if q else True
            if vis and mod_only:
                vis = s.slider.value() != s.default
            s.setVisible(vis)
        for g in self.groups.values():
            g["sec"].setVisible(any(not sl.isHidden() for sl in g["sliders"]))
        for s in self.sliders.values():
            s.set_highlight(bool(q))
        if self.animator.mode == "wave":
            self.animator.start_wave(self._wave_params(self._wave_keys()))

    def _lock_changed(self, s):
        if self.animator.mode == "wave":
            self.animator.start_wave(self._wave_params(self._wave_keys()))
        self.statusBar().showMessage(
            f"{'Locked' if s.locked else 'Unlocked'} “{s.caption}” — "
            f"{'skipped by randomize & waves' if s.locked else 'back in play'}", 3500)

    def update_group_badges(self):
        for key, g in self.groups.items():
            n = sum(1 for sl in g["sliders"] if sl.slider.value() != sl.default)
            g["sec"].set_badge(n)

    # ============================================================= file ops
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open text file", "", "Text files (*.txt);;All files (*)")
        if path:
            self._load_path(path)

    def _load_path(self, path):
        try:
            self.raw_text = Path(path).read_text("utf-8", errors="replace")
        except OSError as e:
            self.statusBar().showMessage(f"Could not open: {e}", 5000)
            return
        self.file_path = str(path)
        self.file_label.setText(path)
        self.refresh()
        self.statusBar().showMessage(f"Opened {path} ({len(self.raw_text):,} chars)", 5000)

    def save_file(self):
        if self.file_path:
            self._write(self.file_path)
        else:
            self.save_file_as()

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save text file", "slidertext.txt",
            "Text files (*.txt);;All files (*)")
        if not path:
            return
        self.file_path = path
        self.file_label.setText(path)
        self._write(path)

    def _write(self, path, quiet=False):
        out = self.transform_text(self.raw_text)
        try:
            Path(path).write_text(out, "utf-8")
        except OSError as e:
            self.statusBar().showMessage(f"Could not save: {e}", 5000)
            return
        if not quiet:
            self.statusBar().showMessage(f"Saved {len(out):,} chars to {path}", 5000)

    def copy_text(self):
        QApplication.clipboard().setText(self.transform_text(self.raw_text))
        self.statusBar().showMessage("Transformed text copied to clipboard", 3000)

    def _render_scene_png(self, path):
        rect = self._content_rect().adjusted(-40, -40, 40, 40)
        img = QImage((rect.size() * 2).toSize(), QImage.Format.Format_ARGB32)
        img.fill(self.scene.backgroundBrush().color())
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(2, 2)
        self.scene.render(p, QRectF(), rect)
        p.end()
        img.save(str(path))

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export preview as PNG", "preview.png", "PNG images (*.png)")
        if path:
            self._render_scene_png(path)
            self.statusBar().showMessage(f"PNG saved: {path}", 5000)

    def export_frames(self):
        keys = self._wave_keys()
        if not keys:
            self.statusBar().showMessage("No visible sliders to animate.", 3000)
            return
        d = QFileDialog.getExistingDirectory(self, "Choose folder for PNG frames")
        if not d:
            return
        self.animator.stop()
        params = self._wave_params(keys)
        if not params:
            self.statusBar().showMessage("All visible sliders are locked.", 3000)
            return
        frames, period = 48, 8.4
        start = self._snapshot()
        self.statusBar().showMessage("Rendering frames…")
        for i in range(frames):
            t = i / frames * period
            for k, (c, mn, mx, f, ph) in params.items():
                v = c + (mx - mn) / 2 * self.animator.sweep * math.sin(
                    2 * math.pi * f * t + ph)
                self.sliders[k].set_value_silent(int(round(max(mn, min(mx, v)))))
            self.transformed = self.transform_text(self.raw_text)
            self.apply_display(self.transformed)
            self._render_scene_png(Path(d) / f"frame_{i:03d}.png")
            if i % 4 == 0:
                QApplication.processEvents()
        for k, v in start.items():
            self.sliders[k].set_value_silent(v)
        self.refresh()
        self.statusBar().showMessage(f"Saved {frames} frames to {d}", 6000)

    # ===================================================== session persistence
    def _save_session(self):
        data = {
            "t": self._snapshot(),
            "g": {k: s.value() for k, s in self.gsliders.items()},
            "dark": self.dark_act.isChecked(),
            "fx": self.gen_fx_combo.currentText(),
        }
        try:
            STATE_FILE.write_text(json.dumps(data), "utf-8")
        except OSError:
            pass

    def _restore_session(self):
        try:
            data = json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            return False
        for k, v in data.get("t", {}).items():
            if k in self.sliders:
                self.sliders[k].set_value_silent(int(v))
        for k, v in data.get("g", {}).items():
            if k in self.gsliders:
                self.gsliders[k].set_value_silent(int(v))
        if data.get("dark"):
            self.dark_act.setChecked(True)
        if data.get("fx") in TextFX.MODES:
            self.gen_fx_combo.setCurrentText(data["fx"])
        self._committed = self._snapshot()
        return True

    # ===================================================== drag & drop open
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            if url.toLocalFile():
                self._load_path(url.toLocalFile())
                break

    # ============================================================== lifecycle
    def refresh(self):
        if self._compare:
            text = self.raw_text
        else:
            self.transformed = self.transform_text(self.raw_text)
            text = self.transformed
        self.apply_display(text)
        self._update_stats(text)
        self._update_title()
        self.update_group_badges()
        if self.autosave_btn.isChecked() and self.file_path:
            self._write(self.file_path, quiet=True)

    def _update_stats(self, text):
        kb = len(text.encode("utf-8", "replace")) / 1024
        self.stats_label.setText(
            f"{len(text):,} chars · {len(text.split()):,} words · "
            f"{text.count(chr(10)) + 1:,} lines · {kb:,.1f} KB")

    def _update_title(self):
        mod = any(s.slider.value() != s.default for s in self.sliders.values())
        nmod = sum(1 for s in self.sliders.values() if s.slider.value() != s.default)
        nlock = sum(1 for s in self.sliders.values() if s.locked)
        self.mod_label.setText(f"{nmod} modified · {nlock} locked")
        base = f"{self.file_path or 'Untitled'} — Slider Text Studio"
        self.setWindowTitle(("• " if mod else "") + base)

    def closeEvent(self, e):
        self._save_session()
        self.animator.stop(commit=False)
        self.gen_animator.stop(commit=False)
        self.evolve_timer.stop()
        self.textfx.stop()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    win = TextStudio()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()