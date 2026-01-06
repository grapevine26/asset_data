import ccxt
import yfinance as yf
import json
import pandas as pd
import time
from datetime import datetime

# ==========================================
# 1. 설정 (Configuration)
# ==========================================

# A. 암호화폐 (메이저 + AI/L1 + 밈코인)
CRYPTO_SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'SOL/USDT',
    'DOGE/USDT', 'SHIB/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT',
    'TRX/USDT', 'MATIC/USDT', 'LTC/USDT', 'BCH/USDT',
    'NEAR/USDT', 'APT/USDT', 'SUI/USDT', 'WLD/USDT', 'PEPE/USDT'
]

# B. 주식 (빅테크 + 반도체 + 고변동성 + 인기주 + ETF)
STOCK_SYMBOLS = [
    'TSLA', 'AAPL', 'NVDA', 'MSFT', 'AMZN', 'GOOGL', 'META', 'NFLX',
    'AMD', 'INTC', 'ARM', 'AVGO', 'MU', 'TSM', 'SMCI',
    'PLTR', 'IONQ', 'SOFI', 'HOOD', 'COIN', 'RBLX',
    'MSTR', 'GME', 'CVNA',
    'QQQ', 'SPY', 'TQQQ', 'SOXL'
]

# 게임 룰 설정
PAST_CANDLES = 65
FUTURE_CANDLES = 10
TOTAL_WINDOW = PAST_CANDLES + FUTURE_CANDLES  # 75개
STEP_SIZE = 3  # 3개 캔들마다 생성

# 난이도별 변동성 기준값
VOLATILITY_SETTINGS = {
    '1m': {'min': 0.002, 'hard': 0.006},
    '5m': {'min': 0.005, 'hard': 0.015},
    '60m': {'min': 0.010, 'hard': 0.040}
}


# ==========================================
# 2. 유틸리티 함수
# ==========================================

def smart_round(price):
    if price is None or pd.isna(price): return None
    if price >= 10:
        return round(price, 2)
    elif price >= 1:
        return round(price, 3)
    elif price >= 0.01:
        return round(price, 4)
    else:
        return round(price, 8)


def smart_round_indicator(price):
    if price is None or pd.isna(price): return None
    if price >= 10:
        return round(price, 3)
    elif price >= 1:
        return round(price, 4)
    elif price >= 0.01:
        return round(price, 5)
    else:
        return round(price, 10)


# ✅ EMA(지수이동평균) 계산
def calculate_ema(df, window):
    return df['close'].ewm(span=window, adjust=False).mean()


# ✅ RSI(상대강도지수) 계산 (기간 14)
def calculate_rsi(df, window=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=window - 1, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=window - 1, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ✅ [신규] 볼린저 밴드 계산 (20일, 표준편차 2)
def calculate_bollinger_bands(df, window=20, num_std=2):
    sma = df['close'].rolling(window=window).mean()
    std = df['close'].rolling(window=window).std()
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    return upper_band, lower_band


def normalize_candle(raw, source):
    try:
        if source == 'ccxt':
            return {
                'time': int(raw[0]),
                'open': float(raw[1]),
                'high': float(raw[2]),
                'low': float(raw[3]),
                'close': float(raw[4]),
                'volume': float(raw[5])
            }
        else:  # yfinance
            return {
                'time': int(raw['Date'].timestamp() * 1000),
                'open': float(raw['Open']),
                'high': float(raw['High']),
                'low': float(raw['Low']),
                'close': float(raw['Close']),
                'volume': float(raw['Volume'])
            }
    except Exception:
        return None


# ==========================================
# 3. 데이터 수집 (Fetchers)
# ==========================================

def fetch_crypto_data(symbol, interval):
    req_interval = '1h' if interval == '60m' else interval
    print(f"   Downloading Crypto: {symbol} ({req_interval}) ...")
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(symbol, req_interval, limit=1500)
        return [normalize_candle(c, 'ccxt') for c in ohlcv]
    except Exception as e:
        print(f"   [Error] {symbol}: {e}")
        return []


def fetch_stock_data(symbol, interval):
    print(f"   Downloading Stock: {symbol} ({interval}) ...")
    period = '2y'
    if interval == '1m':
        period = '7d'
    elif interval == '5m':
        period = '60d'

    try:
        df = yf.download(
            symbol, period=period, interval=interval,
            progress=False, multi_level_index=False, auto_adjust=True
        )
        if df.empty: return []

        df.reset_index(inplace=True)
        if 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'Date'}, inplace=True)

        candles = []
        for _, row in df.iterrows():
            c = normalize_candle(row, 'yfinance')
            if c: candles.append(c)
        return candles
    except Exception as e:
        print(f"   [Skip] {symbol}: {e}")
        return []


# ==========================================
# 4. 게임 데이터 생성 로직 (핵심)
# ==========================================

