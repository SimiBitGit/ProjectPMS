"""
DataTableWidget - Editierbare Tabelle für Marktdaten
src/views/widgets/data_table.py

Features:
- Anzeige von OHLCV-Daten mit adj_close und source
- Inline-Editing mit Audit-Log (via MarketDataRepository.update_with_log)
- Farbliche Hervorhebung manuell editierter Zellen
- Kontextmenü (Bearbeiten / Änderung rückgängig / Bearbeitung-Log anzeigen)
- Kopieren, Exportieren (CSV)
- Paginierung (konfigurierbare Zeilenzahl)
- Statuszeile: Anzahl Zeilen, letzte Änderung
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from PySide6.QtCore import (
    Qt,
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QKeySequence,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Spalten-Definition
# ---------------------------------------------------------------------------

DATE_COL = 0  # Index der Datum-Spalte

COLUMNS = [
    ("date",      "Datum",      False),   # (key, label, editable)
    ("open",      "Open",       True),
    ("high",      "High",       True),
    ("low",       "Low",        True),
    ("close",     "Close",      True),
    ("volume",    "Volume",     True),
    ("adj_close", "Adj. Close", True),
    ("source",    "Quelle",     False),
]

COL_KEYS    = [c[0] for c in COLUMNS]
COL_LABELS  = [c[1] for c in COLUMNS]
COL_EDITABLE = [c[2] for c in COLUMNS]

# Farben
COLOR_EDITED      = QColor("#FFF3CD")   # Gedämpftes Gelb – manuell bearbeitet
COLOR_EDITED_DARK = QColor("#6B5900")
COLOR_HEADER_BG   = QColor("#1E2235")
COLOR_HEADER_FG   = QColor("#E8EAED")
COLOR_POS         = QColor("#1B5E20")   # Close > Open
COLOR_NEG         = QColor("#B71C1C")   # Close < Open
COLOR_EVEN        = QColor("#FAFAFA")
COLOR_ODD         = QColor("#F2F4F8")


# ---------------------------------------------------------------------------
# Daten-Modell
# ---------------------------------------------------------------------------

class MarketDataTableModel(QAbstractTableModel):
    """
    Qt-Modell für eine Liste von Marktdaten-Dicts.

    Erwartetes Format eines Eintrags:
    {
        "data_id":   int,
        "date":      date | str,
        "open":      Decimal | float | None,
        "high":      Decimal | float | None,
        "low":       Decimal | float | None,
        "close":     Decimal | float | None,
        "volume":    int | None,
        "adj_close": Decimal | float | None,
        "source":    str,
        "_edited":   set[str],   # Welche Felder manuell verändert wurden
    }
    """

    # Emittiert (data_id, field, old_value, new_value, reason)
    dataEdited = Signal(int, str, object, object, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def load(self, rows: list[dict]) -> None:
        """Lädt eine neue Liste von Zeilen und aktualisiert die View."""
        self.beginResetModel()
        self._rows = [self._normalize(r) for r in rows]
        self.endResetModel()

    def row_count(self) -> int:
        return len(self._rows)

    def get_row(self, row: int) -> dict:
        return self._rows[row]

    # ------------------------------------------------------------------
    # Qt-Interface
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return COL_LABELS[section]
            if role == Qt.FontRole:
                f = QFont()
                f.setBold(True)
                return f
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return section + 1
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        key = COL_KEYS[index.column()]
        value = row.get(key)

        if role == Qt.DisplayRole:
            return self._format_value(key, value)

        if role == Qt.EditRole:
            if value is None:
                return ""
            return str(value)

        if role == Qt.BackgroundRole:
            # Manuell editierte Zellen
            if key in row.get("_edited", set()):
                return QBrush(COLOR_EDITED)
            # Alternating row colors
            return QBrush(COLOR_EVEN if index.row() % 2 == 0 else COLOR_ODD)

        if role == Qt.ForegroundRole:
            # Close-Farbe relativ zu Open
            if key == "close":
                o = row.get("open")
                c = row.get("close")
                if o is not None and c is not None:
                    try:
                        if float(c) > float(o):
                            return QBrush(COLOR_POS)
                        if float(c) < float(o):
                            return QBrush(COLOR_NEG)
                    except (TypeError, ValueError):
                        pass

        if role == Qt.TextAlignmentRole:
            if key in ("open", "high", "low", "close", "adj_close", "volume"):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        if role == Qt.ToolTipRole:
            if key in row.get("_edited", set()):
                return "Manuell bearbeitet"
            return None

        # UserRole liefert sortierfähige Rohwerte (Datum als ISO-String)
        if role == Qt.UserRole:
            if key == "date":
                d = row.get("date")
                if isinstance(d, date):
                    return d.isoformat()
                return str(d) if d else ""
            return value

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False

        row = self._rows[index.row()]
        key = COL_KEYS[index.column()]

        if not COL_EDITABLE[index.column()]:
            return False

        old_raw = row.get(key)
        try:
            new_raw = self._parse_value(key, value)
        except (ValueError, InvalidOperation):
            return False

        if old_raw == new_raw:
            return False

        # Grund erfragen
        reason, ok = _ask_edit_reason(self.parent())
        if not ok:
            return False

        row[key] = new_raw
        row.setdefault("_edited", set()).add(key)

        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.BackgroundRole])
        self.dataEdited.emit(
            row["data_id"], key, old_raw, new_raw, reason
        )
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if COL_EDITABLE[index.column()]:
            base |= Qt.ItemIsEditable
        return base

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(row: dict) -> dict:
        r = dict(row)
        r.setdefault("_edited", set())
        # Datum normalisieren
        d = r.get("date")
        if isinstance(d, str):
            try:
                r["date"] = date.fromisoformat(d)
            except ValueError:
                pass
        return r

    @staticmethod
    def _format_value(key: str, value: Any) -> str:
        if value is None:
            return ""
        if key == "date":
            if isinstance(value, date):
                return value.strftime("%d.%m.%Y")
            return str(value)
        if key == "volume":
            try:
                return f"{int(value):,}".replace(",", ".")
            except (TypeError, ValueError):
                return str(value)
        if key in ("open", "high", "low", "close", "adj_close"):
            try:
                return f"{float(value):.4f}"
            except (TypeError, ValueError):
                return str(value)
        return str(value)

    @staticmethod
    def _parse_value(key: str, raw: str) -> Any:
        raw = raw.strip()
        if key == "volume":
            # Tausender-Trennzeichen tolerieren
            return int(raw.replace(".", "").replace(",", ""))
        if key in ("open", "high", "low", "close", "adj_close"):
            return Decimal(raw.replace(",", "."))
        return raw


# ---------------------------------------------------------------------------
# Grund-Dialog (für Audit-Log)
# ---------------------------------------------------------------------------

def _ask_edit_reason(parent: Optional[QWidget]) -> tuple[str, bool]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Bearbeitungsgrund")
    dlg.setMinimumWidth(380)

    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Bitte einen Grund für die Änderung angeben:"))

    presets = QComboBox()
    presets.addItems([
        "Datenkorrektur (Fehler in Quelle)",
        "Split-Anpassung",
        "Dividenden-Bereinigung",
        "Sonstiges",
    ])
    lay.addWidget(presets)

    edit = QLineEdit()
    edit.setPlaceholderText("Oder eigenen Grund eingeben …")
    lay.addWidget(edit)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    lay.addWidget(buttons)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)

    if dlg.exec() != QDialog.Accepted:
        return "", False

    reason = edit.text().strip() or presets.currentText()
    return reason, True


# ---------------------------------------------------------------------------
# Edit-Log Dialog
# ---------------------------------------------------------------------------

class EditLogDialog(QDialog):
    """Zeigt den Audit-Trail für eine einzelne Zeile."""

    def __init__(self, data_id: int, log_entries: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bearbeitungs-Log  –  data_id {data_id}")
        self.resize(600, 340)

        lay = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Courier New", 10))

        lines = []
        for e in log_entries:
            ts = e.get("edited_at", "–")
            field = e.get("field_name", "–")
            old = e.get("old_value", "–")
            new = e.get("new_value", "–")
            reason = e.get("edit_reason", "–")
            lines.append(
                f"[{ts}]  {field}\n"
                f"  Alt: {old}\n"
                f"  Neu: {new}\n"
                f"  Grund: {reason}\n"
                f"{'─' * 60}"
            )

        text.setPlainText("\n".join(lines) if lines else "Keine Einträge.")
        lay.addWidget(text)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


# ---------------------------------------------------------------------------
# Haupt-Widget
# ---------------------------------------------------------------------------

class DataTableWidget(QWidget):
    """
    Vollständige editierbare Tabelle für End-of-Day Marktdaten.

    Signale
    -------
    dataEdited(data_id, field, old_value, new_value, reason)
        Wird ausgelöst, wenn der Nutzer einen Wert ändert.
        Der Controller / Repository soll daraufhin update_with_log() aufrufen.

    editLogRequested(data_id)
        Wird ausgelöst, wenn der Nutzer das Edit-Log für eine Zeile anfordert.
        Der Controller soll den Log laden und show_edit_log() aufrufen.
    """

    dataEdited       = Signal(int, str, object, object, str)
    editLogRequested = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setMinimumSize(900, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar.setStyleSheet("""
            #toolbar {
                background: #1E2235;
                border-bottom: 1px solid #2D3250;
            }
        """)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(8)

        self._lbl_ticker = QLabel("–")
        self._lbl_ticker.setStyleSheet(
            "color: #E8EAED; font-size: 15px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
        )
        tl.addWidget(self._lbl_ticker)

        self._lbl_range = QLabel()
        self._lbl_range.setStyleSheet("color: #9AA0B4; font-size: 12px;")
        tl.addWidget(self._lbl_range)

        tl.addStretch()

        # Suchfeld
        self._search = QLineEdit()
        self._search.setPlaceholderText("Datum suchen …")
        self._search.setFixedWidth(180)
        self._search.setStyleSheet("""
            QLineEdit {
                background: #2D3250;
                color: #E8EAED;
                border: 1px solid #3D4470;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
        """)
        tl.addWidget(self._search)

        # Export-Button
        btn_export = self._make_toolbar_btn("⬇ CSV Export")
        btn_export.clicked.connect(self._export_csv)
        tl.addWidget(btn_export)

        root.addWidget(toolbar)

        # ── Tabelle ───────────────────────────────────────────────────────
        self._model = MarketDataTableModel(self)

        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterKeyColumn(0)   # Datum-Spalte
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setSortRole(Qt.UserRole)  # ISO-Datum für korrekte Sortierung

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setObjectName("marketTable")
        self._table.setStyleSheet("""
            QTableView#marketTable {
                background: #FFFFFF;
                gridline-color: #E4E7F0;
                font-size: 13px;
                font-family: 'JetBrains Mono', 'Courier New', monospace;
                selection-background-color: #D0D8FF;
                selection-color: #1E2235;
                border: none;
            }
            QTableView#marketTable QHeaderView::section {
                background: #1E2235;
                color: #E8EAED;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #2D3250;
            }
            QTableView#marketTable QHeaderView::section:horizontal:last {
                border-right: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #F0F2F8;
            }
            QScrollBar::handle:vertical {
                background: #BCC3DB;
                border-radius: 4px;
            }
        """)

        # Einstellungen
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.verticalHeader().setVisible(True)
        self._table.verticalHeader().setStyleSheet(
            "background: #F5F6FA; color: #9AA0B4; font-size: 11px;"
        )

        # Spaltenbreiten
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        hh.setSortIndicator(0, Qt.DescendingOrder)  # Jüngstes Datum zuoberst
        col_widths = [110, 90, 90, 90, 90, 110, 95, 80]
        for i, w in enumerate(col_widths):
            self._table.setColumnWidth(i, w)

        root.addWidget(self._table, 1)

        # ── Statuszeile ───────────────────────────────────────────────────
        status_bar = QWidget()
        status_bar.setObjectName("statusBar")
        status_bar.setStyleSheet("""
            #statusBar {
                background: #F0F2F8;
                border-top: 1px solid #DDE1EE;
            }
        """)
        sl = QHBoxLayout(status_bar)
        sl.setContentsMargins(12, 4, 12, 4)

        self._lbl_count = QLabel("0 Datensätze")
        self._lbl_count.setStyleSheet("color: #5A6282; font-size: 12px;")
        sl.addWidget(self._lbl_count)

        self._lbl_edited_count = QLabel()
        self._lbl_edited_count.setStyleSheet(
            "color: #B07B00; font-size: 12px; font-weight: 600;"
        )
        sl.addWidget(self._lbl_edited_count)

        sl.addStretch()

        self._lbl_last_change = QLabel()
        self._lbl_last_change.setStyleSheet("color: #9AA0B4; font-size: 11px;")
        sl.addWidget(self._lbl_last_change)

        root.addWidget(status_bar)

        # Keyboard-Shortcuts
        QShortcut(QKeySequence("Ctrl+C"), self._table, self._copy_selection)

    def _make_toolbar_btn(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setStyleSheet("""
            QPushButton {
                background: #2D3250;
                color: #E8EAED;
                border: 1px solid #3D4470;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #3D4470;
            }
            QPushButton:pressed {
                background: #1E2235;
            }
        """)
        return btn

    # ------------------------------------------------------------------
    # Signal-Verbindungen
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._model.dataEdited.connect(self._on_data_edited)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._search.textChanged.connect(self._proxy.setFilterFixedString)
        self._model.modelReset.connect(self._update_status)
        self._model.dataChanged.connect(self._update_status)

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def load_data(self, ticker_symbol: str, rows: list[dict]) -> None:
        """
        Lädt Marktdaten für einen Ticker.

        Parameters
        ----------
        ticker_symbol : str
            Wird in der Toolbar angezeigt (z. B. 'AAPL').
        rows : list[dict]
            Liste von Daten-Dicts (siehe MarketDataTableModel-Docstring).
        """
        self._model.load(rows)
        self._lbl_ticker.setText(ticker_symbol)
        self._update_date_range(rows)
        self._update_status()
        self._table.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        self._proxy.sort(0, Qt.DescendingOrder)  # Jüngstes Datum zuoberst

    def show_edit_log(self, data_id: int, log_entries: list[dict]) -> None:
        """Öffnet den Audit-Log-Dialog für data_id."""
        dlg = EditLogDialog(data_id, log_entries, self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Interne Methoden
    # ------------------------------------------------------------------

    def _update_date_range(self, rows: list[dict]) -> None:
        if not rows:
            self._lbl_range.setText("")
            return
        dates = [r.get("date") for r in rows if r.get("date")]
        if dates:
            d_min = min(dates)
            d_max = max(dates)
            fmt = lambda d: d.strftime("%d.%m.%Y") if isinstance(d, date) else str(d)
            self._lbl_range.setText(f"{fmt(d_min)}  –  {fmt(d_max)}")

    def _update_status(self) -> None:
        total = self._model.row_count()
        self._lbl_count.setText(f"{total:,} Datensätze".replace(",", "."))

        edited = sum(
            1 for r in [self._model.get_row(i) for i in range(total)]
            if r.get("_edited")
        )
        if edited:
            self._lbl_edited_count.setText(f"  ·  {edited} manuell bearbeitet")
        else:
            self._lbl_edited_count.setText("")

    @Slot(int, str, object, object, str)
    def _on_data_edited(
        self,
        data_id: int,
        field: str,
        old_value: object,
        new_value: object,
        reason: str,
    ) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._lbl_last_change.setText(f"Letzte Änderung: {ts}")
        self.dataEdited.emit(data_id, field, old_value, new_value, reason)
        logger.info(
            "Manuell bearbeitet: data_id=%s  field=%s  %r → %r  (%s)",
            data_id, field, old_value, new_value, reason,
        )

    # ------------------------------------------------------------------
    # Kontextmenü
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return

        src_idx = self._proxy.mapToSource(idx)
        row_data = self._model.get_row(src_idx.row())
        data_id = row_data.get("data_id")

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1E2235;
                color: #E8EAED;
                border: 1px solid #3D4470;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 13px;
            }
            QMenu::item:selected {
                background: #3D4470;
            }
            QMenu::separator {
                height: 1px;
                background: #2D3250;
                margin: 3px 0;
            }
        """)

        act_edit = QAction("✏  Zelle bearbeiten", self)
        act_edit.triggered.connect(lambda: self._table.edit(idx))
        menu.addAction(act_edit)

        menu.addSeparator()

        act_copy = QAction("⧉  Zeile kopieren", self)
        act_copy.triggered.connect(self._copy_selection)
        menu.addAction(act_copy)

        act_log = QAction("📋  Bearbeitungs-Log anzeigen", self)
        act_log.triggered.connect(lambda: self.editLogRequested.emit(data_id))
        menu.addAction(act_log)

        menu.addSeparator()

        act_export = QAction("⬇  Als CSV exportieren", self)
        act_export.triggered.connect(self._export_csv)
        menu.addAction(act_export)

        menu.exec(self._table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Clipboard & Export
    # ------------------------------------------------------------------

    def _copy_selection(self) -> None:
        indexes = self._table.selectedIndexes()
        if not indexes:
            return

        rows_dict: dict[int, list] = {}
        for idx in sorted(indexes, key=lambda i: (i.row(), i.column())):
            rows_dict.setdefault(idx.row(), []).append(
                self._proxy.data(idx, Qt.DisplayRole) or ""
            )

        text = "\n".join("\t".join(cells) for cells in rows_dict.values())
        QApplication.clipboard().setText(text)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV exportieren", "", "CSV-Dateien (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(COL_LABELS)
                for row_idx in range(self._proxy.rowCount()):
                    row_data = []
                    for col_idx in range(self._proxy.columnCount()):
                        idx = self._proxy.index(row_idx, col_idx)
                        row_data.append(
                            self._proxy.data(idx, Qt.DisplayRole) or ""
                        )
                    writer.writerow(row_data)

            QMessageBox.information(
                self, "Export erfolgreich",
                f"Daten wurden exportiert nach:\n{path}"
            )
        except OSError as e:
            QMessageBox.critical(self, "Fehler beim Export", str(e))


# ---------------------------------------------------------------------------
# Demo / Standalone-Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import random

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Beispieldaten generieren
    base_close = 185.0
    sample_rows = []
    for i in range(120):
        d = date(2024, 1, 1)
        from datetime import timedelta
        d = date(2024, 1, 1) + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        o = round(base_close + random.uniform(-3, 3), 4)
        h = round(o + random.uniform(0, 4), 4)
        l = round(o - random.uniform(0, 4), 4)
        c = round(l + random.uniform(0, h - l), 4)
        base_close = c
        sample_rows.append({
            "data_id":   i + 1,
            "date":      d,
            "open":      Decimal(str(o)),
            "high":      Decimal(str(h)),
            "low":       Decimal(str(l)),
            "close":     Decimal(str(c)),
            "volume":    random.randint(20_000_000, 80_000_000),
            "adj_close": Decimal(str(c)),
            "source":    "eodhd",
            "_edited":   set(),
        })

    widget = DataTableWidget()
    widget.setWindowTitle("DataTableWidget – Portfolio Manager")
    widget.resize(1100, 650)

    widget.load_data("AAPL", sample_rows)

    # Signal-Demo
    def on_edited(data_id, field, old, new, reason):
        print(f"[EDIT] data_id={data_id}  {field}: {old!r} → {new!r}  ({reason})")

    widget.dataEdited.connect(on_edited)
    widget.editLogRequested.connect(
        lambda did: print(f"[LOG REQUEST] data_id={did}")
    )

    widget.show()
    sys.exit(app.exec())
