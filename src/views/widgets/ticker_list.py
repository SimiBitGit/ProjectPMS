
"""
TickerListWidget - src/views/widgets/ticker_list.py
Basiert auf debug_ticker3.py (verifiziert funktionstüchtig)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sys

from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
    QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, Signal, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QAction, QBrush, QColor, QFont

# ---------------------------------------------------------------------------
# Farben
# ---------------------------------------------------------------------------
C_BG       = "#1E2235"
C_BG_ROW   = "#161827"
C_BG_ALT   = "#1A1D2E"
C_BG_SEL   = "#2D3A6B"
C_BORDER   = "#2D3250"
C_TEXT     = "#E8EAED"
C_TEXT_DIM = "#6B7499"
C_ACCENT   = "#5A6FAA"

BADGE_COLORS = {
    "STOCK":     ("#1B3A5C", "#4A9FD4"),
    "ETF":       ("#1B3D2A", "#4ABF7E"),
    "INDEX":     ("#3D2A1B", "#D4844A"),
    "FX":        ("#2A1B3D", "#9B6ED4"),
    "CRYPTO":    ("#3D3A1B", "#D4C44A"),
    "COMMODITY": ("#3A1B2A", "#D44A84"),
    "BOND":      ("#1B3A3A", "#4AD4C4"),
}
BADGE_DEFAULT = ("#2D3250", "#9AA0B4")

# ---------------------------------------------------------------------------
# Datenklasse
# ---------------------------------------------------------------------------
@dataclass
class TickerItem:
    ticker_id:  int
    symbol:     str
    name:       str  = ""
    exchange:   str  = ""
    currency:   str  = ""
    asset_type: str  = "STOCK"
    is_active:  bool = True

# ---------------------------------------------------------------------------
# Spalten
# ---------------------------------------------------------------------------
COLS = ["symbol", "asset_type", "name", "exchange", "currency"]
HDRS = ["Symbol", "Typ",        "Name", "Exchange", "Währung"]
WIDS = [90,       70,           180,    90,         70]

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
class TickerTableModel(QAbstractTableModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[TickerItem] = []

    def load(self, items: list[TickerItem]) -> None:
        self.beginResetModel()
        self._rows = list(items)
        self.endResetModel()

    def add(self, item: TickerItem) -> None:
        n = len(self._rows)
        self.beginInsertRows(QModelIndex(), n, n)
        self._rows.append(item)
        self.endInsertRows()

    def get(self, row: int) -> TickerItem:
        return self._rows[row]

    def set_active(self, row: int, active: bool) -> None:
        self._rows[row].is_active = active
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(COLS)-1))

    def rowCount(self, p=QModelIndex()): return len(self._rows)
    def columnCount(self, p=QModelIndex()): return len(COLS)

    def headerData(self, s, o, role=Qt.DisplayRole):
        if o == Qt.Horizontal and role == Qt.DisplayRole:
            return HDRS[s]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._rows[index.row()]
        key  = COLS[index.column()]
        even = (index.row() % 2 == 0)
        is_type = (index.column() == 1)

        if role == Qt.DisplayRole:
            return str(getattr(item, key) or "")

        if role == Qt.BackgroundRole:
            if not item.is_active:
                return QBrush(QColor("#12141F"))
            if is_type:
                bg, _ = BADGE_COLORS.get(item.asset_type, BADGE_DEFAULT)
                return QBrush(QColor(bg))
            return QBrush(QColor(C_BG_ROW if even else C_BG_ALT))

        if role == Qt.ForegroundRole:
            if not item.is_active:
                return QBrush(QColor(C_TEXT_DIM))
            if is_type:
                _, fg = BADGE_COLORS.get(item.asset_type, BADGE_DEFAULT)
                return QBrush(QColor(fg))
            if key == "symbol":
                return QBrush(QColor(C_TEXT))
            return QBrush(QColor(C_TEXT_DIM))

        if role == Qt.FontRole:
            f = QFont("JetBrains Mono", 10)
            if key == "symbol":
                f.setPointSize(11)
                f.setBold(True)
            elif is_type:
                f.setBold(True)
            return f

        if role == Qt.UserRole:
            return item

        return None

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

# ---------------------------------------------------------------------------
# Add-Dialog
# ---------------------------------------------------------------------------
class AddTickerDialog(QDialog):

    ASSET_TYPES = ["STOCK", "ETF", "INDEX", "FX", "CRYPTO", "COMMODITY", "BOND"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Neuen Ticker hinzufügen")
        self.setMinimumWidth(340)

        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(8)

        self.edit_symbol = QLineEdit()
        self.edit_symbol.setPlaceholderText("z.B. AAPL")

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("z.B. Apple Inc.")

        self.combo_type = QComboBox()
        self.combo_type.addItems(self.ASSET_TYPES)

        self.edit_exchange = QLineEdit()
        self.edit_exchange.setPlaceholderText("z.B. NASDAQ")

        self.edit_currency = QLineEdit()
        self.edit_currency.setPlaceholderText("z.B. USD")
        self.edit_currency.setMaxLength(3)

        form.addRow("Symbol *",  self.edit_symbol)
        form.addRow("Name",      self.edit_name)
        form.addRow("Typ *",     self.combo_type)
        form.addRow("Exchange",  self.edit_exchange)
        form.addRow("Währung",   self.edit_currency)
        lay.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _validate(self):
        if not self.edit_symbol.text().strip():
            QMessageBox.warning(self, "Fehler", "Symbol ist ein Pflichtfeld.")
            return
        self.accept()

    def get_ticker(self) -> TickerItem:
        return TickerItem(
            ticker_id  = -1,
            symbol     = self.edit_symbol.text().strip().upper(),
            name       = self.edit_name.text().strip(),
            exchange   = self.edit_exchange.text().strip().upper(),
            currency   = self.edit_currency.text().strip().upper(),
            asset_type = self.combo_type.currentText(),
            is_active  = True,
        )

# ---------------------------------------------------------------------------
# Haupt-Widget
# ---------------------------------------------------------------------------
class TickerListWidget(QWidget):
    """
    Signale:
        tickerSelected(TickerItem)
        tickerAdded(TickerItem)
        tickerDeactivated(int)
        tickerActivated(int)
    """

    tickerSelected    = Signal(object)
    tickerAdded       = Signal(object)
    tickerDeactivated = Signal(int)
    tickerActivated   = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(460)
        self._type_filter: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background:{C_BG}; border-bottom:1px solid {C_BORDER};")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(10, 10, 10, 8)
        hl.setSpacing(6)

        title = QLabel("Ticker")
        title.setStyleSheet(f"color:{C_TEXT}; font-size:13px; font-weight:700; font-family:'JetBrains Mono',monospace;")
        hl.addWidget(title)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Suchen …")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:#12141F; color:{C_TEXT};
                border:1px solid {C_BORDER}; border-radius:4px;
                padding:5px 8px; font-size:12px;
            }}
            QLineEdit:focus {{ border-color:{C_ACCENT}; }}
        """)
        hl.addWidget(self._search)

        # Filter-Buttons
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        filter_row.setContentsMargins(0, 0, 0, 0)
        self._filter_btns: list[tuple[Optional[str], QPushButton]] = []
        for label, ftype in [("Alle", None), ("STOCK", "STOCK"), ("ETF", "ETF"), ("INDEX", "INDEX"), ("FX", "FX")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C_TEXT_DIM};
                    border:1px solid {C_BORDER}; border-radius:3px;
                    padding:0 8px; font-size:10px; }}
                QPushButton:hover {{ background:{C_BORDER}; color:{C_TEXT}; }}
                QPushButton:checked {{ background:{C_BG_SEL}; color:{C_TEXT}; border-color:{C_ACCENT}; }}
            """)
            btn.setProperty("ftype", ftype)
            btn.clicked.connect(self._on_filter_btn)
            filter_row.addWidget(btn)
            self._filter_btns.append((ftype, btn))
        self._filter_btns[0][1].setChecked(True)  # "Alle" vorselektiert
        filter_row.addStretch()
        hl.addLayout(filter_row)
        root.addWidget(header)

        # Model + Proxy
        self._model = TickerTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        # Tabelle
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setStyleSheet(f"""
            QTableView {{
                background:{C_BG_ROW}; border:none;
                gridline-color:transparent;
                selection-background-color:{C_BG_SEL};
                selection-color:{C_TEXT};
            }}
            QTableView QHeaderView::section {{
                background:{C_BG}; color:{C_TEXT_DIM};
                font-size:10px; font-weight:700;
                padding:4px 6px; border:none;
                border-bottom:1px solid {C_BORDER};
            }}
            QScrollBar:vertical {{ width:6px; background:{C_BG}; }}
            QScrollBar::handle:vertical {{ background:{C_BORDER}; border-radius:3px; }}
        """)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.horizontalHeader().setStretchLastSection(False)

        for i, w in enumerate(WIDS):
            self._table.setColumnWidth(i, w)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

        root.addWidget(self._table, 1)

        # Footer
        footer = QWidget()
        footer.setStyleSheet(f"background:{C_BG}; border-top:1px solid {C_BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(10, 6, 10, 6)
        self._lbl_count = QLabel("0 Ticker")
        self._lbl_count.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        fl.addWidget(self._lbl_count)
        fl.addStretch()
        btn_add = QPushButton("＋ Hinzufügen")
        btn_add.setFixedHeight(26)
        btn_add.setStyleSheet(f"""
            QPushButton {{ background:{C_ACCENT}; color:{C_TEXT}; border:none;
                border-radius:4px; padding:0 12px; font-size:12px; }}
            QPushButton:hover {{ background:#6A7FBF; }}
        """)
        btn_add.clicked.connect(self._on_add)
        fl.addWidget(btn_add)
        root.addWidget(footer)

        # Signals
        self._search.textChanged.connect(self._on_search)
        self._table.selectionModel().currentRowChanged.connect(self._on_selection)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._model.modelReset.connect(self._update_count)
        self._model.rowsInserted.connect(self._update_count)

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def load_tickers(self, items: list[TickerItem]) -> None:
        self._model.load(items)
        self._proxy.sort(0, Qt.AscendingOrder)
        self._update_count()

    def add_ticker(self, item: TickerItem) -> None:
        self._model.add(item)
        self._update_count()

    def select_ticker(self, symbol: str) -> None:
        for row in range(self._proxy.rowCount()):
            if self._proxy.index(row, 0).data() == symbol:
                self._table.selectRow(row)
                break

    # ------------------------------------------------------------------
    # Interne Slots
    # ------------------------------------------------------------------

    def _on_search(self, text: str) -> None:
        if self._type_filter:
            # Typ-Filter aktiv: nur in Spalte 1 filtern
            pass
        else:
            self._proxy.setFilterKeyColumn(-1)
            self._proxy.setFilterFixedString(text)
        self._update_count()

    def _on_filter_btn(self) -> None:
        btn = self.sender()
        ftype = btn.property("ftype")
        self._type_filter = ftype
        # Buttons aktualisieren
        for ft, b in self._filter_btns:
            b.setChecked(ft == ftype)
        # Filter anwenden
        if ftype:
            self._proxy.setFilterKeyColumn(1)
            self._proxy.setFilterFixedString(ftype)
        else:
            self._proxy.setFilterKeyColumn(-1)
            self._proxy.setFilterFixedString(self._search.text())
        self._update_count()

    def _on_selection(self, current, _prev) -> None:
        if not current.isValid():
            return
        src = self._proxy.mapToSource(current)
        self.tickerSelected.emit(self._model.get(src.row()))

    def _on_add(self) -> None:
        dlg = AddTickerDialog(self)
        if dlg.exec() == QDialog.Accepted:
            item = dlg.get_ticker()
            self.tickerAdded.emit(item)
            self._model.add(item)
            self._update_count()
            self.select_ticker(item.symbol)

    def _on_context_menu(self, pos) -> None:
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
        src  = self._proxy.mapToSource(idx)
        item = self._model.get(src.row())

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:{C_BG}; color:{C_TEXT};
                border:1px solid {C_BORDER}; padding:4px 0; }}
            QMenu::item {{ padding:6px 20px; font-size:12px; }}
            QMenu::item:selected {{ background:{C_BG_SEL}; }}
            QMenu::separator {{ height:1px; background:{C_BORDER}; margin:3px 0; }}
        """)

        if item.is_active:
            act_toggle = QAction("⊘  Deaktivieren", self)
            act_toggle.triggered.connect(lambda: self._toggle(src.row(), item, False))
        else:
            act_toggle = QAction("✓  Aktivieren", self)
            act_toggle.triggered.connect(lambda: self._toggle(src.row(), item, True))

        act_info = QAction("ℹ  Details", self)
        act_info.triggered.connect(lambda: QMessageBox.information(
            self, item.symbol,
            f"Symbol:   {item.symbol}\nName:     {item.name or '-'}\n"
            f"Typ:      {item.asset_type}\nExchange: {item.exchange or '-'}\n"
            f"Währung:  {item.currency or '-'}\nAktiv:    {'Ja' if item.is_active else 'Nein'}"
        ))
        menu.addAction(act_info)
        menu.addSeparator()
        menu.addAction(act_toggle)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _toggle(self, row: int, item: TickerItem, active: bool) -> None:
        self._model.set_active(row, active)
        if active:
            self.tickerActivated.emit(item.ticker_id)
        else:
            self.tickerDeactivated.emit(item.ticker_id)

    def _update_count(self) -> None:
        shown = self._proxy.rowCount()
        total = self._model.rowCount()
        self._lbl_count.setText(
            f"{total} Ticker" if shown == total else f"{shown} / {total} Ticker"
        )

# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    sample = [
        TickerItem(1,  "AAPL",   "Apple Inc.",                "NASDAQ", "USD", "STOCK",     True),
        TickerItem(2,  "MSFT",   "Microsoft Corporation",     "NASDAQ", "USD", "STOCK",     True),
        TickerItem(3,  "GOOGL",  "Alphabet Inc.",             "NASDAQ", "USD", "STOCK",     True),
        TickerItem(4,  "TSLA",   "Tesla Inc.",                "NASDAQ", "USD", "STOCK",     True),
        TickerItem(5,  "SPY",    "SPDR S&P 500 ETF",          "NYSE",   "USD", "ETF",       True),
        TickerItem(6,  "QQQ",    "Invesco QQQ Trust",         "NASDAQ", "USD", "ETF",       True),
        TickerItem(7,  "SPX",    "S&P 500 Index",             "",       "USD", "INDEX",     True),
        TickerItem(8,  "EURUSD", "Euro / US Dollar",          "FOREX",  "USD", "FX",        True),
        TickerItem(9,  "BTCUSD", "Bitcoin / US Dollar",       "CRYPTO", "USD", "CRYPTO",    True),
        TickerItem(10, "NVDA",   "NVIDIA Corporation",        "NASDAQ", "USD", "STOCK",     False),
        TickerItem(11, "GLD",    "SPDR Gold Shares",          "NYSE",   "USD", "COMMODITY", True),
        TickerItem(12, "TLT",    "iShares 20+ Year Treasury", "NASDAQ", "USD", "BOND",      True),
    ]

    w = TickerListWidget()
    w.setWindowTitle("TickerListWidget – Portfolio Manager")
    w.resize(500, 700)
    w.load_tickers(sample)
    w.tickerSelected.connect(lambda t: print(f"[SELECT] {t.symbol} – {t.name}"))
    w.tickerAdded.connect(lambda t: print(f"[ADD] {t.symbol}"))
    w.tickerDeactivated.connect(lambda tid: print(f"[DEACTIVATE] id={tid}"))
    w.show()
    sys.exit(app.exec())
