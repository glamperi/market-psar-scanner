"""
Covered Call Analysis Module
Analyzes stocks for covered call opportunities with options data.
Uses utils.options_data for Schwab -> yfinance fallback chain.
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class CoveredCallSuggestion:
    """Data class for covered call suggestion."""
    ticker: str
    price: float
    atr_percent: float
    williams_r: float
    adx_value: float
    signal_type: str
    
    # Options data (filled if fetch_options=True)
    expiration: Optional[str] = None
    strike: Optional[float] = None
    premium: Optional[float] = None
    days_to_exp: Optional[int] = None
    upside_pct: Optional[float] = None
    premium_pct: Optional[float] = None
    annualized_yield: Optional[float] = None
    source: str = 'none'


def get_covered_call_data(ticker: str, current_price: float, min_days: int = 21, max_days: int = 60) -> Optional[dict]:
    """Get covered call data using unified options fetcher."""
    try:
        from utils.options_data import fetch_options_chain, find_cc_calls
        
        # Fetch options chain (calls only for efficiency)
        chain = fetch_options_chain(ticker, min_days, max_days, option_type='CALL')
        if not chain or not chain.get('calls'):
            return None
        
        # Find best call for covered call
        best_call = find_cc_calls(chain['calls'], current_price, target_otm_pct=8.0)
        if not best_call:
            return None
        
        # Calculate metrics
        exp_date = chain['expiration']
        today = datetime.now().date()
        exp = datetime.strptime(exp_date, '%Y-%m-%d').date()
        days_to_exp = (exp - today).days
        
        premium_pct = best_call['premium_pct']
        annualized = (premium_pct / days_to_exp) * 365 if days_to_exp > 0 else 0
        
        return {
            'expiration': exp_date,
            'strike': best_call['strike'],
            'premium': best_call['mid'],
            'days_to_exp': days_to_exp,
            'upside_pct': best_call['upside_pct'],
            'premium_pct': premium_pct,
            'annualized_yield': annualized,
            'source': chain.get('source', 'unknown')
        }
    except ImportError:
        pass  # utils.options_data not available
    except Exception:
        pass
    return None


def estimate_price_ceiling(
    current_price: float,
    atr_percent: float,
    williams_r: float = -50,
    adx_value: float = 20
) -> dict:
    """
    Estimate price ceiling for covered call strike selection.
    
    Uses ATR and technical indicators to estimate how far price might move.
    
    Args:
        current_price: Current stock price
        atr_percent: ATR as percentage of price
        williams_r: Williams %R value (-100 to 0)
        adx_value: ADX trend strength
    
    Returns:
        Dict with:
        - ceiling_price: Estimated max price in timeframe
        - ceiling_pct: Ceiling as % above current
        - confidence: 'high', 'medium', 'low'
        - reasoning: Explanation
    """
    # Base ceiling: 2x ATR (covers ~95% of moves in 2-4 weeks)
    base_ceiling_pct = atr_percent * 2
    
    # Adjust based on Williams %R (momentum)
    # Overbought (near 0) = likely to pull back, lower ceiling
    # Oversold (near -100) = room to run, higher ceiling
    if williams_r > -20:
        # Overbought - reduce ceiling
        momentum_adj = -0.3
        momentum_note = "overbought, likely pullback"
    elif williams_r < -80:
        # Oversold - increase ceiling
        momentum_adj = 0.3
        momentum_note = "oversold, room to run"
    else:
        momentum_adj = 0
        momentum_note = "neutral momentum"
    
    # Adjust based on ADX (trend strength)
    # Strong trend = more likely to continue
    if adx_value > 40:
        trend_adj = 0.2
        trend_note = "very strong trend"
        confidence = 'low'  # Strong trends can extend further
    elif adx_value > 25:
        trend_adj = 0.1
        trend_note = "strong trend"
        confidence = 'medium'
    else:
        trend_adj = 0
        trend_note = "weak/no trend"
        confidence = 'high'  # Easier to predict range-bound
    
    # Calculate final ceiling
    ceiling_pct = base_ceiling_pct * (1 + momentum_adj + trend_adj)
    ceiling_price = current_price * (1 + ceiling_pct / 100)
    
    return {
        'ceiling_price': ceiling_price,
        'ceiling_pct': ceiling_pct,
        'confidence': confidence,
        'reasoning': f"Base {base_ceiling_pct:.1f}% (2x ATR), {momentum_note}, {trend_note}"
    }


def analyze_covered_call(
    ticker: str,
    current_price: float,
    atr_percent: float,
    williams_r: float = -50,
    adx_value: float = 20,
    signal_type: str = "Buy",
    fetch_options: bool = True
) -> Optional[CoveredCallSuggestion]:
    """
    Analyze a stock for covered call opportunity.
    
    Args:
        ticker: Stock symbol
        current_price: Current stock price
        atr_percent: ATR as % of price
        williams_r: Williams %R value
        adx_value: ADX value
        signal_type: "Strong Buy", "Buy", or "Hold"
        fetch_options: Whether to fetch actual options data
    
    Returns:
        CoveredCallSuggestion or None
    """
    suggestion = CoveredCallSuggestion(
        ticker=ticker,
        price=current_price,
        atr_percent=atr_percent,
        williams_r=williams_r,
        adx_value=adx_value,
        signal_type=signal_type
    )
    
    if fetch_options:
        options_data = get_covered_call_data(ticker, current_price)
        
        if options_data:
            suggestion.expiration = options_data['expiration']
            suggestion.strike = options_data['strike']
            suggestion.premium = options_data['premium']
            suggestion.days_to_exp = options_data['days_to_exp']
            suggestion.upside_pct = options_data['upside_pct']
            suggestion.premium_pct = options_data['premium_pct']
            suggestion.annualized_yield = options_data['annualized_yield']
            suggestion.source = options_data['source']
    
    return suggestion


def build_trade_links(ticker: str, expiration: str, strike: float) -> str:
    """Build OptionStrat and Fidelity trade links."""
    try:
        exp_yymmdd = expiration[2:4] + expiration[5:7] + expiration[8:10]  # "251219"
        exp_mmddyyyy = f"{expiration[5:7]}/{expiration[8:10]}/{expiration[0:4]}"  # "12/19/2025"
        strike_int = int(strike)
        
        # OptionStrat URL
        optionstrat_url = f"https://optionstrat.com/build/covered-call/{ticker}/{ticker}x100,-.{ticker}{exp_yymmdd}C{strike_int}"
        
        # Fidelity URL
        fid_base = "https://researchtools.fidelity.com/ftgw/mloptions/goto/plCalculator"
        fid_sellc = f"{fid_base}?ulSymbol={ticker}&ulSecurity=E&ulAction=I&ulQuantity=0&strategy=SL&optSymbol1=-{ticker}{exp_yymmdd}C{strike_int}&optSecurity1=O&optAction1=S&optExp1={exp_mmddyyyy}&optStrike1={strike_int}&optType1=C&optQuantity1=1"
        
        return f'<a href="{optionstrat_url}" target="_blank" style="color:#007bff;">📊 Trade</a> | <a href="{fid_sellc}" target="_blank" style="font-size:10px;">F-SellC</a>'
    except:
        return "-"


def build_covered_call_section(suggestions: List[CoveredCallSuggestion]) -> str:
    """Build HTML section for covered call opportunities."""
    if not suggestions:
        return ""
    
    html = """
    <div class='section-warning' style='background-color:#e67e22; color:white; padding:12px; margin:20px 0 10px 0; font-size:14px; font-weight:bold;'>
        📞 COVERED CALL CANDIDATES - High ATR Stocks ({} stocks)
    </div>
    <p style='color:#e67e22; font-size:11px; margin:5px 0;'>
        Stocks with ATR &gt; 5% in buy zones. High volatility = higher premiums. Sorted by ATR%.
    </p>
    """.format(len(suggestions))
    
    html += """
    <table>
        <tr class='th-warning' style='background-color:#e67e22; color:white;'>
            <th>Ticker</th>
            <th>Price</th>
            <th>Signal</th>
            <th>ATR%</th>
            <th>W%R</th>
            <th>ADX</th>
            <th>Exp (DTE)</th>
            <th>Strike</th>
            <th>Upside</th>
            <th>Ann.Yield</th>
            <th>Trade</th>
        </tr>
    """
    
    for s in suggestions:
        # Signal color
        if s.signal_type == "Strong Buy":
            signal_color = "#1e8449"
        elif s.signal_type == "Buy":
            signal_color = "#27ae60"
        else:
            signal_color = "#f39c12"
        
        # Options data display
        if s.expiration and s.strike:
            exp_display = f"{s.expiration} ({s.days_to_exp}d)"
            strike_display = f"${s.strike:.0f}"
            upside_display = f"+{s.upside_pct:.1f}%"
            yield_display = f"<strong>{s.annualized_yield:.0f}%</strong>"
            trade_link = build_trade_links(s.ticker, s.expiration, s.strike)
        else:
            exp_display = "-"
            strike_display = "-"
            upside_display = "-"
            yield_display = "-"
            trade_link = "-"
        
        # W%R color (closer to 0 = more overbought)
        if s.williams_r > -20:
            wr_color = "#e74c3c"  # Overbought
        elif s.williams_r < -80:
            wr_color = "#27ae60"  # Oversold
        else:
            wr_color = "#333"
        
        html += f"""
        <tr id='cc-{s.ticker}'>
            <td><strong>{s.ticker}</strong></td>
            <td>${s.price:.2f}</td>
            <td style='color:{signal_color};'>{s.signal_type}</td>
            <td style='color:#e74c3c;'><strong>{s.atr_percent:.1f}%</strong></td>
            <td style='color:{wr_color};'>{s.williams_r:.0f}</td>
            <td>{s.adx_value:.0f}</td>
            <td>{exp_display}</td>
            <td>{strike_display}</td>
            <td>{upside_display}</td>
            <td>{yield_display}</td>
            <td>{trade_link}</td>
        </tr>
        """
    
    html += "</table>"
    
    # Add legend
    html += """
    <p style='font-size:10px; color:#7f8c8d; margin-top:5px;'>
        📊 Trade = OptionStrat P&L analyzer | F-SellC = Fidelity sell call calculator<br>
        Higher ATR% = higher premiums but more volatile. W%R near 0 = overbought (good time to sell calls).
    </p>
    """
    
    return html
