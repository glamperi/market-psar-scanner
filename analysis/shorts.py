"""
Shorts Analysis Module

Analyzes stocks for short opportunities with put spread suggestions.
Includes short interest data and squeeze risk warnings.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import os
import csv


@dataclass
class ShortCandidate:
    """Short candidate analysis result."""
    ticker: str
    current_price: float
    
    # Technical indicators
    psar_gap: float  # Negative = below PSAR (good for shorts)
    psar_days_bearish: int  # Days price below PSAR
    psar_gap_slope: float = 0  # Change in gap over 3 days (negative = accelerating down)
    prsi_bearish: bool = False
    prsi_days_since_flip: int = 0
    obv_bearish: bool = False  # Distribution = good for shorts
    dmi_bearish: bool = False  # -DI > +DI
    adx_value: float = 20
    williams_r: float = -50  # Near 0 = overbought = good short entry
    atr_percent: float = 0
    
    # Smart Short Indicator
    ssi: int = 0  # 0-10, higher = better short
    
    # Short interest data
    short_percent: Optional[float] = None  # % of float shorted
    days_to_cover: Optional[float] = None  # Short ratio
    squeeze_risk: str = "UNKNOWN"  # LOW, MODERATE, HIGH, UNKNOWN
    
    # Scoring
    short_score: int = 0
    category: str = ""  # PRIME_SHORT, SHORT_CANDIDATE, NOT_READY, AVOID
    reasons: List[str] = None
    warnings: List[str] = None
    
    # Put spread suggestion
    buy_put_strike: Optional[float] = None
    sell_put_strike: Optional[float] = None
    put_expiration: Optional[str] = None
    put_days_to_expiry: Optional[int] = None
    spread_cost: Optional[float] = None
    max_profit: Optional[float] = None
    
    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.warnings is None:
            self.warnings = []


# Load manual short interest overrides from CSV
def load_short_interest_overrides(filepath=None):
    """Load manual short interest data from CSV."""
    overrides = {}
    
    # Check multiple possible locations
    possible_paths = [
        filepath,
        'short_interest.csv',
        'data_files/short_interest.csv',
        os.path.join(os.path.dirname(__file__), '..', 'data_files', 'short_interest.csv'),
        os.path.join(os.path.dirname(__file__), '..', 'short_interest.csv'),
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('Symbol') and not row['Symbol'].startswith('#'):
                            ticker = row['Symbol'].upper().strip()
                            overrides[ticker] = {
                                'short_percent': float(row.get('ShortPercent', 0)) if row.get('ShortPercent') else None,
                                'days_to_cover': float(row.get('DaysToCover', 0)) if row.get('DaysToCover') else None,
                            }
                print(f"  Loaded {len(overrides)} short interest overrides from {path}")
                break
            except Exception as e:
                print(f"  Warning: Could not load short interest CSV: {e}")
    
    return overrides


# Global overrides cache
_short_interest_overrides = None


def get_short_interest_overrides():
    """Get cached short interest overrides."""
    global _short_interest_overrides
    if _short_interest_overrides is None:
        _short_interest_overrides = load_short_interest_overrides()
    return _short_interest_overrides


def get_short_interest(ticker: str, info: dict = None) -> Tuple[Optional[float], Optional[float]]:
    """
    Get short interest data for a ticker.
    
    Returns:
        Tuple of (short_percent, days_to_cover)
    """
    # Check overrides first
    overrides = get_short_interest_overrides()
    if ticker.upper() in overrides:
        data = overrides[ticker.upper()]
        return data.get('short_percent'), data.get('days_to_cover')
    
    # Try yfinance
    if info is None:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
        except:
            return None, None
    
    short_percent = info.get('shortPercentOfFloat')
    if short_percent is not None:
        short_percent = short_percent * 100  # Convert decimal to percentage
    
    days_to_cover = info.get('shortRatio')
    
    return short_percent, days_to_cover


def get_squeeze_risk(short_percent: Optional[float]) -> Tuple[str, str]:
    """
    Determine squeeze risk level.
    
    Returns:
        Tuple of (risk_level, emoji)
    """
    if short_percent is None:
        return 'UNKNOWN', '❓'
    elif short_percent > 25:
        return 'HIGH', '🔴'
    elif short_percent > 15:
        return 'MODERATE', '🟡'
    else:
        return 'LOW', '🟢'


def calculate_ssi(
    psar_days_bearish: int,
    atr_percent: float,
    adx_value: float,
    psar_gap: float = 0,
    psar_gap_slope: float = 0,
    obv_bearish: bool = False,
    williams_r: float = -50
) -> int:
    """
    Calculate Smart Short Indicator (SSI) 0-10.
    
    For shorts, we WANT:
    - PSAR gap NEGATIVE = confirmed breakdown (not just PRSI flip)
    - OBV distribution = selling pressure
    - Williams %R overbought (> -20) = room to fall
    - High ATR = more profit potential
    - High ADX = strong trend
    - Negative PSAR slope = gap widening downward (accelerating)
    
    Days 1-5 (Fresh breakdown): 30% PSAR gap + 25% OBV + 25% Williams %R + 20% ATR
    Days 6+ (Established): 30% PSAR slope + 25% ADX + 25% OBV + 20% ATR
    
    Args:
        psar_days_bearish: Days since price crossed below PSAR
        atr_percent: ATR as % of price
        adx_value: ADX trend strength
        psar_gap: Current PSAR gap % (negative = below PSAR = confirmed)
        psar_gap_slope: Change in PSAR gap over 3 days
        obv_bearish: True if OBV shows distribution
        williams_r: Williams %R value (-100 to 0, > -20 = overbought)
    
    Returns:
        SSI score 0-10 (10 = best short candidate)
    """
    # PSAR gap score - NEGATIVE is required for confirmed short
    # More negative = better (further below resistance)
    if psar_gap <= -5:
        gap_score = 10  # Deep below PSAR - strong confirmation
    elif psar_gap <= -3:
        gap_score = 9
    elif psar_gap <= -1:
        gap_score = 8
    elif psar_gap < 0:
        gap_score = 6   # Just below PSAR
    elif psar_gap < 2:
        gap_score = 3   # Still above PSAR - early/risky
    else:
        gap_score = 1   # Well above PSAR - too early!
    
    # OBV score - distribution (bearish) is what we want
    obv_score = 10 if obv_bearish else 3
    
    # Williams %R score - overbought (> -20) = good short entry
    # Oversold (< -80) = bounce risk, bad for shorts
    if williams_r > -20:
        wr_score = 10  # Overbought - ideal short entry
    elif williams_r > -40:
        wr_score = 8   # Upper range
    elif williams_r > -60:
        wr_score = 6   # Middle
    elif williams_r > -80:
        wr_score = 4   # Lower range
    else:
        wr_score = 2   # Oversold - bounce risk!
    
    # ATR score - HIGHER is better for shorts (more profit potential)
    if atr_percent >= 6:
        atr_score = 10
    elif atr_percent >= 5:
        atr_score = 9
    elif atr_percent >= 4:
        atr_score = 8
    elif atr_percent >= 3:
        atr_score = 7
    elif atr_percent >= 2:
        atr_score = 5
    else:
        atr_score = 3  # Low ATR = less profit potential
    
    # ADX score - HIGHER is better (strong trend)
    if adx_value >= 40:
        adx_score = 10
    elif adx_value >= 30:
        adx_score = 8
    elif adx_value >= 25:
        adx_score = 6
    elif adx_value >= 20:
        adx_score = 4
    else:
        adx_score = 2  # Choppy = bad for shorts
    
    if psar_days_bearish <= 5:
        # Fresh breakdown: 30% PSAR gap + 25% OBV + 25% Williams %R + 20% ATR
        # Emphasis on CONFIRMATION (gap below PSAR) and TIMING (overbought)
        ssi = int(0.30 * gap_score + 0.25 * obv_score + 0.25 * wr_score + 0.20 * atr_score)
    else:
        # Established downtrend: 30% slope + 25% ADX + 25% OBV + 20% ATR
        # PSAR slope - for shorts, NEGATIVE slope is good (gap widening downward)
        if psar_gap_slope <= -2:
            slope_score = 10  # Strongly accelerating down
        elif psar_gap_slope <= -1:
            slope_score = 9
        elif psar_gap_slope <= -0.5:
            slope_score = 8
        elif psar_gap_slope <= 0.5:
            slope_score = 6  # Stable
        elif psar_gap_slope <= 1:
            slope_score = 4  # Slowing
        else:
            slope_score = 2  # Reversing up = bad
        
        ssi = int(0.30 * slope_score + 0.25 * adx_score + 0.25 * obv_score + 0.20 * atr_score)
    
    return max(0, min(10, ssi))


def get_ssi_display(ssi: int) -> str:
    """Get colored SSI display HTML."""
    if ssi >= 9:
        return f"<span style='color:#c0392b; font-weight:bold;'>{ssi}</span>"  # Dark red = excellent short
    elif ssi >= 8:
        return f"<span style='color:#e74c3c; font-weight:bold;'>{ssi}</span>"  # Red = good short
    elif ssi >= 6:
        return f"<span style='color:#f39c12;'>{ssi}</span>"  # Yellow = OK
    elif ssi >= 4:
        return f"<span style='color:#95a5a6;'>{ssi}</span>"  # Gray = weak
    else:
        return f"<span style='color:#27ae60;'>{ssi}</span>"  # Green = avoid (bullish)


def calculate_short_score(
    psar_gap: float,
    psar_days_bearish: int,
    prsi_bearish: bool,
    prsi_days_since_flip: int,
    obv_bearish: bool,
    dmi_bearish: bool,
    adx_value: float,
    williams_r: float,
    atr_percent: float,
    short_percent: Optional[float] = None,
) -> Tuple[int, List[str], List[str]]:
    """
    Calculate short score (0-100) and return reasons/warnings.
    
    Higher score = better short candidate.
    """
    score = 0
    reasons = []
    warnings = []
    
    # PRSI Bearish (most important - leads price)
    if prsi_bearish:
        score += 25
        reasons.append(f"PRSI bearish ({prsi_days_since_flip}d)")
    else:
        score -= 30
        warnings.append("PRSI bullish - NOT a short")
    
    # Price vs PSAR
    if psar_gap < 0:
        # Below PSAR - confirmed downtrend
        if psar_gap < -5:
            score += 20
            reasons.append(f"Deep below PSAR ({psar_gap:.1f}%)")
        else:
            score += 15
            reasons.append(f"Below PSAR ({psar_gap:.1f}%)")
        
        # Freshness bonus
        if psar_days_bearish <= 5:
            score += 10
            reasons.append(f"Fresh breakdown ({psar_days_bearish}d)")
    else:
        # Still above PSAR
        if prsi_bearish:
            score += 5  # Early short potential
            warnings.append(f"Price still above PSAR (+{psar_gap:.1f}%)")
        else:
            score -= 20
            warnings.append("Above PSAR - avoid")
    
    # OBV Distribution
    if obv_bearish:
        score += 15
        reasons.append("OBV distribution")
    else:
        warnings.append("OBV accumulation")
    
    # DMI Bearish
    if dmi_bearish:
        score += 10
        reasons.append("DMI bearish (-DI > +DI)")
    
    # ADX Trend Strength
    if adx_value >= 25:
        score += 10
        reasons.append(f"Strong trend (ADX {adx_value:.0f})")
    elif adx_value < 15:
        score -= 5
        warnings.append(f"Weak trend (ADX {adx_value:.0f})")
    
    # Williams %R - Overbought = good short entry
    if williams_r > -20:
        score += 15
        reasons.append(f"Overbought (Will%R {williams_r:.0f})")
    elif williams_r < -80:
        score -= 15
        warnings.append(f"Oversold (Will%R {williams_r:.0f}) - bounce risk")
    
    # ATR Volatility - want high ATR for shorts
    if atr_percent >= 5:
        score += 10
        reasons.append(f"High volatility (ATR {atr_percent:.1f}%)")
    elif atr_percent < 2:
        score -= 5
        warnings.append(f"Low volatility (ATR {atr_percent:.1f}%)")
    
    # Short Interest / Squeeze Risk
    if short_percent is not None:
        if short_percent > 25:
            score -= 25
            warnings.append(f"⚠️ HIGH squeeze risk (SI {short_percent:.1f}%)")
        elif short_percent > 15:
            score -= 10
            warnings.append(f"Elevated SI ({short_percent:.1f}%)")
        elif short_percent < 5:
            score += 5
            reasons.append(f"Low SI ({short_percent:.1f}%)")
    
    # Clamp score
    score = max(0, min(100, score))
    
    return score, reasons, warnings


def categorize_short(score: int, prsi_bearish: bool, psar_gap: float, psar_days: int, williams_r: float = -50) -> str:
    """
    Categorize short candidate based on score and signals.
    
    STRICT criteria to avoid too many false positives:
    - PRIME_SHORT: High score, confirmed breakdown, overbought
    - SHORT_CANDIDATE: Good score, below PSAR
    - NOT_READY: PRSI bearish but waiting for confirmation
    - AVOID: Everything else
    """
    if not prsi_bearish:
        return "AVOID"
    
    # PRIME_SHORT: Must be high conviction
    # - Score >= 70
    # - Price below PSAR (confirmed breakdown)
    # - Fresh signal (≤3 days)
    # - Williams %R not oversold (> -70 means not bouncing yet)
    if score >= 70 and psar_gap < 0 and psar_days <= 3 and williams_r > -70:
        return "PRIME_SHORT"
    
    # SHORT_CANDIDATE: Good setup but less urgent
    # - Score >= 60
    # - Price below PSAR
    # - Not deeply oversold
    elif score >= 60 and psar_gap < 0 and williams_r > -80:
        return "SHORT_CANDIDATE"
    
    # NOT_READY: PRSI bearish but price still above PSAR or oversold
    elif score >= 45 and prsi_bearish:
        return "NOT_READY"
    
    else:
        return "AVOID"


def get_put_spread_recommendation(
    ticker: str,
    current_price: float,
    atr_percent: float,
    min_days: int = 14,
    max_days: int = 28
) -> Optional[Dict]:
    """
    Get put spread recommendation for a short position.
    
    Strategy: Buy higher strike put (delta ~0.40), sell lower strike put (delta ~0.15)
    Expiration: 2-4 weeks
    
    Uses Schwab API (via data.schwab_options) with yfinance fallback.
    """
    try:
        # Use schwab_options module with Schwab API + yfinance fallback
        from data.schwab_options import get_options_chain
        
        options_data = get_options_chain(ticker, days_out=max_days)
        if not options_data:
            return None
        
        puts = options_data.get('puts')
        if puts is None or puts.empty:
            return None
        
        # Filter by expiration range
        puts = puts.copy()
        puts['exp_date'] = pd.to_datetime(puts['expiration'])
        now = datetime.now()
        puts['days_to_exp'] = (puts['exp_date'] - now).dt.days
        puts = puts[(puts['days_to_exp'] >= min_days) & (puts['days_to_exp'] <= max_days)]
        
        if puts.empty:
            # If no puts in range, take earliest available
            puts = options_data['puts'].copy()
            puts['exp_date'] = pd.to_datetime(puts['expiration'])
            puts['days_to_exp'] = (puts['exp_date'] - now).dt.days
            puts = puts[puts['days_to_exp'] >= min_days].head(50)
        
        if puts.empty:
            return None
        
        # Get the target expiration (first one in range)
        target_exp = puts['expiration'].iloc[0]
        puts = puts[puts['expiration'] == target_exp]
        
        # Buy put target: delta ~0.40 = roughly ATM or slightly ITM
        buy_target_strike = current_price * 1.05  # 5% ITM
        
        # Sell put target: delta ~0.15 = roughly 10-15% OTM
        sell_target_strike = current_price * 0.85  # 15% OTM
        
        # Find closest strikes
        puts['buy_diff'] = abs(puts['strike'] - buy_target_strike)
        puts['sell_diff'] = abs(puts['strike'] - sell_target_strike)
        
        buy_put = puts.loc[puts['buy_diff'].idxmin()]
        sell_put = puts.loc[puts['sell_diff'].idxmin()]
        
        buy_strike = buy_put['strike']
        sell_strike = sell_put['strike']
        
        # Make sure buy strike > sell strike
        if buy_strike <= sell_strike:
            # Adjust - buy should be higher strike
            itm_puts = puts[puts['strike'] > current_price]
            otm_puts = puts[puts['strike'] < current_price * 0.90]
            
            if not itm_puts.empty and not otm_puts.empty:
                buy_strike = itm_puts['strike'].min()
                sell_strike = otm_puts['strike'].max()
                buy_put = puts[puts['strike'] == buy_strike].iloc[0]
                sell_put = puts[puts['strike'] == sell_strike].iloc[0]
        
        # Calculate costs - handle both Schwab and yfinance column names
        buy_bid = buy_put.get('bid', 0) or 0
        buy_ask = buy_put.get('ask', 0) or 0
        buy_last = buy_put.get('last', buy_put.get('lastPrice', 0)) or 0
        buy_mid = (buy_bid + buy_ask) / 2 if buy_bid > 0 and buy_ask > 0 else buy_last
        
        sell_bid = sell_put.get('bid', 0) or 0
        sell_ask = sell_put.get('ask', 0) or 0
        sell_last = sell_put.get('last', sell_put.get('lastPrice', 0)) or 0
        sell_mid = (sell_bid + sell_ask) / 2 if sell_bid > 0 and sell_ask > 0 else sell_last
        
        spread_cost = buy_mid - sell_mid  # Net debit
        max_profit = buy_strike - sell_strike - spread_cost  # Max profit at expiration
        
        today = datetime.now().date()
        exp_date = datetime.strptime(target_exp, '%Y-%m-%d').date()
        days_to_exp = (exp_date - today).days
        
        return {
            'buy_strike': buy_strike,
            'sell_strike': sell_strike,
            'expiration': target_exp,
            'days_to_expiry': days_to_exp,
            'spread_cost': spread_cost,
            'max_profit': max_profit,
            'buy_premium': buy_mid,
            'sell_premium': sell_mid,
            'source': options_data.get('source', 'unknown')
        }
        
    except Exception as e:
        error_msg = str(e)
        # Only print warning for non-rate-limit errors
        if 'Too Many Requests' not in error_msg and '429' not in error_msg:
            print(f"    Warning: Could not get put spread for {ticker}: {e}")
        return None


def analyze_short_candidate(
    ticker: str,
    current_price: float,
    psar_gap: float,
    psar_days_bearish: int,
    prsi_bearish: bool,
    prsi_days_since_flip: int,
    obv_bearish: bool,
    dmi_bearish: bool,
    adx_value: float,
    williams_r: float,
    atr_percent: float,
    psar_gap_slope: float = 0,
    info: dict = None,
    fetch_options: bool = True
) -> ShortCandidate:
    """
    Analyze a stock as a short candidate.
    """
    # Get short interest
    short_percent, days_to_cover = get_short_interest(ticker, info)
    squeeze_risk, _ = get_squeeze_risk(short_percent)
    
    # Calculate short score (for categorization)
    score, reasons, warnings = calculate_short_score(
        psar_gap=psar_gap,
        psar_days_bearish=psar_days_bearish,
        prsi_bearish=prsi_bearish,
        prsi_days_since_flip=prsi_days_since_flip,
        obv_bearish=obv_bearish,
        dmi_bearish=dmi_bearish,
        adx_value=adx_value,
        williams_r=williams_r,
        atr_percent=atr_percent,
        short_percent=short_percent,
    )
    
    # Calculate SSI (Smart Short Indicator)
    ssi = calculate_ssi(
        psar_days_bearish=psar_days_bearish,
        atr_percent=atr_percent,
        adx_value=adx_value,
        psar_gap=psar_gap,
        psar_gap_slope=psar_gap_slope,
        obv_bearish=obv_bearish,
        williams_r=williams_r
    )
    
    # Categorize - pass williams_r for oversold check
    category = categorize_short(score, prsi_bearish, psar_gap, psar_days_bearish, williams_r)
    
    candidate = ShortCandidate(
        ticker=ticker,
        current_price=current_price,
        psar_gap=psar_gap,
        psar_days_bearish=psar_days_bearish,
        psar_gap_slope=psar_gap_slope,
        prsi_bearish=prsi_bearish,
        prsi_days_since_flip=prsi_days_since_flip,
        obv_bearish=obv_bearish,
        dmi_bearish=dmi_bearish,
        adx_value=adx_value,
        williams_r=williams_r,
        atr_percent=atr_percent,
        ssi=ssi,
        short_percent=short_percent,
        days_to_cover=days_to_cover,
        squeeze_risk=squeeze_risk,
        short_score=score,
        category=category,
        reasons=reasons,
        warnings=warnings,
    )
    
    # Get put spread if good candidate
    if fetch_options and category in ['PRIME_SHORT', 'SHORT_CANDIDATE']:
        put_data = get_put_spread_recommendation(ticker, current_price, atr_percent)
        if put_data:
            candidate.buy_put_strike = put_data['buy_strike']
            candidate.sell_put_strike = put_data['sell_strike']
            candidate.put_expiration = put_data['expiration']
            candidate.put_days_to_expiry = put_data['days_to_expiry']
            candidate.spread_cost = put_data['spread_cost']
            candidate.max_profit = put_data['max_profit']
    
    return candidate


def build_shorts_html_section(candidates: List[ShortCandidate], title: str, section_class: str) -> str:
    """Build HTML table for a shorts section."""
    if not candidates:
        return ""
    
    html = f"""
    <div style='background-color:{section_class}; color:white; padding:12px; margin:20px 0 10px 0; font-size:14px; font-weight:bold;'>
        {title} ({len(candidates)} stocks)
    </div>
    <table>
        <tr style='background-color:{section_class}; color:white;'>
            <th>Ticker</th><th>Price</th><th>PSAR%</th><th>Days</th><th>SSI</th>
            <th>PRSI</th><th>OBV</th><th>DMI</th><th>ADX</th><th>Will%R</th><th>ATR%</th>
            <th>SI%</th><th>Squeeze</th>
            <th>Buy Put</th><th>Sell Put</th><th>Exp</th><th>Cost</th><th>Links</th>
        </tr>
    """
    
    for c in candidates:
        prsi_icon = "↘️" if c.prsi_bearish else "↗️"
        obv_icon = "🔴" if c.obv_bearish else "🟢"
        dmi_icon = "✓" if c.dmi_bearish else "✗"
        
        # Williams color
        if c.williams_r > -20:
            wr_color = '#e74c3c'  # Red = overbought = good for shorts
        elif c.williams_r < -80:
            wr_color = '#27ae60'  # Green = oversold = bad for shorts
        else:
            wr_color = '#f39c12'
        
        # Squeeze risk color
        if c.squeeze_risk == 'HIGH':
            sq_icon = '🔴'
        elif c.squeeze_risk == 'MODERATE':
            sq_icon = '🟡'
        elif c.squeeze_risk == 'LOW':
            sq_icon = '🟢'
        else:
            sq_icon = '❓'
        
        si_display = f"{c.short_percent:.1f}%" if c.short_percent else "-"
        
        buy_put = f"${c.buy_put_strike:.0f}" if c.buy_put_strike else "-"
        sell_put = f"${c.sell_put_strike:.0f}" if c.sell_put_strike else "-"
        exp = c.put_expiration if c.put_expiration else "-"
        cost = f"${c.spread_cost:.2f}" if c.spread_cost else "-"
        
        # SSI display
        ssi_display = get_ssi_display(c.ssi)
        
        # Build trading links
        trade_links = "-"
        if c.buy_put_strike and c.sell_put_strike and c.put_expiration:
            try:
                exp_date = datetime.strptime(c.put_expiration, '%Y-%m-%d')
                exp_yymmdd = exp_date.strftime('%y%m%d')
                buy_strike_int = int(c.buy_put_strike) if c.buy_put_strike == int(c.buy_put_strike) else c.buy_put_strike
                sell_strike_int = int(c.sell_put_strike) if c.sell_put_strike == int(c.sell_put_strike) else c.sell_put_strike
                
                # Fidelity links
                buy_symbol = f"-{c.ticker}{exp_yymmdd}P{buy_strike_int}"
                sell_symbol = f"-{c.ticker}{exp_yymmdd}P{sell_strike_int}"
                buy_url = f"https://digital.fidelity.com/ftgw/digital/quick-quote/popup?symbol={buy_symbol}"
                sell_url = f"https://digital.fidelity.com/ftgw/digital/quick-quote/popup?symbol={sell_symbol}"
                
                # Optionstrat link for bear put spread
                # Format: BTO higher strike, STO lower strike
                # Use - prefix for sell leg
                exp_optionstrat = exp_date.strftime('%y%m%d')
                optionstrat_url = f"https://optionstrat.com/build/bear-put-spread/{c.ticker}/.{c.ticker}{exp_optionstrat}P{buy_strike_int},-.{c.ticker}{exp_optionstrat}P{sell_strike_int}"
                
                trade_links = f"<a href='{optionstrat_url}' target='_blank' style='text-decoration:none;' title='Optionstrat'>📊</a> "
                trade_links += f"<a href='{buy_url}' target='_blank' style='text-decoration:none;' title='Fidelity Buy'>📈</a> "
                trade_links += f"<a href='{sell_url}' target='_blank' style='text-decoration:none;' title='Fidelity Sell'>📉</a>"
            except:
                trade_links = "-"
        
        html += f"""
        <tr>
            <td><strong>{c.ticker}</strong></td>
            <td>${c.current_price:.2f}</td>
            <td style='color:{"#e74c3c" if c.psar_gap < 0 else "#27ae60"};'>{c.psar_gap:+.1f}%</td>
            <td>{c.psar_days_bearish}</td>
            <td>{ssi_display}</td>
            <td>{prsi_icon}</td>
            <td>{obv_icon}</td>
            <td>{dmi_icon}</td>
            <td>{c.adx_value:.0f}</td>
            <td style='color:{wr_color};'>{c.williams_r:.0f}</td>
            <td>{c.atr_percent:.1f}%</td>
            <td>{si_display}</td>
            <td>{sq_icon}</td>
            <td>{buy_put}</td>
            <td>{sell_put}</td>
            <td>{exp}</td>
            <td>{cost}</td>
            <td>{trade_links}</td>
        </tr>"""
    
    html += "</table>"
    return html


def build_avoid_section(candidates: List[ShortCandidate]) -> str:
    """Build HTML section for stocks to avoid shorting."""
    if not candidates:
        return ""
    
    html = """
    <div style='background-color:#95a5a6; color:white; padding:12px; margin:20px 0 10px 0; font-size:14px; font-weight:bold;'>
        ❌ AVOID - Not Short Candidates ({} stocks)
    </div>
    <p style='color:#666; font-size:11px; margin:5px 0;'>These stocks do not meet short criteria. Reasons listed below.</p>
    <table>
        <tr style='background-color:#95a5a6; color:white;'>
            <th>Ticker</th><th>Price</th><th>PSAR%</th><th>Score</th><th>Why Avoid</th>
        </tr>
    """.format(len(candidates))
    
    for c in candidates:
        warnings_str = "; ".join(c.warnings[:3]) if c.warnings else "No clear short signal"
        
        html += f"""
        <tr>
            <td><strong>{c.ticker}</strong></td>
            <td>${c.current_price:.2f}</td>
            <td style='color:{"#e74c3c" if c.psar_gap < 0 else "#27ae60"};'>{c.psar_gap:+.1f}%</td>
            <td>{c.short_score}</td>
            <td style='color:#e74c3c;'>{warnings_str}</td>
        </tr>"""
    
    html += "</table>"
    return html


def build_shorts_report_html(
    short_candidates: List[ShortCandidate],
    mode: str = "Shorts",
    total_scanned: int = 0
) -> str:
    """Build complete HTML report for shorts analysis - single list only."""
    
    html = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; font-size: 12px; }
            table { border-collapse: collapse; width: 100%; margin: 10px 0; }
            th { padding: 8px; text-align: left; font-size: 11px; }
            td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }
            tr:hover { background-color: #f5f5f5; }
        </style>
    </head>
    <body>
    """
    
    html += f"""
    <h2>🐻 Short Candidates - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>
    <p>Mode: {mode} | Scanned: {total_scanned} | Showing: {len(short_candidates)} with tradeable options</p>
    """
    
    # Summary
    html += f"""
    <div style='background-color:#f5f5f5; padding:15px; margin:10px 0; border-left:4px solid #c0392b;'>
        <strong>🔴 {len(short_candidates)} SHORT CANDIDATES</strong> - All have tradeable put options<br>
        <span style='font-size:11px; color:#666;'>Sorted by short score (highest conviction first)</span>
    </div>
    """
    
    # Guide
    html += """
    <div style='font-size:10px; color:#666; padding:10px; background:#fff3cd; margin:10px 0;'>
        <strong>Score Components:</strong> PRSI bearish (+25) | Below PSAR (+15-20) | Fresh signal (+10) | 
        OBV distribution (+15) | DMI bearish (+10) | Overbought Will%R (+15) | High ATR (+10) | Low SI (+5)<br>
        <strong>Penalties:</strong> PRSI bullish (-30) | Above PSAR (-20) | Oversold Will%R (-15) | High SI squeeze risk (-25)
    </div>
    """
    
    # Single list of short candidates with options
    if short_candidates:
        html += build_shorts_html_section(short_candidates, f"🔴 SHORT CANDIDATES ({len(short_candidates)} stocks)", "#c0392b")
    else:
        html += """
        <div style='padding:20px; background:#f9f9f9; text-align:center; color:#666;'>
            No short candidates found with tradeable options.
        </div>
        """
    
    # Legend
    html += """
    <div style='font-size:10px; color:#666; margin-top:20px; padding:10px; background:#f9f9f9;'>
        <strong>Legend:</strong><br>
        <strong>SSI (Smart Short Indicator):</strong> 0-10 | Days 1-5: 30% Gap + 25% OBV + 25% Will%R + 20% ATR | Days 6+: 30% Slope + 25% ADX + 25% OBV + 20% ATR<br>
        &nbsp;&nbsp;&nbsp;<span style='color:#c0392b'>9-10 = Prime</span> | <span style='color:#e74c3c'>8 = Good</span> | <span style='color:#f39c12'>6-7 = OK</span> | <span style='color:#95a5a6'>4-5 = Weak</span> | <span style='color:#27ae60'>0-3 = Avoid</span><br>
        PRSI: ↘️ Bearish | OBV: 🔴 Distribution (good) 🟢 Accumulation (bad)<br>
        Squeeze Risk: 🟢 Low (<15% SI) 🟡 Moderate (15-25%) 🔴 High (>25%)<br>
        Will%R: Red = Overbought (good entry) | Green = Oversold (bounce risk)<br>
        <strong>Links:</strong> 📊 Optionstrat | 📈 Fidelity Buy Put | 📉 Fidelity Sell Put<br>
        <strong>Put Spread Strategy:</strong> Buy higher strike put, sell lower strike put. Max loss = spread cost. Max profit = strike diff - cost.
    </div>
    """
    
    html += "</body></html>"
    return html


