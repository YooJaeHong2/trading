"""
미국 주식 시가총액 상위 100 데이터 레이어

- 후보 종목(UNIVERSE)의 시가총액을 yfinance로 조회해 상위 100개를 선정
- 상위 100개의 최근 2년 일봉(OHLCV)을 내려받음
- 1위 기업은 전체 기간(max) 종가도 받아 '역대 최고점'을 계산
- 결과는 cache/ 폴더에 하루 단위로 저장하여 재실행 시 빠르게 로드

환경변수 DEMO_DATA=1 을 주면 네트워크 없이 합성 데이터로 동작합니다.
"""
from __future__ import annotations

import os
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

TOP_N = 100
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
REFRESH_HOURS = float(os.getenv("REFRESH_HOURS", "6"))
DEMO = os.getenv("DEMO_DATA", "0") == "1"

# 미국 상장 대형주 후보군 (상위 100개는 실행 시점 시가총액으로 다시 정렬해서 선정)
# 동일 회사의 중복 클래스(GOOG/GOOGL 등)는 하나만 포함
UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "LLY",
    "JPM", "WMT", "V", "ORCL", "MA", "XOM", "NFLX", "COST", "JNJ", "HD",
    "PLTR", "ABBV", "BAC", "PG", "UNH", "CVX", "KO", "GE", "AMD", "CSCO",
    "TMUS", "WFC", "IBM", "MS", "AXP", "CRM", "PM", "GS", "ABT", "MU",
    "LIN", "MCD", "DIS", "RTX", "T", "INTU", "MRK", "PEP", "CAT", "UBER",
    "NOW", "TMO", "VZ", "BKNG", "ISRG", "APP", "QCOM", "AMAT", "SCHW", "BA",
    "C", "BLK", "TXN", "SPGI", "LRCX", "ANET", "GEV", "ACN", "NEE", "AMGN",
    "ADBE", "BSX", "SYK", "PGR", "LOW", "DHR", "ETN", "TJX", "GILD", "PFE",
    "KLAC", "HON", "UNP", "COF", "PANW", "DE", "CMCSA", "ADP", "KKR", "CRWD",
    "MDT", "ADI", "APH", "LMT", "INTC", "SNPS", "CB", "WELL", "MO", "VRTX",
    "BX", "CEG", "SO", "PLD", "CDNS", "DASH", "ICE", "MMC", "CME", "HOOD",
    "SBUX", "DUK", "MCK", "TT", "NKE", "COIN", "PH", "CVS", "ORLY", "BMY",
    "MCO", "WM", "CTAS", "CI", "SHW", "RCL", "AJG", "ABNB", "DELL", "GD",
    "NOC", "EQIX", "MSI", "HCA", "AON", "MMM", "ECL", "ITW", "PNC", "USB",
    "ZTS", "EMR", "APO", "MAR", "UPS", "NEM", "CL", "WMB", "ELV", "RSG",
    "HWM", "SNOW", "MRVL", "VST", "AZO", "FCX", "CSX", "TDG", "ADSK", "JCI",
    "NSC", "FTNT", "ROP", "PYPL", "TRV", "KMI", "WDAY", "CARR", "AEP", "SRE",
]


@dataclass
class Dataset:
    ranking: pd.DataFrame          # Rank, Ticker, Name, MarketCap, Close
    prices: dict                   # Ticker -> DataFrame(Date index; Open High Low Close Volume)
    leader_history: pd.Series      # 1위 기업 전체 기간 종가 (Date index)
    updated_at: datetime
    demo: bool = False


# --------------------------------------------------------------------------- #
# 실데이터 (yfinance)
# --------------------------------------------------------------------------- #
def _market_cap(ticker: str):
    import yfinance as yf
    try:
        t = yf.Ticker(ticker)
        cap = t.fast_info.get("marketCap")
        name = ticker
        try:
            info = t.get_info()
            name = info.get("shortName") or info.get("longName") or ticker
            cap = cap or info.get("marketCap")
        except Exception:
            pass
        return ticker, name, float(cap) if cap else None
    except Exception:
        return ticker, ticker, None


