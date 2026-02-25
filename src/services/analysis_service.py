# src/services/analysis_service.py
"""
Analysis-Service — Berechnung und Persistierung von Indikatoren.

Wrapper über die Berechnungsfunktionen aus chart_widget.py.
Persistiert Ergebnisse in der processed_data-Tabelle via ProcessedDataRepository.

Usage:
    service = AnalysisService(session)
    bars = service.load_bars(ticker_id, start_date, end_date)
    series = service.compute_and_store_sma(ticker_id, bars, period=20)
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from src.database.market_data_repository import MarketDataRepository
from src.database.processed_data_repository import ProcessedDataRepository
from src.database.ticker_repository import TickerRepository
from src.models.processed_data import ProcessedData
from src.views.widgets.chart_widget import (
    IndicatorSeries,
    OHLCVBar,
    compute_macd,
    compute_roc,
    compute_sma,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisService:
    """
    Service-Schicht für Indikator-Berechnungen.

    Verantwortlichkeiten:
    - Laden von OHLCVBars aus der DB
    - Berechnung via compute_sma / compute_macd / compute_roc
    - Persistierung in processed_data (mit delete-before-insert)
    - Laden gespeicherter Indikatoren als IndicatorSeries
    """

    def __init__(self, session: Session):
        self._session = session
        self._market_repo = MarketDataRepository(session)
        self._processed_repo = ProcessedDataRepository(session)
        self._ticker_repo = TickerRepository(session)

    # ──────────────────────────────────────────
    #  Bars laden
    # ──────────────────────────────────────────

    def load_bars(
        self,
        ticker_id: int,
        start_date: date,
        end_date: date,
    ) -> list[OHLCVBar]:
        """Lädt Marktdaten als OHLCVBar-Liste aus der DB."""
        records = self._market_repo.get_by_ticker_and_daterange(
            ticker_id, start_date, end_date
        )
        return [
            OHLCVBar(
                date=r.date,
                open=float(r.open) if r.open else 0.0,
                high=float(r.high) if r.high else 0.0,
                low=float(r.low) if r.low else 0.0,
                close=float(r.close) if r.close else 0.0,
                volume=float(r.volume) if r.volume else 0.0,
                adj_close=float(r.adj_close) if r.adj_close else 0.0,
            )
            for r in records
        ]

    def resolve_ticker_id(self, symbol: str) -> Optional[int]:
        """Symbol → ticker_id auflösen."""
        ticker = self._ticker_repo.get_by_symbol(symbol)
        return ticker.ticker_id if ticker else None

    # ──────────────────────────────────────────
    #  Berechnung + Persistierung
    # ──────────────────────────────────────────

    def compute_and_store_sma(
        self,
        ticker_id: int,
        bars: list[OHLCVBar],
        period: int = 20,
    ) -> IndicatorSeries:
        """Berechnet SMA, speichert in DB und gibt IndicatorSeries zurück."""
        series = compute_sma(bars, period)
        indicator_name = f"SMA_{period}"
        params = {"period": period, "method": "simple"}

        self._persist_single_series(ticker_id, bars, series, indicator_name, params)
        logger.info(f"SMA({period}) berechnet und gespeichert für ticker_id={ticker_id}")
        return series

    def compute_and_store_ema(
        self,
        ticker_id: int,
        bars: list[OHLCVBar],
        period: int = 20,
    ) -> IndicatorSeries:
        """Berechnet EMA, speichert in DB und gibt IndicatorSeries zurück."""
        # EMA-Berechnung (gleiche Logik wie in compute_macd intern)
        closes = np.array([b.close for b in bars], dtype=float)
        ema_values = np.full_like(closes, np.nan)
        k = 2 / (period + 1)
        if len(closes) >= period:
            ema_values[period - 1] = closes[:period].mean()
            for i in range(period, len(closes)):
                ema_values[i] = closes[i] * k + ema_values[i - 1] * (1 - k)

        series = IndicatorSeries(
            name=f"EMA {period}",
            values=ema_values,
            panel="main",
            color="#1ABC9C",
        )

        indicator_name = f"EMA_{period}"
        params = {"period": period, "method": "exponential"}
        self._persist_single_series(ticker_id, bars, series, indicator_name, params)
        logger.info(f"EMA({period}) berechnet und gespeichert für ticker_id={ticker_id}")
        return series

    def compute_and_store_macd(
        self,
        ticker_id: int,
        bars: list[OHLCVBar],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> list[IndicatorSeries]:
        """Berechnet MACD + Signal, speichert in DB und gibt IndicatorSeries-Liste zurück."""
        series_list = compute_macd(bars, fast, slow, signal)
        indicator_name = f"MACD_{fast}_{slow}_{signal}"
        params = {"fast": fast, "slow": slow, "signal": signal}

        self._persist_macd(ticker_id, bars, series_list, indicator_name, params)
        logger.info(
            f"MACD({fast},{slow},{signal}) berechnet und gespeichert für ticker_id={ticker_id}"
        )
        return series_list

    def compute_and_store_roc(
        self,
        ticker_id: int,
        bars: list[OHLCVBar],
        period: int = 10,
    ) -> IndicatorSeries:
        """Berechnet ROC, speichert in DB und gibt IndicatorSeries zurück."""
        series = compute_roc(bars, period)
        indicator_name = f"ROC_{period}"
        params = {"period": period}

        self._persist_single_series(ticker_id, bars, series, indicator_name, params)
        logger.info(f"ROC({period}) berechnet und gespeichert für ticker_id={ticker_id}")
        return series

    # ──────────────────────────────────────────
    #  Gespeicherte Indikatoren laden
    # ──────────────────────────────────────────

    def load_stored_indicator(
        self,
        ticker_id: int,
        indicator_name: str,
        start_date: date,
        end_date: date,
    ) -> Optional[IndicatorSeries]:
        """
        Lädt einen gespeicherten Indikator aus processed_data
        und konvertiert ihn zu einer IndicatorSeries.
        """
        records = self._processed_repo.get_by_ticker_indicator_daterange(
            ticker_id, indicator_name, start_date, end_date
        )
        if not records:
            return None

        values = np.array(
            [float(r.value) if r.value is not None else np.nan for r in records],
            dtype=float,
        )

        # Panel-Zuordnung ableiten
        panel = "sub" if indicator_name.startswith(("MACD", "ROC")) else "main"

        return IndicatorSeries(
            name=indicator_name.replace("_", " "),
            values=values,
            panel=panel,
        )

    def get_available_indicators(self, ticker_id: int) -> list[str]:
        """Gibt alle gespeicherten Indikatoren für einen Ticker zurück."""
        return self._processed_repo.get_available_indicators(ticker_id)

    # ──────────────────────────────────────────
    #  Persistierung (intern)
    # ──────────────────────────────────────────

    def _persist_single_series(
        self,
        ticker_id: int,
        bars: list[OHLCVBar],
        series: IndicatorSeries,
        indicator_name: str,
        params: dict,
    ):
        """Speichert eine einzelne IndicatorSeries in die processed_data-Tabelle."""
        # Alte Daten für diesen Indikator löschen (delete-before-insert)
        deleted = self._processed_repo.delete_by_ticker_indicator(
            ticker_id, indicator_name
        )
        if deleted:
            logger.debug(f"  {deleted} alte {indicator_name}-Einträge gelöscht")

        # Neue Daten erstellen
        records = []
        for i, bar in enumerate(bars):
            val = series.values[i]
            if np.isnan(val):
                continue
            records.append(
                ProcessedData(
                    ticker_id=ticker_id,
                    date=bar.date,
                    indicator=indicator_name,
                    value=Decimal(str(round(val, 6))),
                    parameters=json.dumps(params),
                    version=1,
                )
            )

        if records:
            self._processed_repo.bulk_create(records)
            self._session.commit()
            logger.debug(f"  {len(records)} {indicator_name}-Einträge gespeichert")

    def _persist_macd(
        self,
        ticker_id: int,
        bars: list[OHLCVBar],
        series_list: list[IndicatorSeries],
        indicator_name: str,
        params: dict,
    ):
        """Speichert MACD (Linie + Signal) als zusammenhängende Datensätze."""
        # Alte MACD-Daten löschen
        deleted = self._processed_repo.delete_by_ticker_indicator(
            ticker_id, indicator_name
        )
        if deleted:
            logger.debug(f"  {deleted} alte {indicator_name}-Einträge gelöscht")

        macd_values = series_list[0].values  # MACD-Linie
        signal_values = series_list[1].values  # Signal-Linie

        records = []
        for i, bar in enumerate(bars):
            macd_val = macd_values[i]
            sig_val = signal_values[i]
            # Mindestens einer der Werte muss vorhanden sein
            if np.isnan(macd_val) and np.isnan(sig_val):
                continue

            histogram = (macd_val - sig_val) if not (np.isnan(macd_val) or np.isnan(sig_val)) else None

            records.append(
                ProcessedData(
                    ticker_id=ticker_id,
                    date=bar.date,
                    indicator=indicator_name,
                    value=Decimal(str(round(macd_val, 6))) if not np.isnan(macd_val) else None,
                    value_secondary=Decimal(str(round(sig_val, 6))) if not np.isnan(sig_val) else None,
                    value_tertiary=Decimal(str(round(histogram, 6))) if histogram is not None else None,
                    parameters=json.dumps(params),
                    version=1,
                )
            )

        if records:
            self._processed_repo.bulk_create(records)
            self._session.commit()
            logger.debug(f"  {len(records)} {indicator_name}-Einträge gespeichert")
