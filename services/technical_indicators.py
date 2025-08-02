import numpy as np
import pandas as pd
from typing import Tuple, List

class TechnicalIndicators:
    """Calculate technical indicators for algorithmic trading"""
    
    @staticmethod
    def calculate_sma(prices: np.array, period: int = 20) -> np.array:
        """Calculate Simple Moving Average"""
        return pd.Series(prices).rolling(window=period).mean().values
    
    @staticmethod
    def calculate_std(prices: np.array, period: int = 20) -> np.array:
        """Calculate Standard Deviation"""
        return pd.Series(prices).rolling(window=period).std().values
    
    @staticmethod
    def calculate_adx_dmi(high: np.array, low: np.array, close: np.array, period: int = 14) -> Tuple[np.array, np.array, np.array]:
        """
        Calculate Wilder's Directional Movement Index (DMI) and Average Directional Index (ADX)
        Returns: (ADX, DI+, DI-)
        """
        # Manual ADX and DMI calculation
        df = pd.DataFrame({'high': high, 'low': low, 'close': close})
        
        # Calculate True Range
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # Calculate Directional Movement
        df['dm_plus'] = np.where(
            (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
            np.maximum(df['high'] - df['high'].shift(1), 0), 0
        )
        df['dm_minus'] = np.where(
            (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
            np.maximum(df['low'].shift(1) - df['low'], 0), 0
        )
        
        # Smooth the values using Wilder's smoothing
        alpha = 1.0 / period
        df['tr_smooth'] = df['tr'].ewm(alpha=alpha, adjust=False).mean()
        df['dm_plus_smooth'] = df['dm_plus'].ewm(alpha=alpha, adjust=False).mean()
        df['dm_minus_smooth'] = df['dm_minus'].ewm(alpha=alpha, adjust=False).mean()
        
        # Calculate DI+ and DI-
        df['di_plus'] = 100 * df['dm_plus_smooth'] / df['tr_smooth']
        df['di_minus'] = 100 * df['dm_minus_smooth'] / df['tr_smooth']
        
        # Calculate DX and ADX
        df['dx'] = 100 * abs(df['di_plus'] - df['di_minus']) / (df['di_plus'] + df['di_minus'])
        df['adx'] = df['dx'].ewm(alpha=alpha, adjust=False).mean()
        
        return df['adx'].values, df['di_plus'].values, df['di_minus'].values
    
    @staticmethod
    def calculate_pivot_points(high: float, low: float, close: float) -> dict:
        """
        Calculate Pivot Points and Support/Resistance levels
        """
        pivot = (high + low + close) / 3
        
        # Standard Pivot Points
        r1 = (2 * pivot) - low
        r2 = pivot + (high - low)
        s1 = (2 * pivot) - high
        s2 = pivot - (high - low)
        
        return {
            'pivot_point': pivot,
            'resistance_1': r1,
            'resistance_2': r2,
            'support_1': s1,
            'support_2': s2
        }
    
    @staticmethod
    def calculate_cci(high: np.array, low: np.array, close: np.array, period: int = 14) -> np.array:
        """
        Calculate Commodity Channel Index (CCI)
        CCI = (Price - MA) / (0.015 * D)
        where Price = (High + Low + Close) / 3
        """
        # Calculate typical price
        tp = (high + low + close) / 3
        # Calculate simple moving average of typical price
        tp_ma = pd.Series(tp).rolling(window=period).mean()
        # Calculate mean deviation
        mad = pd.Series(tp).rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())))
        # Calculate CCI
        cci = (tp - tp_ma) / (0.015 * mad)
        return cci.values
    
    @staticmethod
    def calculate_stochastic(high: np.array, low: np.array, close: np.array, 
                           k_period: int = 14, d_period: int = 3) -> Tuple[np.array, np.array]:
        """
        Calculate Stochastic Oscillator
        %K = 100 * (C - L14) / (H14 - L14)
        %D = 3-period moving average of %K
        """
        df = pd.DataFrame({'high': high, 'low': low, 'close': close})
        
        # Calculate %K
        df['lowest_low'] = df['low'].rolling(window=k_period).min()
        df['highest_high'] = df['high'].rolling(window=k_period).max()
        df['stoch_k'] = 100 * (df['close'] - df['lowest_low']) / (df['highest_high'] - df['lowest_low'])
        
        # Calculate %D (SMA of %K)
        df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()
        
        return df['stoch_k'].values, df['stoch_d'].values
    
    @staticmethod
    def calculate_bollinger_bands(close: np.array, period: int = 20, std_dev: int = 2) -> Tuple[np.array, np.array, np.array]:
        """Calculate Bollinger Bands"""
        middle = pd.Series(close).rolling(window=period).mean()
        std = pd.Series(close).rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper.values, middle.values, lower.values
    
    @staticmethod
    def calculate_rsi(close: np.array, period: int = 14) -> np.array:
        """Calculate Relative Strength Index"""
        delta = pd.Series(close).diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.values
    
    @staticmethod
    def calculate_macd(close: np.array, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Tuple[np.array, np.array, np.array]:
        """Calculate MACD"""
        ema_fast = pd.Series(close).ewm(span=fast_period).mean()
        ema_slow = pd.Series(close).ewm(span=slow_period).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal_period).mean()
        macd_hist = macd - macd_signal
        return macd.values, macd_signal.values, macd_hist.values
    
    @staticmethod
    def identify_priority_stocks(df: pd.DataFrame, symbol: str) -> bool:
        """
        Identify if a stock should be priority based on criteria:
        - Closing price > 1 std dev above/below 20-day MA
        - Closing price > $5
        """
        if len(df) < 20:
            return False
        
        latest = df.iloc[-1]
        close_price = latest['Close']
        
        # Must be above $5
        if close_price <= 5:
            return False
        
        # Calculate 20-day SMA and standard deviation
        sma_20 = TechnicalIndicators.calculate_sma(df['Close'].values, 20)
        std_20 = TechnicalIndicators.calculate_std(df['Close'].values, 20)
        
        if len(sma_20) == 0 or len(std_20) == 0:
            return False
        
        latest_sma = sma_20[-1]
        latest_std = std_20[-1]
        
        # Check if price is more than 1 std dev away from SMA
        upper_threshold = latest_sma + latest_std
        lower_threshold = latest_sma - latest_std
        
        return close_price > upper_threshold or close_price < lower_threshold
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators for a DataFrame with OHLCV data
        """
        if len(df) < 20:  # Need minimum data for calculations
            return df
        
        # Convert to numpy arrays
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        
        # Calculate indicators
        df['SMA_20'] = TechnicalIndicators.calculate_sma(close, 20)
        df['STD_20'] = TechnicalIndicators.calculate_std(close, 20)
        
        # ADX and DMI
        adx, di_plus, di_minus = TechnicalIndicators.calculate_adx_dmi(high, low, close)
        df['ADX'] = adx
        df['DI_Plus'] = di_plus
        df['DI_Minus'] = di_minus
        
        # CCI
        df['CCI'] = TechnicalIndicators.calculate_cci(high, low, close)
        
        # Stochastic
        stoch_k, stoch_d = TechnicalIndicators.calculate_stochastic(high, low, close)
        df['Stoch_K'] = stoch_k
        df['Stoch_D'] = stoch_d
        
        # Calculate pivot points for each row
        pivot_data = []
        for _, row in df.iterrows():
            pivots = TechnicalIndicators.calculate_pivot_points(row['High'], row['Low'], row['Close'])
            pivot_data.append(pivots)
        
        pivot_df = pd.DataFrame(pivot_data)
        df['Pivot_Point'] = pivot_df['pivot_point']
        df['Resistance_1'] = pivot_df['resistance_1']
        df['Resistance_2'] = pivot_df['resistance_2']
        df['Support_1'] = pivot_df['support_1']
        df['Support_2'] = pivot_df['support_2']
        
        # Additional indicators
        df['RSI'] = TechnicalIndicators.calculate_rsi(close)
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = TechnicalIndicators.calculate_bollinger_bands(close)
        df['BB_Upper'] = bb_upper
        df['BB_Middle'] = bb_middle
        df['BB_Lower'] = bb_lower
        
        # MACD
        macd, macd_signal, macd_hist = TechnicalIndicators.calculate_macd(close)
        df['MACD'] = macd
        df['MACD_Signal'] = macd_signal
        df['MACD_Hist'] = macd_hist
        
        return df
    
    @staticmethod
    def detect_price_momentum(prices: List[float], periods: int = 3) -> str:
        """
        Detect price momentum direction
        Returns: 'up', 'down', 'sideways'
        """
        if len(prices) < periods + 1:
            return 'sideways'
        
        recent_prices = prices[-periods-1:]
        changes = [recent_prices[i+1] - recent_prices[i] for i in range(len(recent_prices)-1)]
        
        positive_changes = sum(1 for change in changes if change > 0)
        negative_changes = sum(1 for change in changes if change < 0)
        
        if positive_changes == len(changes):
            return 'up'
        elif negative_changes == len(changes):
            return 'down'
        else:
            return 'sideways'
    
    @staticmethod
    def calculate_price_change_percentage(current_price: float, previous_price: float) -> float:
        """Calculate percentage change between two prices"""
        if previous_price == 0:
            return 0.0
        return ((current_price - previous_price) / previous_price) * 100
    
    @staticmethod
    def is_overbought_oversold(rsi: float, stoch_k: float, stoch_d: float) -> str:
        """
        Determine if asset is overbought, oversold, or neutral
        """
        overbought_signals = 0
        oversold_signals = 0
        
        # RSI signals
        if rsi > 70:
            overbought_signals += 1
        elif rsi < 30:
            oversold_signals += 1
        
        # Stochastic signals
        if stoch_k > 80 and stoch_d > 80:
            overbought_signals += 1
        elif stoch_k < 20 and stoch_d < 20:
            oversold_signals += 1
        
        if overbought_signals >= 1:
            return 'overbought'
        elif oversold_signals >= 1:
            return 'oversold'
        else:
            return 'neutral'
    
    @staticmethod
    def calculate_support_resistance_levels(df: pd.DataFrame, lookback: int = 20) -> dict:
        """
        Calculate dynamic support and resistance levels
        """
        if len(df) < lookback:
            return {'support': 0, 'resistance': 0}
        
        recent_data = df.tail(lookback)
        
        # Find local maxima and minima
        highs = recent_data['High'].values
        lows = recent_data['Low'].values
        
        resistance = np.max(highs)
        support = np.min(lows)
        
        return {
            'support': support,
            'resistance': resistance,
            'range_percent': ((resistance - support) / support) * 100
        }
