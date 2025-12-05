"""
Covered Call Analysis Module

Analyzes high-ATR stocks for covered call opportunities.
Uses Williams %R trajectory, ATR, and options data to suggest strikes.
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import math


@dataclass
class CoveredCallSuggestion:
    """Suggested covered call parameters."""
    ticker: str
    current_price: float
    atr_percent: float
    williams_r: float
    adx_value: float
    estimated_ceiling: float
    upside_potential: float
    suggested_strike: float
    strike_otm_percent: float
    expiration_date: str
    days_to_expiry: int
    delta: Optional[float] = None
    premium: Optional[float] = None
    premium_yield: Optional[float] = None
    signal_type: str = ""


def estimate_price_ceiling(current_price, atr_percent, williams_r, adx_value, days_out=15):
    """Estimate likely price ceiling based on technicals."""
    if williams_r <= -80:
        williams_room = 1.0
    elif williams_r <= -50:
        williams_room = 0.7
    elif williams_r <= -20:
        williams_room = 0.4
    else:
        williams_room = 0.15
    
    if adx_value < 15:
        adx_mult = 0.7
    elif adx_value < 25:
        adx_mult = 0.9
    elif adx_value < 35:
        adx_mult = 1.1
    else:
        adx_mult = 1.3
    
    sqrt_days = math.sqrt(days_out)
    base_move_pct = atr_percent * sqrt_days
    adjusted_move_pct = min(base_move_pct * williams_room * adx_mult, 30.0)
    ceiling_price = current_price * (1 + adjusted_move_pct / 100)
    return ceiling_price, adjusted_move_pct


def get_option_chain_data(ticker, current_price, target_delta=0.09, min_days=10, max_days=30):
    """Fetch options chain and find strike closest to target delta."""
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return None
        
        today = datetime.now().date()
        target_exp = None
        
        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
            days_to_exp = (exp_date - today).days
            if min_days <= days_to_exp <= max_days:
                target_exp = exp_str
                break
        
        if not target_exp:
            for exp_str in expirations:
                exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
                if (exp_date - today).days >= min_days:
                    target_exp = exp_str
                    break
        
        if not target_exp:
            return None
        
        chain = stock.option_chain(target_exp)
        calls = chain.calls
        if calls.empty:
            return None
        
        otm_calls = calls[calls['strike'] > current_price].copy()
        if otm_calls.empty:
            return None
        
        otm_calls['otm_pct'] = (otm_calls['strike'] - current_price) / current_price * 100
        
        best_row = None
        delta = None
        
        if 'delta' in otm_calls.columns and otm_calls['delta'].notna().any():
            valid_delta = otm_calls[otm_calls['delta'].notna()].copy()
            if not valid_delta.empty:
                valid_delta['delta_diff'] = abs(valid_delta['delta'] - target_delta)
                best_row = valid_delta.loc[valid_delta['delta_diff'].idxmin()]
                delta = best_row.get('delta')
        
        if best_row is None:
            # No delta data - target 15% OTM for ~delta 9
            target_otm = 15.0
            otm_calls['target_diff'] = abs(otm_calls['otm_pct'] - target_otm)
            best_row = otm_calls.loc[otm_calls['target_diff'].idxmin()]
        
        strike = best_row['strike']
        actual_otm_pct = (strike - current_price) / current_price * 100
        
        bid = best_row.get('bid', 0) or 0
        ask = best_row.get('ask', 0) or 0
        premium = (bid + ask) / 2 if bid > 0 and ask > 0 else (best_row.get('lastPrice', 0) or 0)
        
        exp_date = datetime.strptime(target_exp, '%Y-%m-%d').date()
        
        return {
            'strike': strike,
            'expiration': target_exp,
            'days_to_expiry': (exp_date - today).days,
            'delta': delta,
            'premium': premium,
            'premium_yield': (premium / current_price * 100) if current_price > 0 else 0,
            'otm_percent': actual_otm_pct,
        }
    except Exception as e:
        print(f"    Warning: Could not fetch options for {ticker}: {e}")
        return None


def analyze_covered_call(ticker, current_price, atr_percent, williams_r, adx_value, signal_type="", fetch_options=True):
    """Analyze a stock for covered call opportunity."""
    ceiling, upside_pct = estimate_price_ceiling(current_price, atr_percent, williams_r, adx_value, 15)
    
    # 15% buffer above ceiling for strike
    suggested_strike = ceiling * 1.15
    
    # Round to standard option increments
    if suggested_strike < 20:
        suggested_strike = round(suggested_strike * 2) / 2
    elif suggested_strike < 100:
        suggested_strike = round(suggested_strike)
    elif suggested_strike < 200:
        suggested_strike = round(suggested_strike / 2.5) * 2.5
    else:
        suggested_strike = round(suggested_strike / 5) * 5
    
    strike_otm = (suggested_strike - current_price) / current_price * 100
    
    today = datetime.now()
    days_to_friday = (4 - today.weekday()) % 7 or 7
    target_friday = today + timedelta(days=days_to_friday + 14)
    
    suggestion = CoveredCallSuggestion(
        ticker=ticker,
        current_price=current_price,
        atr_percent=atr_percent,
        williams_r=williams_r,
        adx_value=adx_value,
        estimated_ceiling=ceiling,
        upside_potential=upside_pct,
        suggested_strike=suggested_strike,
        strike_otm_percent=strike_otm,
        expiration_date=target_friday.strftime('%Y-%m-%d'),
        days_to_expiry=21,
        signal_type=signal_type
    )
    
    if fetch_options:
        options_data = get_option_chain_data(ticker, current_price, target_delta=0.09)
        if options_data:
            suggestion.suggested_strike = options_data['strike']
            suggestion.strike_otm_percent = options_data['otm_percent']
            suggestion.expiration_date = options_data['expiration']
            suggestion.days_to_expiry = options_data['days_to_expiry']
            suggestion.delta = options_data['delta']
            suggestion.premium = options_data['premium']
            suggestion.premium_yield = options_data['premium_yield']
    
    return suggestion


def build_covered_call_section(suggestions):
    """Build HTML section for covered call suggestions."""
    if not suggestions:
        return ""
    
    html = """
    <div style='background-color:#8e44ad; color:white; padding:12px; margin:20px 0 10px 0; font-size:14px; font-weight:bold;'>
        📞 COVERED CALL CANDIDATES - High Volatility Stocks
    </div>
    <p style='color:#8e44ad; font-size:11px; margin:5px 0;'>
        High ATR stocks suitable for covered calls. Strikes target ~Delta 9 (~9% ITM probability) with 2-4 week expiration.
    </p>
    <table>
        <tr style='background-color:#8e44ad; color:white;'>
            <th>Ticker</th><th>Price</th><th>ATR%</th><th>Will%R</th><th>ADX</th>
            <th>Est.Ceiling</th><th>Strike</th><th>OTM%</th><th>Expiry</th>
            <th>Delta</th><th>Premium</th><th>Yield</th>
        </tr>
    """
    
    for s in suggestions:
        if s.williams_r <= -80:
            wc = '#27ae60'
        elif s.williams_r <= -50:
            wc = '#2ecc71'
        elif s.williams_r <= -20:
            wc = '#f39c12'
        else:
            wc = '#e74c3c'
        
        delta_d = f"{s.delta:.2f}" if s.delta else "~0.09"
        prem_d = f"${s.premium:.2f}" if s.premium else "-"
        yield_d = f"{s.premium_yield:.1f}%" if s.premium_yield else "-"
        
        html += f"""
        <tr>
            <td><strong>{s.ticker}</strong></td>
            <td>${s.current_price:.2f}</td>
            <td style='color:#e74c3c; font-weight:bold;'>{s.atr_percent:.1f}%</td>
            <td style='color:{wc};'>{s.williams_r:.0f}</td>
            <td>{s.adx_value:.0f}</td>
            <td style='color:#27ae60;'>${s.estimated_ceiling:.2f}</td>
            <td style='font-weight:bold;'>${s.suggested_strike:.2f}</td>
            <td>{s.strike_otm_percent:.1f}%</td>
            <td>{s.expiration_date}</td>
            <td>{delta_d}</td>
            <td>{prem_d}</td>
            <td style='color:#27ae60;'>{yield_d}</td>
        </tr>"""
    
    html += """</table>
    <div style='font-size:10px; color:#666; margin-top:10px; padding:8px; background:#f9f9f9; border-left:3px solid #8e44ad;'>
        <strong>Legend:</strong> Est.Ceiling = price target based on Williams %R room + ATR + ADX | 
        Strike targets delta ~0.09 | OTM% = distance from current price
    </div>"""
    
    return html