def generate_game_data(candles, ticker, interval, asset_type):
    valid_games = []

    df = pd.DataFrame(candles)
    if len(df) < TOTAL_WINDOW: return []

    # ⭐️ 지표 계산 (EMA, RSI, BB 추가)
    df['ema5'] = calculate_ema(df, 5)
    df['ema20'] = calculate_ema(df, 20)
    df['ema60'] = calculate_ema(df, 60)
    df['ema120'] = calculate_ema(df, 120)  # ✅ EMA 120 추가
    df['rsi'] = calculate_rsi(df, 14)
    df['bb_upper'], df['bb_lower'] = calculate_bollinger_bands(df, 20, 2)  # ✅ 볼린저 밴드 추가

    calc_df = df.iloc[-2000:].reset_index(drop=True)
    setting = VOLATILITY_SETTINGS.get(interval, VOLATILITY_SETTINGS['60m'])

    for i in range(0, len(calc_df) - TOTAL_WINDOW + 1, STEP_SIZE):
        window_df = calc_df.iloc[i: i + TOTAL_WINDOW]

        entry_row = window_df.iloc[PAST_CANDLES - 1]
        exit_row = window_df.iloc[TOTAL_WINDOW - 1]

        entry_price = entry_row['close']
        exit_price = exit_row['close']

        if entry_price == 0: continue

        if window_df['high'].max() == window_df['low'].min(): continue

        # EMA 20 괴리율 체크
        ema20_val = entry_row['ema20']
        if pd.notnull(ema20_val) and ema20_val != 0:
            if abs(entry_price - ema20_val) / ema20_val > 0.5: continue

        change_rate = (exit_price - entry_price) / entry_price
        abs_change = abs(change_rate)

        if abs_change < setting['min']: continue

        # 난이도 판별 (EMA 5 > 20 > 60 정배열)
        difficulty = "Normal"
        if abs_change >= setting['hard']:
            difficulty = "Hard"
        else:
            is_bull_easy = (entry_row['ema5'] > entry_row['ema20'] > entry_row['ema60']) and (change_rate > 0)
            is_bear_easy = (entry_row['ema5'] < entry_row['ema20'] < entry_row['ema60']) and (change_rate < 0)
            if is_bull_easy or is_bear_easy: difficulty = "Easy"

        short_ticker = ticker.split('/')[0]
        short_time = int(exit_row['time'] / 1000)
        short_id = f"{short_ticker}_{interval}_{short_time}"

        optimized_candles = []
        for _, row in window_df.iterrows():
            optimized_candles.append([
                int(row['time']),  # 0
                smart_round(row['open']),  # 1
                smart_round(row['high']),  # 2
                smart_round(row['low']),  # 3
                smart_round(row['close']),  # 4
                int(row['volume']),  # 5

                # ⭐️ [지표 데이터]
                smart_round_indicator(row['ema5']) if pd.notnull(row['ema5']) else None,  # 6
                smart_round_indicator(row['ema20']) if pd.notnull(row['ema20']) else None,  # 7
                smart_round_indicator(row['ema60']) if pd.notnull(row['ema60']) else None,  # 8
                smart_round_indicator(row['ema120']) if pd.notnull(row['ema120']) else None,  # 9 (New)

                round(row['rsi'], 2) if pd.notnull(row['rsi']) else None,  # 10

                smart_round_indicator(row['bb_upper']) if pd.notnull(row['bb_upper']) else None,  # 11 (New)
                smart_round_indicator(row['bb_lower']) if pd.notnull(row['bb_lower']) else None  # 12 (New)
            ])

        game_round = {
            'game_id': short_id,
            'asset_type': asset_type,
            'ticker': ticker,
            'interval': interval,
            'difficulty': difficulty,
            'result': {
                'position': 'LONG' if change_rate > 0 else 'SHORT',
                'change_percent': round(change_rate * 100, 2),
                'entry_price': smart_round(entry_price),
                'exit_price': smart_round(exit_price)
            },
            'candles': optimized_candles
        }
        valid_games.append(game_round)

    return valid_games


# ==========================================
# 5. 메인 실행
# ==========================================

def main():
    all_game_data = []
    targets = []

    for s in CRYPTO_SYMBOLS:
        targets.extend([
            {'type': 'crypto', 'symbol': s, 'interval': '1m'},
            {'type': 'crypto', 'symbol': s, 'interval': '5m'},
            {'type': 'crypto', 'symbol': s, 'interval': '60m'}
        ])
    for s in STOCK_SYMBOLS:
        targets.extend([
            {'type': 'stock', 'symbol': s, 'interval': '1m'},
            {'type': 'stock', 'symbol': s, 'interval': '5m'},
            {'type': 'stock', 'symbol': s, 'interval': '60m'}
        ])

    print(f"🚀 데이터 수집 시작 (타겟: {len(targets)}개, 스텝: {STEP_SIZE})\n")

    for t in targets:
        raw_data = []
        if t['type'] == 'crypto':
            raw_data = fetch_crypto_data(t['symbol'], t['interval'])
        else:
            raw_data = fetch_stock_data(t['symbol'], t['interval'])

        if not raw_data: continue

        games = generate_game_data(raw_data, t['symbol'], t['interval'], t['type'])

        if games:
            print(f"   ✅ {t['symbol']} ({t['interval']}): {len(games)}개")
            all_game_data.extend(games)
        else:
            print(f"   ⚠️ {t['symbol']} ({t['interval']}): 없음")

    filename = 'game_data_final.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_game_data, f, indent=2, ensure_ascii=False)

    print(f"\n[완료] 총 {len(all_game_data)}개 저장됨: '{filename}'")


if __name__ == "__main__":
    main()