def build_shorts_watchlist_html(
    prime_shorts: List[ShortCandidate],
    short_candidates: List[ShortCandidate],
    not_ready: List[ShortCandidate],
    avoid: List[ShortCandidate],
    mode: str = "Shorts",
    total_scanned: int = 0
) -> str:
    """Build HTML report for shorts watchlist - shows ALL stocks with categories."""
    
    html = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; font-size: 12px; }
            table { border-collapse: collapse; width: 100%; margin: 10px 0; }
            th { padding: 8px; text-align: left; font-size: 11px; }
            td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }
            tr:hover { background-color: #f5f5f5; }
        </style>
    </head>
    <body>
    """
    
    html += f"""
    <h2>🐻 Short Watchlist Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>
    <p>Mode: {mode} | Analyzed: {total_scanned} stocks from shorts.txt</p>
    """
    
    # Summary
    html += f"""
    <div style='background-color:#f5f5f5; padding:15px; margin:10px 0; border-left:4px solid #c0392b;'>
        <strong>📊 WATCHLIST BREAKDOWN:</strong><br>
        🔴🔴 <strong>{len(prime_shorts)} Prime Shorts</strong> (Execute now) |
        🔴 <strong>{len(short_candidates)} Short Candidates</strong> (Good setups) |
        ⏳ <strong>{len(not_ready)} Not Ready</strong> (Watch) |
        ❌ <strong>{len(avoid)} Avoid</strong> (Wrong direction)
    </div>
    """
    
    # Guide
    html += """
    <div style='font-size:10px; color:#666; padding:10px; background:#fff3cd; margin:10px 0;'>
        <strong>Score Components:</strong> PRSI bearish (+25) | Below PSAR (+15-20) | Fresh signal (+10) | 
        OBV distribution (+15) | DMI bearish (+10) | Overbought Will%R (+15) | High ATR (+10) | Low SI (+5)<br>
        <strong>Penalties:</strong> PRSI bullish (-30) | Above PSAR (-20) | Oversold Will%R (-15) | High SI squeeze risk (-25)
    </div>
    """
    
    # Prime Shorts
    if prime_shorts:
        html += build_shorts_html_section(prime_shorts, f"🔴🔴 PRIME SHORTS - Execute Now ({len(prime_shorts)})", "#c0392b")
    
    # Short Candidates
    if short_candidates:
        html += build_shorts_html_section(short_candidates, f"🔴 SHORT CANDIDATES - Good Setups ({len(short_candidates)})", "#e74c3c")
    
    # Not Ready
    if not_ready:
        html += build_shorts_html_section(not_ready, f"⏳ NOT READY - Watch for Breakdown ({len(not_ready)})", "#f39c12")
    
    # Avoid
    if avoid:
        html += build_avoid_section(avoid)
    
    # Legend
    html += """
    <div style='font-size:10px; color:#666; margin-top:20px; padding:10px; background:#f9f9f9;'>
        <strong>Legend:</strong><br>
        <strong>SSI (Smart Short Indicator):</strong> 0-10 | Days 1-5: 30% Gap + 25% OBV + 25% Will%R + 20% ATR | Days 6+: 30% Slope + 25% ADX + 25% OBV + 20% ATR<br>
        &nbsp;&nbsp;&nbsp;<span style='color:#c0392b'>9-10 = Prime</span> | <span style='color:#e74c3c'>8 = Good</span> | <span style='color:#f39c12'>6-7 = OK</span> | <span style='color:#95a5a6'>4-5 = Weak</span> | <span style='color:#27ae60'>0-3 = Avoid</span><br>
        PRSI: ↘️ Bearish (good) ↗️ Bullish (bad) | OBV: 🔴 Distribution (good) 🟢 Accumulation (bad)<br>
        Squeeze Risk: 🟢 Low (<15% SI) 🟡 Moderate (15-25%) 🔴 High (>25%)<br>
        Will%R: Red = Overbought (good entry) | Green = Oversold (bounce risk)<br>
        <strong>Links:</strong> 📊 Optionstrat | 📈 Fidelity Buy Put | 📉 Fidelity Sell Put<br>
        <strong>Put Spread Strategy:</strong> Buy higher strike put, sell lower strike put. Max loss = spread cost. Max profit = strike diff - cost.
    </div>
    """
    
    html += "</body></html>"
    return html
