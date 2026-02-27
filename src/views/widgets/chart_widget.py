"""
ChartWidget - OHLC Candlestick Chart mit Volumen & Indikator-Overlay
src/views/widgets/chart_widget.py

Features:
- Candlestick-Chart (OHLCV) via pyqtgraph
- Volumen-Balken (unteres Panel, synchronisiert)
- Indikator-Overlays: SMA, MACD, ROC (erweiterbar)
- Crosshair mit Live-OHLCV-Anzeige
- Zoom (Maus-Scroll) & Pan (Drag)
- Zeitraum-Buttons: 1M / 3M / 6M / 1J / Alles
- Dark Theme, passend zu DataTableWidget
- Öffentliche API: load_data(), add_indicator(), clear_indicators()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QMouseEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Farb-Palette (konsistent mit DataTableWidget)
# ---------------------------------------------------------------------------

C_BG          = "#0D0F1A"   # Chart-Hintergrund
C_BG_PANEL    = "#1E2235"   # Toolbar / Panel
C_GRID        = "#1C2038"
C_BULL        = "#26A65B"   # Grün – bullish Kerze
C_BEAR        = "#E84343"   # Rot   – bearish Kerze
C_BULL_BODY   = "#26A65B"
C_BEAR_BODY   = "#E84343"
C_WICK        = "#6B7499"
C_VOL_BULL    = "#1A5C3A"
C_VOL_BEAR    = "#5C1A1A"
C_CROSS       = "#5A6FAA"
C_TEXT        = "#E8EAED"
C_TEXT_DIM    = "#6B7499"
C_AXIS        = "#2D3250"

# Indikator-Farben (zyklisch)
INDICATOR_COLORS = ["#F5A623", "#4A90D9", "#9B59B6", "#1ABC9C", "#E67E22"]


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class OHLCVBar:
    """Ein einzelner OHLCV-Datenpunkt."""
    date:      date
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float
    adj_close: float = 0.0

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open


@dataclass
class IndicatorSeries:
    """Eine berechnete Indikator-Linie."""
    name:   str
    values: np.ndarray          # Länge = Anzahl Bars (nan für fehlende Werte)
    color:  str = "#F5A623"
    width:  float = 1.5
    panel:  str = "main"        # "main" oder "sub"


# ---------------------------------------------------------------------------
# Candlestick-Item (Custom pyqtgraph GraphicsItem)
# ---------------------------------------------------------------------------

class CandlestickItem(pg.GraphicsObject):
    """
    Candlestick-Zeichnung mit:
    - Körper: 0.6 Daten-Einheiten breit (= 60% des Slots, 40% Lücke)
    - Docht: cosmetic=True → immer 1 Pixel breit, unabhängig vom Zoom
    """

    W = 0.3   # halbe Körperbreite in Daten-Einheiten (0.3 = 60% des Slots)

    def __init__(self) -> None:
        super().__init__()
        self._bars: list[OHLCVBar] = []

    def set_bars(self, bars: list[OHLCVBar]) -> None:
        self._bars = bars
        self.prepareGeometryChange()
        self.update()

    def paint(self, p, *args) -> None:
        if not self._bars:
            return
        p.setRenderHint(QPainter.Antialiasing, False)

        for i, bar in enumerate(self._bars):
            if bar.is_bullish:
                body_color = QColor(C_BULL_BODY)
                wick_color = QColor(C_BULL)
            else:
                body_color = QColor(C_BEAR_BODY)
                wick_color = QColor(C_BEAR)

            # Docht: cosmetic Pen = immer 1px, egal wie weit gezoomt
            wick_pen = QPen(wick_color)
            wick_pen.setWidth(1)
            wick_pen.setCosmetic(True)
            p.setPen(wick_pen)
            p.drawLine(QPointF(i, bar.low), QPointF(i, bar.high))

            # Körper: feste Daten-Breite, kein Pen (kein Rand)
            body_top    = max(bar.open, bar.close)
            body_bottom = min(bar.open, bar.close)
            body_height = max(body_top - body_bottom, 0.0001)

            p.setPen(Qt.NoPen)
            p.setBrush(body_color)
            p.drawRect(pg.QtCore.QRectF(i - self.W, body_bottom, 2 * self.W, body_height))

    def boundingRect(self) -> pg.QtCore.QRectF:
        if not self._bars:
            return pg.QtCore.QRectF()
        return pg.QtCore.QRectF(
            -0.5,
            min(b.low for b in self._bars),
            len(self._bars) + 0.5,
            max(b.high for b in self._bars) - min(b.low for b in self._bars),
        )


# ---------------------------------------------------------------------------
# Volumen-Item
# ---------------------------------------------------------------------------

class VolumeItem(pg.GraphicsObject):
    """Volumen-Balken – gleiche feste Breite wie CandlestickItem."""

    W = 0.3   # identisch mit CandlestickItem.W

    def __init__(self) -> None:
        super().__init__()
        self._bars: list[OHLCVBar] = []

    def set_bars(self, bars: list[OHLCVBar]) -> None:
        self._bars = bars
        self.prepareGeometryChange()
        self.update()

    def paint(self, p, *args) -> None:
        if not self._bars:
            return
        for i, bar in enumerate(self._bars):
            color = QColor(C_VOL_BULL if bar.is_bullish else C_VOL_BEAR)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRect(pg.QtCore.QRectF(i - self.W, 0, 2 * self.W, bar.volume))

    def boundingRect(self) -> pg.QtCore.QRectF:
        if not self._bars:
            return pg.QtCore.QRectF()
        max_vol = max(b.volume for b in self._bars) if self._bars else 1
        return pg.QtCore.QRectF(-0.5, 0, len(self._bars) + 0.5, max_vol)


# ---------------------------------------------------------------------------
# X-Achsen-Label (Datum statt Index)
# ---------------------------------------------------------------------------

class DateAxisItem(pg.AxisItem):
    """Ersetzt numerischen x-Index durch Datums-Labels."""

    def __init__(self, dates: list[date], **kwargs):
        super().__init__(**kwargs)
        self._dates = dates
        self.setStyle(tickTextOffset=4)

    def set_dates(self, dates: list[date]) -> None:
        self._dates = dates

    def tickStrings(self, values, scale, spacing) -> list[str]:
        result = []
        for v in values:
            i = int(round(v))
            if 0 <= i < len(self._dates):
                d = self._dates[i]
                result.append(d.strftime("%d.%m.%y"))
            else:
                result.append("")
        return result


# ---------------------------------------------------------------------------
# Crosshair + OHLCV-Info-Label
# ---------------------------------------------------------------------------

class CrosshairOverlay:
    """Vertikale + horizontale Linie mit schwebendem Info-Label."""

    def __init__(
        self,
        plot: pg.PlotItem,
        info_label: QLabel,
        bars: list[OHLCVBar],
    ) -> None:
        self._plot = plot
        self._label = info_label
        self._bars = bars

        pen = pg.mkPen(color=C_CROSS, width=1, style=Qt.DashLine)
        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._hline = pg.InfiniteLine(angle=0,  movable=False, pen=pen)
        plot.addItem(self._vline, ignoreBounds=True)
        plot.addItem(self._hline, ignoreBounds=True)

    def update_bars(self, bars: list[OHLCVBar]) -> None:
        self._bars = bars

    def on_mouse_move(self, pos) -> None:
        if not self._plot.sceneBoundingRect().contains(pos):
            return
        mp = self._plot.vb.mapSceneToView(pos)
        self._vline.setPos(mp.x())
        self._hline.setPos(mp.y())

        i = int(round(mp.x()))
        if 0 <= i < len(self._bars):
            bar = self._bars[i]
            chg = bar.close - bar.open
            pct = (chg / bar.open * 100) if bar.open else 0
            sign = "▲" if chg >= 0 else "▼"
            color = C_BULL if chg >= 0 else C_BEAR
            self._label.setText(
                f"<span style='color:{C_TEXT_DIM}'>{bar.date.strftime('%d.%m.%Y')}</span>"
                f"  <b>O</b> {bar.open:.4f}"
                f"  <b>H</b> {bar.high:.4f}"
                f"  <b>L</b> {bar.low:.4f}"
                f"  <b>C</b> <span style='color:{color}'>{bar.close:.4f}</span>"
                f"  <span style='color:{color}'>{sign} {abs(chg):.4f} ({pct:+.2f}%)</span>"
                f"  <span style='color:{C_TEXT_DIM}'>Vol {int(bar.volume):,}</span>"
            )



# ---------------------------------------------------------------------------
# Range-Slider (Zwei-Handle, für freie Zeitraum-Wahl)
# ---------------------------------------------------------------------------

class RangeSlider(QWidget):
    """
    Horizontaler Zwei-Handle-Slider.

    Signale
    -------
    rangeChanged(left_frac, right_frac)
        Beide Werte in [0.0, 1.0] – Anteil des Gesamtzeitraums.
    """

    rangeChanged = Signal(float, float)

    _HANDLE_W = 10   # Breite eines Handles in px
    _TRACK_H  = 4    # Höhe der Track-Linie
    _SNAP_PX  = 20   # Mindestabstand zwischen Handles in px

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(32)
        self.setMaximumHeight(32)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._left  = 0.0   # [0..1]
        self._right = 1.0   # [0..1]
        self._drag: Optional[str] = None   # "left" | "right" | "range"
        self._drag_start_x = 0
        self._drag_start_left  = 0.0
        self._drag_start_right = 1.0

        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def set_range(self, left: float, right: float, emit: bool = False) -> None:
        """Setzt den Slider programmatisch (Werte in [0..1])."""
        self._left  = max(0.0, min(left, 1.0))
        self._right = max(0.0, min(right, 1.0))
        if self._left > self._right - 0.01:
            self._left = max(0.0, self._right - 0.01)
        self.update()
        if emit:
            self.rangeChanged.emit(self._left, self._right)

    def get_range(self) -> tuple[float, float]:
        return self._left, self._right

    # ------------------------------------------------------------------
    # Zeichnung
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter, QBrush, QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        W = self.width()
        H = self.height()
        hw = self._HANDLE_W
        track_y = H // 2 - self._TRACK_H // 2
        track_x0 = hw // 2
        track_w  = W - hw

        lx = self._frac_to_px(self._left)
        rx = self._frac_to_px(self._right)

        # Track gesamt (dunkel)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2D3250"))
        p.drawRoundedRect(track_x0, track_y, track_w, self._TRACK_H, 2, 2)

        # Track aktiver Bereich (hell)
        p.setBrush(QColor("#3D4470"))
        p.drawRect(lx + hw // 2, track_y, rx - lx, self._TRACK_H)

        # Handles
        for x, hovered in [(lx, self._drag == "left"), (rx, self._drag == "right")]:
            color = QColor("#7A8BCC") if hovered else QColor("#5A6FAA")
            p.setBrush(color)
            p.setPen(QPen(QColor("#1E2235"), 1))
            p.drawRoundedRect(x, H // 2 - 8, hw, 16, 3, 3)

        # Datum-Labels
        p.setPen(QColor(C_TEXT_DIM))
        p.setFont(QFont("JetBrains Mono", 9))
        left_txt  = self._frac_to_label(self._left)
        right_txt = self._frac_to_label(self._right)
        p.drawText(max(0, lx - 2), H - 2, left_txt)
        rt_w = p.fontMetrics().horizontalAdvance(right_txt)
        p.drawText(min(W - rt_w, rx - rt_w // 2), H - 2, right_txt)

        p.end()

    # ------------------------------------------------------------------
    # Maus-Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        mx = event.position().x()
        lx = self._frac_to_px(self._left)
        rx = self._frac_to_px(self._right)

        if abs(mx - lx) <= self._HANDLE_W + 4:
            self._drag = "left"
        elif abs(mx - rx) <= self._HANDLE_W + 4:
            self._drag = "right"
        elif lx < mx < rx:
            self._drag = "range"
            self._drag_start_x     = int(mx)
            self._drag_start_left  = self._left
            self._drag_start_right = self._right
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag is None:
            return
        mx = event.position().x()
        frac = self._px_to_frac(mx)
        W = self.width()

        if self._drag == "left":
            snap = self._px_to_frac(self._frac_to_px(self._right) - self._SNAP_PX)
            self._left = max(0.0, min(frac, snap))
        elif self._drag == "right":
            snap = self._px_to_frac(self._frac_to_px(self._left) + self._SNAP_PX)
            self._right = min(1.0, max(frac, snap))
        elif self._drag == "range":
            delta = self._px_to_frac(mx) - self._px_to_frac(self._drag_start_x)
            span = self._drag_start_right - self._drag_start_left
            new_l = self._drag_start_left + delta
            new_r = self._drag_start_right + delta
            if new_l < 0:
                new_l = 0.0
                new_r = span
            if new_r > 1.0:
                new_r = 1.0
                new_l = 1.0 - span
            self._left  = new_l
            self._right = new_r

        self.update()
        self.rangeChanged.emit(self._left, self._right)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag = None
        self.update()

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def _frac_to_px(self, frac: float) -> int:
        hw = self._HANDLE_W
        return int(hw // 2 + frac * (self.width() - hw))

    def _px_to_frac(self, px: float) -> float:
        hw = self._HANDLE_W
        track_w = self.width() - hw
        if track_w <= 0:
            return 0.0
        return max(0.0, min(1.0, (px - hw // 2) / track_w))

    def set_dates(self, dates: list) -> None:
        """Ermöglicht Datums-Labels statt Prozentwerte."""
        self._dates = dates
        self.update()

    def _frac_to_label(self, frac: float) -> str:
        dates = getattr(self, '_dates', [])
        if not dates:
            return f"{int(frac * 100)}%"
        i = max(0, min(int(round(frac * (len(dates) - 1))), len(dates) - 1))
        d = dates[i]
        if hasattr(d, 'strftime'):
            return d.strftime("%d.%m.%y")
        return str(d)


# ---------------------------------------------------------------------------
# Haupt-Widget
# ---------------------------------------------------------------------------

class ChartWidget(QWidget):
    """
    OHLC Candlestick Chart Widget.

    Öffentliche API
    ---------------
    load_data(ticker_symbol, bars)
        Lädt eine Liste von OHLCVBar und zeichnet den Chart.

    add_indicator(series: IndicatorSeries)
        Fügt eine Indikator-Linie hinzu (main oder sub panel).

    clear_indicators()
        Entfernt alle Indikatoren.

    set_period(days)
        Zoomt auf die letzten N Tage.

    Signale
    -------
    barHovered(index)   – Index der Kerze unter dem Cursor
    """

    barHovered = Signal(int)
    indicatorRemoved = Signal(str)   # Emitted when indicator deleted via keyboard

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._bars:       list[OHLCVBar]       = []
        self._indicators: list[IndicatorSeries] = []
        self._ind_items:  list                  = []   # PlotDataItem list
        self._ind_item_names: dict = {}                # PlotDataItem → indicator name
        self._color_idx   = 0
        self._sync_slider = True   # Verhindert Rückkopplungsschleifen
        self._slider_connected = False
        self._selected_indicator: str | None = None    # Aktuell selektierter Indikator-Name

        self.setFocusPolicy(Qt.StrongFocus)  # Damit keyPressEvent funktioniert
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setMinimumSize(800, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setObjectName("chartToolbar")
        toolbar.setStyleSheet(f"""
            #chartToolbar {{
                background: {C_BG_PANEL};
                border-bottom: 1px solid #2D3250;
            }}
        """)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(12, 7, 12, 7)
        tl.setSpacing(6)

        self._lbl_ticker = QLabel("–")
        self._lbl_ticker.setStyleSheet(
            f"color:{C_TEXT}; font-size:15px; font-weight:700;"
            f"font-family:'JetBrains Mono',monospace;"
        )
        tl.addWidget(self._lbl_ticker)

        # OHLCV-Info (Crosshair)
        self._lbl_ohlcv = QLabel()
        self._lbl_ohlcv.setStyleSheet(
            f"color:{C_TEXT}; font-size:12px; font-family:'JetBrains Mono',monospace;"
        )
        tl.addWidget(self._lbl_ohlcv, 1)

        # Zeitraum-Buttons
        self._period_group = QButtonGroup(self)
        period_bar = QWidget()
        pl = QHBoxLayout(period_bar)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(2)

        for label, days in [("1M", 21), ("3M", 63), ("6M", 126), ("1J", 252), ("Alles", 0)]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(42, 26)
            btn.setStyleSheet(self._period_btn_style())
            btn.clicked.connect(lambda checked, d=days: self.set_period(d))
            self._period_group.addButton(btn)
            pl.addWidget(btn)
            if label == "Alles":
                btn.setChecked(True)

        tl.addWidget(period_bar)
        root.addWidget(toolbar)

        # ── pyqtgraph Layout ─────────────────────────────────────────
        pg.setConfigOptions(antialias=False, background=C_BG, foreground=C_TEXT_DIM)

        self._gw = pg.GraphicsLayoutWidget()
        self._gw.setBackground(C_BG)
        root.addWidget(self._gw, 1)

        # ── Range-Slider ─────────────────────────────────────────────
        slider_wrap = QWidget()
        slider_wrap.setObjectName("sliderWrap")
        slider_wrap.setStyleSheet(f"""
            #sliderWrap {{
                background: {C_BG_PANEL};
                border-top: 1px solid #2D3250;
            }}
        """)
        sw_lay = QVBoxLayout(slider_wrap)
        sw_lay.setContentsMargins(14, 6, 14, 8)
        sw_lay.setSpacing(0)

        lbl_slider = QLabel("Zeitraum")
        lbl_slider.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; font-family:'JetBrains Mono',monospace;")
        sw_lay.addWidget(lbl_slider)

        self._range_slider = RangeSlider()
        sw_lay.addWidget(self._range_slider)
        root.addWidget(slider_wrap)

        # Datum-Achse (geteilt)
        self._date_axis_main = DateAxisItem([], orientation="bottom")
        self._date_axis_vol  = DateAxisItem([], orientation="bottom")

        # Hauptplot (Kerzen + Indikatoren)
        self._plot_main = self._gw.addPlot(
            row=0, col=0,
            axisItems={"bottom": self._date_axis_main},
        )
        self._style_plot(self._plot_main)
        self._plot_main.setMinimumHeight(320)

        # Volumen-Plot
        self._plot_vol = self._gw.addPlot(
            row=1, col=0,
            axisItems={"bottom": self._date_axis_vol},
        )
        self._style_plot(self._plot_vol)
        self._plot_vol.setMaximumHeight(100)
        self._plot_vol.setLabel("left", "Vol", color=C_TEXT_DIM, size="10pt")

        # X-Achsen synchronisieren
        self._plot_vol.setXLink(self._plot_main)

        # Grafik-Items
        self._candle_item = CandlestickItem()
        self._vol_item    = VolumeItem()
        self._plot_main.addItem(self._candle_item)
        self._plot_vol.addItem(self._vol_item)


        # Sub-Plot für Indikatoren (z.B. MACD) – initial versteckt
        self._plot_sub = self._gw.addPlot(row=2, col=0)
        self._style_plot(self._plot_sub)
        self._plot_sub.setMaximumHeight(90)
        self._plot_sub.setXLink(self._plot_main)
        self._plot_sub.hide()

        # Crosshair
        self._crosshair = CrosshairOverlay(
            self._plot_main, self._lbl_ohlcv, self._bars
        )
        self._gw.scene().sigMouseMoved.connect(self._crosshair.on_mouse_move)

        # Row-Stretch
        self._gw.ci.layout.setRowStretchFactor(0, 4)
        self._gw.ci.layout.setRowStretchFactor(1, 1)
        self._gw.ci.layout.setRowStretchFactor(2, 1)

        # Zoom → Slider synchronisieren
        self._plot_main.sigXRangeChanged.connect(self._on_xrange_changed)

        # Klick auf Chart → Indikator selektieren
        self._gw.scene().sigMouseClicked.connect(self._on_scene_clicked)

    def _style_plot(self, plot: pg.PlotItem) -> None:
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.getAxis("bottom").setStyle(
            tickTextOffset=5,
            tickFont=QFont("JetBrains Mono", 9),
        )
        plot.getAxis("left").setStyle(
            tickTextOffset=5,
            tickFont=QFont("JetBrains Mono", 9),
        )
        for axis_name in ("top", "right"):
            plot.showAxis(axis_name, show=False)
        plot.getAxis("bottom").setPen(pg.mkPen(C_AXIS))
        plot.getAxis("left").setPen(pg.mkPen(C_AXIS))
        plot.setMenuEnabled(False)

    def _period_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                color: {C_TEXT_DIM};
                border: 1px solid #2D3250;
                border-radius: 3px;
                font-size: 11px;
                font-family: 'JetBrains Mono', monospace;
            }}
            QPushButton:hover {{
                background: #2D3250;
                color: {C_TEXT};
            }}
            QPushButton:checked {{
                background: #3D4470;
                color: {C_TEXT};
                border-color: #5A6FAA;
            }}
        """

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def load_data(self, ticker_symbol: str, bars: list[OHLCVBar]) -> None:
        """Hauptmethode: Lädt OHLCV-Daten und zeichnet den Chart."""
        # Chronologisch sortieren (ältestes zuerst = linke Seite)
        self._bars = sorted(bars, key=lambda b: b.date)
        dates = [b.date for b in self._bars]

        self._lbl_ticker.setText(ticker_symbol)
        self._date_axis_main.set_dates(dates)
        self._date_axis_vol.set_dates(dates)
        self._range_slider.set_dates(dates)
        self._crosshair.update_bars(self._bars)

        self._candle_item.set_bars(self._bars)
        self._vol_item.set_bars(self._bars)

        # Vorhandene Indikatoren neu zeichnen
        self._redraw_indicators()

        # Slider initialisieren
        self._range_slider.set_range(0.0, 1.0)
        if not self._slider_connected:
            self._range_slider.rangeChanged.connect(self._on_slider_changed)
            self._slider_connected = True

        # Alles zeigen
        self.set_period(0)
        logger.debug("ChartWidget: %d Bars geladen für %s", len(bars), ticker_symbol)

    def add_indicator(self, series: IndicatorSeries) -> None:
        """
        Fügt eine Indikator-Linie hinzu.

        Parameters
        ----------
        series.panel == "main"  → Overlay im Kerzen-Chart
        series.panel == "sub"   → Eigenes Panel unten (z.B. MACD, ROC)
        """
        if not series.color:
            series.color = INDICATOR_COLORS[self._color_idx % len(INDICATOR_COLORS)]
            self._color_idx += 1

        self._indicators.append(series)
        self._draw_indicator(series)

    def clear_indicators(self) -> None:
        """Entfernt alle Indikator-Linien."""
        for item in self._ind_items:
            try:
                item.getViewBox().removeItem(item)
            except Exception:
                pass
        self._ind_items.clear()
        self._ind_item_names.clear()
        self._indicators.clear()
        self._color_idx = 0
        self._selected_indicator = None
        self._plot_sub.hide()

    def remove_indicator(self, name: str) -> None:
        """
        Entfernt einen einzelnen Indikator anhand seines Namens.

        Parameters
        ----------
        name : str
            Name des Indikators (z.B. "SMA 20", "MACD", "Signal")
        """
        # Alle Indikatoren mit diesem Namen sammeln
        to_keep = [s for s in self._indicators if s.name != name]
        if len(to_keep) == len(self._indicators):
            return  # Nichts zum Entfernen

        # Alles neu zeichnen (einfachster sicherer Weg)
        self._indicators = to_keep
        for item in self._ind_items:
            try:
                item.getViewBox().removeItem(item)
            except Exception:
                pass
        self._ind_items.clear()
        self._ind_item_names.clear()
        self._color_idx = 0

        if self._selected_indicator == name:
            self._selected_indicator = None

        # Sub-Panel nur zeigen wenn noch sub-Indikatoren vorhanden
        has_sub = any(s.panel == "sub" for s in self._indicators)
        if not has_sub:
            self._plot_sub.hide()

        # Verbliebene Indikatoren neu zeichnen
        for series in self._indicators:
            if not series.color:
                series.color = INDICATOR_COLORS[self._color_idx % len(INDICATOR_COLORS)]
            self._color_idx += 1
            self._draw_indicator(series)

    def get_active_indicator_names(self) -> list[str]:
        """Gibt die Namen aller aktuell angezeigten Indikatoren zurück."""
        return [s.name for s in self._indicators]

    def set_period(self, days: int) -> None:
        """Zoomt auf die letzten `days` Bars (0 = alles)."""
        n = len(self._bars)
        if n == 0:
            return

        if days == 0 or days >= n:
            x_min, x_max = -0.5, n - 0.5
        else:
            x_min = n - days - 0.5
            x_max = n - 0.5

        # Slider synchronisieren (ohne Rückkopplung)
        self._sync_slider = False
        left_frac  = (x_min + 0.5) / n if n > 0 else 0.0
        right_frac = (x_max + 0.5) / n if n > 0 else 1.0
        self._range_slider.set_range(
            max(0.0, left_frac),
            min(1.0, right_frac),
        )
        self._sync_slider = True

        self._plot_main.setXRange(x_min, x_max, padding=0.01)

    # ------------------------------------------------------------------
    # Interne Methoden
    # ------------------------------------------------------------------

    def _on_slider_changed(self, left_frac: float, right_frac: float) -> None:
        """Slider → Chart-Zoom."""
        if not getattr(self, '_sync_slider', True):
            return
        n = len(self._bars)
        if n == 0:
            return
        x_min = left_frac  * n - 0.5
        x_max = right_frac * n - 0.5
        # Zeitraum-Buttons deselektieren
        for btn in self._period_group.buttons():
            btn.setChecked(False)
        self._plot_main.setXRange(x_min, x_max, padding=0.0)

    def _on_xrange_changed(self, _view, x_range) -> None:
        """Chart-Zoom (z.B. via Maus-Scroll) → Slider."""
        n = len(self._bars)
        if n == 0:
            return
        x_min, x_max = x_range
        left_frac  = (x_min + 0.5) / n
        right_frac = (x_max + 0.5) / n
        self._sync_slider = False
        self._range_slider.set_range(
            max(0.0, left_frac),
            min(1.0, right_frac),
        )
        self._sync_slider = True

    def _draw_indicator(self, series: IndicatorSeries) -> None:
        x = np.arange(len(series.values), dtype=float)
        y = series.values.astype(float)

        # NaN-Segmente aufteilen (keine Linien über Lücken)
        pen = pg.mkPen(color=series.color, width=series.width)

        if series.panel == "main":
            target = self._plot_main
        else:
            target = self._plot_sub
            self._plot_sub.show()

        # Segmente zeichnen (NaN-aware)
        segments = self._split_nan_segments(x, y)
        for sx, sy in segments:
            item = target.plot(sx, sy, pen=pen, name=series.name)
            # Breitere unsichtbare Hover-Zone für einfacheres Klicken
            item.setCurveClickable(True, width=12)
            self._ind_items.append(item)
            self._ind_item_names[id(item)] = series.name

    def _redraw_indicators(self) -> None:
        old = list(self._indicators)
        self.clear_indicators()
        for series in old:
            self.add_indicator(series)

    # ------------------------------------------------------------------
    #  Indikator-Selektion (Klick + Delete)
    # ------------------------------------------------------------------

    def _on_scene_clicked(self, event) -> None:
        """Klick im Chart → prüfe ob eine Indikator-Linie getroffen wurde."""
        if event.button() != Qt.LeftButton:
            return

        pos = event.scenePos()
        clicked_name = None

        # Prüfe alle Indikator-Items (PlotDataItem → .curve ist PlotCurveItem)
        for item in self._ind_items:
            try:
                curve = item.curve
                local_pos = curve.mapFromScene(pos)
                if curve.mouseShape().contains(local_pos):
                    clicked_name = self._ind_item_names.get(id(item))
                    break
            except Exception:
                continue

        if clicked_name:
            self._select_indicator(clicked_name)
            self.setFocus()
        else:
            self._deselect_indicator()

    def _select_indicator(self, name: str) -> None:
        """Markiert einen Indikator als selektiert (visuelle Hervorhebung)."""
        self._deselect_indicator()  # Vorherige Selektion aufheben
        self._selected_indicator = name

        # Selektierte Linie dicker + heller, andere dimmen
        for item in self._ind_items:
            item_name = self._ind_item_names.get(id(item))
            current_pen = item.opts.get("pen", pg.mkPen("w"))
            if isinstance(current_pen, pg.QtGui.QPen):
                color = current_pen.color()
                width = current_pen.widthF()
            else:
                color = QColor("#FFFFFF")
                width = 1.5

            if item_name == name:
                # Selektiert: breiter + volle Opazität
                highlight_pen = pg.mkPen(color=color, width=width + 1.5)
                item.setPen(highlight_pen)
                item.setZValue(10)
            else:
                # Nicht selektiert: gedimmt
                dimmed = QColor(color)
                dimmed.setAlphaF(0.3)
                dim_pen = pg.mkPen(color=dimmed, width=width)
                item.setPen(dim_pen)
                item.setZValue(0)

        logger.debug(f"Indikator selektiert: {name} (Delete zum Entfernen)")

    def _deselect_indicator(self) -> None:
        """Hebt die Selektion auf und stellt Original-Darstellung wieder her."""
        if self._selected_indicator is None:
            return
        self._selected_indicator = None

        # Alle Indikatoren neu zeichnen mit Originalfarben
        for item in self._ind_items:
            try:
                item.getViewBox().removeItem(item)
            except Exception:
                pass
        self._ind_items.clear()
        self._ind_item_names.clear()

        for series in self._indicators:
            self._draw_indicator(series)

    def keyPressEvent(self, event) -> None:
        """Delete/Backspace entfernt den selektierten Indikator."""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self._selected_indicator:
                name = self._selected_indicator
                self.remove_indicator(name)
                self.indicatorRemoved.emit(name)
                logger.info(f"Indikator per Tastatur entfernt: {name}")
                return
        super().keyPressEvent(event)

    @staticmethod
    def _split_nan_segments(
        x: np.ndarray, y: np.ndarray
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """Teilt Arrays an NaN-Stellen auf."""
        segments = []
        mask = ~np.isnan(y)
        if not mask.any():
            return segments

        # Zusammenhängende True-Bereiche finden
        changes = np.diff(mask.astype(int))
        starts  = list(np.where(changes == 1)[0] + 1)
        ends    = list(np.where(changes == -1)[0] + 1)

        if mask[0]:
            starts.insert(0, 0)
        if mask[-1]:
            ends.append(len(mask))

        for s, e in zip(starts, ends):
            segments.append((x[s:e], y[s:e]))

        return segments


# ---------------------------------------------------------------------------
# Hilfsfunktionen für Controller
# ---------------------------------------------------------------------------

def compute_sma(bars: list[OHLCVBar], period: int) -> IndicatorSeries:
    """Berechnet SMA und gibt eine IndicatorSeries zurück."""
    closes = np.array([b.close for b in bars], dtype=float)
    sma = np.full_like(closes, np.nan)
    for i in range(period - 1, len(closes)):
        sma[i] = closes[i - period + 1 : i + 1].mean()
    return IndicatorSeries(
        name=f"SMA {period}",
        values=sma,
        panel="main",
    )


def compute_macd(
    bars: list[OHLCVBar],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> list[IndicatorSeries]:
    """Berechnet MACD-Linie, Signal-Linie. Gibt zwei IndicatorSeries zurück."""
    closes = np.array([b.close for b in bars], dtype=float)

    def ema(arr: np.ndarray, period: int) -> np.ndarray:
        result = np.full_like(arr, np.nan)
        k = 2 / (period + 1)
        # Startwert: erster gültiger SMA
        result[period - 1] = arr[:period].mean()
        for i in range(period, len(arr)):
            result[i] = arr[i] * k + result[i - 1] * (1 - k)
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow

    sig_line = np.full_like(macd_line, np.nan)
    first_valid = slow - 1
    sig_line[first_valid + signal - 1] = macd_line[first_valid : first_valid + signal].mean()
    k = 2 / (signal + 1)
    for i in range(first_valid + signal, len(macd_line)):
        sig_line[i] = macd_line[i] * k + sig_line[i - 1] * (1 - k)

    return [
        IndicatorSeries(name="MACD",   values=macd_line, panel="sub", color="#4A90D9"),
        IndicatorSeries(name="Signal", values=sig_line,  panel="sub", color="#F5A623"),
    ]


def compute_roc(bars: list[OHLCVBar], period: int = 10) -> IndicatorSeries:
    """Berechnet Rate of Change."""
    closes = np.array([b.close for b in bars], dtype=float)
    roc = np.full_like(closes, np.nan)
    for i in range(period, len(closes)):
        if closes[i - period] != 0:
            roc[i] = (closes[i] - closes[i - period]) / closes[i - period] * 100
    return IndicatorSeries(
        name=f"ROC {period}",
        values=roc,
        panel="sub",
        color="#9B59B6",
    )


# ---------------------------------------------------------------------------
# Demo / Standalone-Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import random
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Beispieldaten generieren
    bars: list[OHLCVBar] = []
    price = 185.0
    start = date(2023, 1, 2)
    d = start
    while d <= date(2024, 12, 31):
        if d.weekday() < 5:
            o = round(price + random.uniform(-3, 3), 4)
            h = round(o + random.uniform(0, 5), 4)
            l = round(o - random.uniform(0, 5), 4)
            c = round(l + random.uniform(0, h - l), 4)
            price = c
            bars.append(OHLCVBar(
                date=d,
                open=o, high=h, low=l, close=c,
                volume=random.randint(20_000_000, 80_000_000),
                adj_close=c,
            ))
        d += timedelta(days=1)

    widget = ChartWidget()
    widget.setWindowTitle("ChartWidget – Portfolio Manager")
    widget.resize(1200, 700)
    widget.load_data("AAPL", bars)

    # SMA 20 + SMA 50
    widget.add_indicator(compute_sma(widget._bars, 20))
    widget.add_indicator(compute_sma(widget._bars, 50))

    # MACD im Sub-Panel
    for series in compute_macd(widget._bars):
        widget.add_indicator(series)

    widget.show()
    sys.exit(app.exec())