def _load_real() -> Dataset:
    import yfinance as yf

    with ThreadPoolExecutor(max_workers=16) as ex:
        caps = list(ex.map(_market_cap, UNIVERSE))
    ranking = (
        pd.DataFrame(caps, columns=["Ticker", "Name", "MarketCap"])
        .dropna(subset=["MarketCap"])
        .sort_values("MarketCap", ascending=False)
        .head(TOP_N)
        .reset_index(drop=True)
    )
    if ranking.empty:
        raise RuntimeError("시가총액 데이터를 가져오지 못했습니다 (네트워크/Yahoo 접근 확인).")
    ranking.insert(0, "Rank", ranking.index + 1)

    tickers = ranking["Ticker"].tolist()
    raw = yf.download(tickers, period="2y", interval="1d", auto_adjust=True,
                      group_by="ticker", progress=False, threads=True)
    prices = {}
    for tk in tickers:
        try:
            df = raw[tk].dropna(how="all")
        except KeyError:
            continue
        if not df.empty:
            df.index = pd.to_datetime(df.index).tz_localize(None)
            prices[tk] = df[["Open", "High", "Low", "Close", "Volume"]]

    ranking = ranking[ranking["Ticker"].isin(prices)].reset_index(drop=True)
    ranking["Rank"] = ranking.index + 1
    ranking["Close"] = [prices[t]["Close"].iloc[-1] for t in ranking["Ticker"]]

    leader = ranking["Ticker"].iloc[0]
    hist = yf.Ticker(leader).history(period="max", auto_adjust=True)["Close"].dropna()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)

    return Dataset(ranking, prices, hist, datetime.now())


# --------------------------------------------------------------------------- #
# 데모 데이터 (네트워크 없이 UI 확인용)
# --------------------------------------------------------------------------- #
def _load_demo() -> Dataset:
    rng = np.random.default_rng(42)
    tickers = UNIVERSE[:TOP_N]
    end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=503)
    caps = np.sort(rng.lognormal(mean=26.5, sigma=0.9, size=TOP_N))[::-1] + 1e11
    prices = {}
    for i, tk in enumerate(tickers):
        start = rng.uniform(30, 600)
        ret = rng.normal(0.0006, 0.018, len(dates))
        close = start * np.exp(np.cumsum(ret))
        open_ = close * (1 + rng.normal(0, 0.006, len(dates)))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, len(dates))))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, len(dates))))
        vol = rng.integers(5e6, 8e7, len(dates))
        prices[tk] = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=dates)
    ranking = pd.DataFrame({
        "Rank": range(1, TOP_N + 1), "Ticker": tickers,
        "Name": [f"{t} (demo)" for t in tickers], "MarketCap": caps,
        "Close": [prices[t]["Close"].iloc[-1] for t in tickers],
    })
    # 1위: 10년치 장기 종가 (앞부분은 2년치에 이어 붙임)
    long_dates = pd.bdate_range(end=dates[0] - timedelta(days=1), periods=2000)
    lret = rng.normal(0.0008, 0.02, len(long_dates))
    first = prices[tickers[0]]["Close"].iloc[0]
    lclose = first * np.exp(np.cumsum(lret) - np.cumsum(lret)[-1])
    hist = pd.concat([pd.Series(lclose, index=long_dates), prices[tickers[0]]["Close"]])
    return Dataset(ranking, prices, hist, datetime.now(), demo=True)


# --------------------------------------------------------------------------- #
# 캐시 + 로드
# --------------------------------------------------------------------------- #
_lock = threading.Lock()
_current: Dataset | None = None


def _cache_path() -> str:
    return os.path.join(CACHE_DIR, "demo.pkl" if DEMO else "top100.pkl")


def get_data(force: bool = False) -> Dataset:
    """메모리 → 디스크 캐시 → 원천 순으로 데이터를 반환. REFRESH_HOURS 지나면 갱신."""
    global _current
    with _lock:
        fresh = lambda d: d and datetime.now() - d.updated_at < timedelta(hours=REFRESH_HOURS)
        if not force and fresh(_current):
            return _current
        path = _cache_path()
        if not force and _current is None and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    cached = pickle.load(f)
                if fresh(cached):
                    _current = cached
                    return _current
            except Exception:
                pass
        try:
            data = _load_demo() if DEMO else _load_real()
        except Exception:
            if _current is not None:      # 갱신 실패 시 이전 데이터 유지
                return _current
            raise
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(data, f)
        _current = data
        return _current


# --------------------------------------------------------------------------- #
# 계산 유틸
# --------------------------------------------------------------------------- #
PERIODS = [  # (라벨, 영업일 수 또는 'YTD')
    ("1일", 1), ("1주", 5), ("1개월", 21), ("3개월", 63),
    ("6개월", 126), ("YTD", "YTD"), ("1년", 252), ("2년", None),
]


def period_return(close: pd.Series, period) -> float:
    close = close.dropna()
    if len(close) < 2:
        return np.nan
    last = close.iloc[-1]
    if period == "YTD":
        prev = close[close.index < pd.Timestamp(close.index[-1].year, 1, 1)]
        base = prev.iloc[-1] if len(prev) else close.iloc[0]
    elif period is None:
        base = close.iloc[0]
    else:
        if len(close) <= period:
            return np.nan
        base = close.iloc[-1 - period]
    return (last / base - 1) * 100


def fmt_cap(v: float) -> str:
    if v >= 1e12:
        return f"${v / 1e12:,.2f}T"
    return f"${v / 1e9:,.1f}B"
