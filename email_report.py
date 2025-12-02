"""
Market Scanner Email Report Generator
Groups stocks by PSAR zones with Momentum Score (1-10)
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

EXIT_HISTORY_FILE = 'exit_history.json'

class EmailReport:
    def __init__(self, scan_results, eps_filter=None, rev_filter=None, mc_filter=None):
        self.scan_results = scan_results
        self.all_results = scan_results['all_results']
        self.watchlist_results = scan_results['watchlist_results']
        self.eps_filter = eps_filter
        self.rev_filter = rev_filter
        self.mc_filter = mc_filter if mc_filter else 10  # Default $10B
        
        self.exit_history = self.load_exit_history()
        self.recent_exits = self.update_exit_history()
        
    def load_exit_history(self):
        if os.path.exists(EXIT_HISTORY_FILE):
            try:
                with open(EXIT_HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_exit_history(self):
        try:
            with open(EXIT_HISTORY_FILE, 'w') as f:
                json.dump(self.exit_history, f, indent=2)
        except:
            pass
    
    def update_exit_history(self):
        now = datetime.now()
        cutoff = now - timedelta(days=7)
        
        current_buys = set(r['ticker'] for r in self.all_results if r.get('psar_zone') in ['STRONG_BUY', 'BUY'])
        current_others = {r['ticker']: r for r in self.all_results if r.get('psar_zone') not in ['STRONG_BUY', 'BUY']}
        
        previous_buys = set(self.exit_history.get('previous_buys', []))
        
        new_exits = []
        for ticker in previous_buys:
            if ticker in current_others and ticker not in current_buys:
                result = current_others[ticker]
                new_exits.append({
                    'ticker': ticker,
                    'exit_date': now.isoformat(),
                    'exit_price': result['price'],
                    'psar_zone': result.get('psar_zone', 'UNKNOWN'),
                    'psar_momentum': result.get('psar_momentum', 5),
                })
        
        exits_list = self.exit_history.get('exits', []) + new_exits
        recent_exits = [e for e in exits_list if datetime.fromisoformat(e['exit_date']) >= cutoff]
        
        self.exit_history = {
            'previous_buys': list(current_buys),
            'exits': recent_exits,
            'last_updated': now.isoformat()
        }
        self.save_exit_history()
        return sorted(recent_exits, key=lambda x: x['exit_date'], reverse=True)
    
    def get_indicator_symbols(self, r):
        def sym(val):
            return "<span style='color:#27ae60;'>✓</span>" if val else "<span style='color:#e74c3c;'>✗</span>"
        return f"M{sym(r.get('has_macd'))} B{sym(r.get('has_bb'))} W{sym(r.get('has_willr'))} C{sym(r.get('has_coppock'))} U{sym(r.get('has_ultimate'))}"
    
    def get_obv_display(self, obv_status):
        """Get OBV status display"""
        if obv_status == 'CONFIRM':
            return "<span style='color:#27ae60;'>🟢</span>"
        elif obv_status == 'DIVERGE':
            return "<span style='color:#c0392b;'>🔴</span>"
        else:
            return "<span style='color:#f39c12;'>🟡</span>"
    
    def get_zone_color(self, zone):
        return {'STRONG_BUY': '#1e8449', 'BUY': '#27ae60', 'NEUTRAL': '#f39c12', 'WEAK': '#e67e22', 'SELL': '#c0392b'}.get(zone, '#7f8c8d')
    
    def get_zone_emoji(self, zone):
        return {'STRONG_BUY': '🟢🟢', 'BUY': '🟢', 'NEUTRAL': '🟡', 'WEAK': '🟠', 'SELL': '🔴'}.get(zone, '⚪')
    
    def get_momentum_display(self, momentum):
        """Get colored momentum score display"""
        if momentum >= 8:
            return f"<span style='color:#1e8449; font-weight:bold;'>{momentum}</span>"
        elif momentum >= 6:
            return f"<span style='color:#27ae60;'>{momentum}</span>"
        elif momentum >= 4:
            return f"<span style='color:#f39c12;'>{momentum}</span>"
        elif momentum >= 2:
            return f"<span style='color:#e67e22;'>{momentum}</span>"
        else:
            return f"<span style='color:#c0392b;'>{momentum}</span>"
    
    def build_email_body(self):
        # Count total scanned (before market cap filter) - estimate from typical scan
        total_scanned = len(self.all_results) + 2000  # Rough estimate of filtered stocks
        
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; font-size: 12px; }
                table { border-collapse: collapse; width: 100%; margin: 10px 0; }
                th { padding: 8px; text-align: left; font-size: 11px; }
                td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }
                tr:hover { background-color: #f5f5f5; }
                
                .section-toptier { background-color: #145a32; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-strongbuy { background-color: #1e8449; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-buy { background-color: #27ae60; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-neutral { background-color: #f39c12; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-weak { background-color: #e67e22; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-sell { background-color: #c0392b; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-purple { background-color: #8e44ad; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-gray { background-color: #7f8c8d; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-red { background-color: #c0392b; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-yellow { background-color: #f39c12; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
                
                .th-toptier { background-color: #145a32; color: white; }
                .th-strongbuy { background-color: #1e8449; color: white; }
                .th-buy { background-color: #27ae60; color: white; }
                .th-neutral { background-color: #f39c12; color: white; }
                .th-weak { background-color: #e67e22; color: white; }
                .th-sell { background-color: #c0392b; color: white; }
                .th-purple { background-color: #8e44ad; color: white; }
                .th-gray { background-color: #7f8c8d; color: white; }
                .th-yellow { background-color: #e67e22; color: white; }
                
                .alert-box { padding: 10px; margin: 10px 0; border-radius: 5px; }
                .alert-green { background-color: #d4edda; border-left: 4px solid #27ae60; }
                .alert-red { background-color: #f8d7da; border-left: 4px solid #c0392b; }
                .summary-box { background-color: #ecf0f1; padding: 15px; margin: 15px 0; border-radius: 5px; }
            </style>
        </head>
        <body>
        """
        
        html += f"<h2>📈 Market Scanner Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>"
        
        # Build filter description
        filter_parts = [f"${self.mc_filter}B+ market cap"]
        if self.eps_filter:
            filter_parts.append(f"EPS growth ≥{self.eps_filter}%")
        if self.rev_filter:
            filter_parts.append(f"Rev growth ≥{self.rev_filter}%")
        filter_desc = " | ".join(filter_parts)
        
        html += f"<p style='color:#7f8c8d; font-size:11px;'>Scanned ~2,500 stocks from S&P 500, NASDAQ 100, Russell 2000, IBD | Filtered: {filter_desc} | {len(self.all_results)} stocks passed</p>"
        
        # MARKET SENTIMENT from CBOE (using Selenium)
        try:
            from cboe import get_cboe_ratios_and_analyze
            sentiment_text = get_cboe_ratios_and_analyze()
            
            if sentiment_text and 'FAILED' not in sentiment_text:
                # Format the output nicely
                html += f"""
                <div style='background-color:#ecf0f1; border-left:4px solid #2c3e50; padding:12px; margin:10px 0;'>
                    <pre style='font-family: monospace; white-space: pre-wrap; margin: 0; font-size: 12px; color: #333;'>{sentiment_text}</pre>
                </div>
                """
            else:
                # Show error
                html += f"""
                <div style='background-color:#f8d7da; border-left:4px solid #dc3545; padding:12px; margin:10px 0;'>
                    <pre style='font-family: monospace; white-space: pre-wrap; margin: 0; font-size: 12px; color: #c0392b;'>{sentiment_text}</pre>
                </div>
                """
        except Exception as e:
            pass  # Skip if cboe.py not available
        
        # ZONE GUIDE
        html += """
        <div class='section-gray'>📊 PSAR ZONE & MOMENTUM GUIDE</div>
        <table>
            <tr><th class='th-gray'>Zone</th><th class='th-gray'>PSAR %</th><th class='th-gray'>Criteria</th><th class='th-gray'>Action</th></tr>
            <tr style='background-color:#c8e6c9;'><td><strong>🟢🟢🟢 STRONG BUY</strong></td><td>> +5%</td><td>+ Momentum≥7 + IR≥40 + Above 50MA + OBV🟢</td><td>Best opportunities</td></tr>
            <tr style='background-color:#d4edda;'><td><strong>🟢🟢 BUY</strong></td><td>> +5%</td><td>Confirmed uptrend</td><td>Hold / Add on dips</td></tr>
            <tr style='background-color:#e8f5e9;'><td><strong>🟢 BUY</strong></td><td>+2% to +5%</td><td>Healthy signal</td><td>Hold / Watch</td></tr>
            <tr style='background-color:#fff8e1;'><td><strong>🟡 NEUTRAL</strong></td><td>-2% to +2%</td><td>Could flip either way</td><td>Watch closely</td></tr>
            <tr style='background-color:#ffebee;'><td><strong>🟠 WEAK</strong></td><td>-5% to -2%</td><td>Sell but could reverse</td><td>Covered calls / stops</td></tr>
            <tr style='background-color:#f8d7da;'><td><strong>🔴 SELL</strong></td><td>< -5%</td><td>Confirmed downtrend</td><td>Exit or hedge</td></tr>
        </table>
        <p style='font-size:10px; color:#7f8c8d;'>
        <strong>Momentum (1-10):</strong> Trajectory since signal start. 8-10=Strong, 4-7=Neutral, 1-3=Weak<br>
        <strong>IR (Indicator Rating):</strong> MACD(30) + Ultimate(30) + Williams(20) + Bollinger(10) + Coppock(10) = Max 100<br>
        <strong>OBV:</strong> 🟢=Volume confirms price | 🟡=Neutral | 🔴=Divergence warning<br>
        <strong>⭐ = IBD Stock</strong> (Investor's Business Daily growth stock list)
        </p>
        """
        
        # Categorize stocks into tiers
        all_strong = [r for r in self.all_results if r.get('psar_zone') == 'STRONG_BUY' and not r.get('is_watchlist')]
        
        # TOP TIER: PSAR>5% + Momentum>=7 + IR>=40 + Above 50MA + OBV Confirms + NOT Overbought
        top_tier = [r for r in all_strong if 
                    r.get('psar_momentum', 0) >= 7 and 
                    r.get('signal_weight', 0) >= 40 and 
                    r.get('above_ma50', False) and
                    r.get('obv_status', 'NEUTRAL') == 'CONFIRM' and
                    r.get('atr_status', 'NORMAL') != 'OVERBOUGHT']  # Exclude overextended!
        
        # STRONG BUY: Rest of >5%
        strong_buy = [r for r in all_strong if r not in top_tier]
        
        # BUY: +2% to +5%
        buy = [r for r in self.all_results if r.get('psar_zone') == 'BUY' and not r.get('is_watchlist')]
        
        # Other zones
        neutral = [r for r in self.all_results if r.get('psar_zone') == 'NEUTRAL' and not r.get('is_watchlist')]
        weak = [r for r in self.all_results if r.get('psar_zone') == 'WEAK' and not r.get('is_watchlist')]
        sell = [r for r in self.all_results if r.get('psar_zone') == 'SELL' and not r.get('is_watchlist')]
        
        # Sort each by momentum then IR
        for lst in [top_tier, strong_buy, buy, neutral, weak, sell]:
            lst.sort(key=lambda x: (-x.get('psar_momentum', 0), -x.get('signal_weight', 0)))
        
        # Count overbought stocks in buy zones (warning)
        overbought_buys = [r for r in self.all_results 
                          if r.get('psar_zone') in ['STRONG_BUY', 'BUY'] 
                          and r.get('atr_status') == 'OVERBOUGHT']
        
        # Count oversold stocks (best entries)
        oversold_stocks = [r for r in self.all_results 
                          if r.get('atr_status') == 'OVERSOLD']
        
        # SUMMARY
        html += f"""
        <div class='summary-box'>
            <h3 style='margin-top:0;'>Market Summary</h3>
            <table style='width:auto;'>
                <tr><td>🟢🟢🟢 <strong>STRONG BUY (Top Tier):</strong></td><td><strong>{len(top_tier)}</strong></td></tr>
                <tr><td>🟢🟢 <strong>BUY (Confirmed):</strong></td><td><strong>{len(strong_buy)}</strong></td></tr>
                <tr><td>🟢 <strong>BUY:</strong></td><td>{len(buy)}</td></tr>
                <tr><td>🟡 <strong>NEUTRAL:</strong></td><td>{len(neutral)}</td></tr>
                <tr><td>🟠 <strong>WEAK:</strong></td><td>{len(weak)}</td></tr>
                <tr><td>🔴 <strong>SELL:</strong></td><td>{len(sell)}</td></tr>
            </table>
            <p style='font-size:10px; margin-top:8px;'>
                🔥 <strong>Overbought (avoid buying):</strong> {len(overbought_buys)} stocks in buy zones are overextended<br>
                ❄️ <strong>Oversold (best entries):</strong> {len(oversold_stocks)} stocks at good entry points
            </p>
        </div>
        """
        
        # EXITS ALERT
        if self.recent_exits:
            html += "<div class='section-red'>🚨 RECENT ZONE EXITS (Last 7 Days)</div>"
            html += "<table><tr><th class='th-sell'>Ticker</th><th class='th-sell'>Exit Date</th><th class='th-sell'>Now Zone</th><th class='th-sell'>Momentum</th></tr>"
            for e in self.recent_exits[:15]:
                date_str = datetime.fromisoformat(e['exit_date']).strftime('%m/%d') if 'exit_date' in e else "?"
                html += f"<tr><td><strong>{e['ticker']}</strong></td><td>{date_str}</td><td>{self.get_zone_emoji(e.get('psar_zone','?'))} {e.get('psar_zone','?')}</td><td>{self.get_momentum_display(e.get('psar_momentum', 5))}</td></tr>"
            html += "</table>"
        
        # HIGH MOMENTUM IMPROVING
        improving = [r for r in self.all_results if r.get('psar_zone') in ['SELL', 'WEAK', 'NEUTRAL'] and r.get('psar_momentum', 0) >= 6 and r.get('psar_distance', 0) < 0]
        if improving:
            improving.sort(key=lambda x: -x.get('psar_momentum', 0))
            html += "<div class='alert-box alert-green'>"
            html += f"<strong>⬆️ {len(improving)} stocks improving rapidly (Momentum ≥6):</strong> "
            html += ", ".join([f"<strong>{r['ticker']}</strong> ({r['psar_distance']:+.1f}%, M:{r['psar_momentum']})" for r in improving[:10]])
            if len(improving) > 10:
                html += f" +{len(improving)-10} more"
            html += "</div>"
        
        # ATR OVERBOUGHT WARNING - Stocks in buy zones that are overextended
        if overbought_buys:
            overbought_buys.sort(key=lambda x: -x.get('psar_distance', 0))
            html += "<div class='alert-box' style='background-color:#fff3cd; border-left:4px solid #ffc107;'>"
            html += f"<strong>🔥 {len(overbought_buys)} BUY zone stocks are OVERBOUGHT (wait for pullback):</strong> "
            html += ", ".join([f"<strong>{r['ticker']}</strong> ({r['psar_zone']})" for r in overbought_buys[:10]])
            if len(overbought_buys) > 10:
                html += f" +{len(overbought_buys)-10} more"
            html += "</div>"
        
        # OVERSOLD OPPORTUNITIES - Best entry points
        oversold_in_buy = [r for r in oversold_stocks if r.get('psar_zone') in ['STRONG_BUY', 'BUY', 'NEUTRAL']]
        if oversold_in_buy:
            oversold_in_buy.sort(key=lambda x: (-1 if x.get('psar_zone') == 'STRONG_BUY' else 0 if x.get('psar_zone') == 'BUY' else 1, -x.get('psar_momentum', 0)))
            html += "<div class='alert-box' style='background-color:#d1ecf1; border-left:4px solid #17a2b8;'>"
            html += f"<strong>❄️ {len(oversold_in_buy)} stocks OVERSOLD (ideal entry points):</strong> "
            html += ", ".join([f"<strong>{r['ticker']}</strong> ({r['psar_zone']})" for r in oversold_in_buy[:10]])
            if len(oversold_in_buy) > 10:
                html += f" +{len(oversold_in_buy)-10} more"
            html += "</div>"
        
        # WATCHLIST
        watchlist = [r for r in self.all_results if r.get('is_watchlist', False)]
        if watchlist:
            html += "<div class='section-yellow'>⭐ PERSONAL WATCHLIST</div>"
            html += self._build_zone_table(watchlist, 'yellow')
        
        # TOP TIER STRONG BUY - Show ALL
        if top_tier:
            html += f"<div class='section-toptier'>🟢🟢🟢 STRONG BUY - TOP TIER ({len(top_tier)} stocks)</div>"
            html += "<p style='font-size:10px;color:#666;'>PSAR >+5% + Momentum≥7 + IR≥40 + Above 50MA</p>"
            html += self._build_zone_table(top_tier, 'toptier')
        
        # STRONG BUY (Confirmed) - Show ALL
        if strong_buy:
            html += f"<div class='section-strongbuy'>🟢🟢 BUY - CONFIRMED ({len(strong_buy)} stocks)</div>"
            html += "<p style='font-size:10px;color:#666;'>PSAR >+5% but missing some Top Tier criteria</p>"
            html += self._build_zone_table(strong_buy, 'strongbuy')
        
        # BUY - Show ALL
        if buy:
            html += f"<div class='section-buy'>🟢 BUY ({len(buy)} stocks)</div>"
            html += self._build_zone_table(buy, 'buy')
        
        # NEUTRAL/WEAK/SELL - Just show counts in summary, no tables
        # (Users can see these in -mystocks mode for their portfolio)
        
        # DIVIDEND STOCKS
        div_stocks = [r for r in self.all_results 
                      if 1.5 <= r.get('dividend_yield', 0) <= 15.0 
                      and not r.get('is_watchlist', False)
                      and not r.get('is_reit', False)
                      and not r.get('is_lp', False)]
        
        zone_priority = {'STRONG_BUY': 0, 'BUY': 1, 'NEUTRAL': 2, 'WEAK': 3, 'SELL': 4}
        div_stocks.sort(key=lambda x: (zone_priority.get(x.get('psar_zone', 'SELL'), 5), -x.get('dividend_yield', 0)))
        
        if div_stocks:
            div_in_buy = len([d for d in div_stocks if d.get('psar_zone') in ['STRONG_BUY', 'BUY']])
            html += f"<div class='section-purple'>💰 DIVIDEND STOCKS ({len(div_stocks)} total, {div_in_buy} in BUY zones, showing top 30)</div>"
            html += """<table><tr>
                <th class='th-purple'>Ticker</th><th class='th-purple'>Company</th><th class='th-purple'>Zone</th>
                <th class='th-purple'>Mom</th><th class='th-purple'>Price</th><th class='th-purple'>PSAR %</th>
                <th class='th-purple'>Yield</th><th class='th-purple'>IR</th></tr>"""
            
            for r in div_stocks[:30]:
                zone = r.get('psar_zone', 'UNKNOWN')
                is_ibd = 'IBD' in r.get('source', '')
                ticker_display = f"⭐{r['ticker']}" if is_ibd else r['ticker']
                html += f"""<tr>
                    <td><strong>{ticker_display}</strong></td><td>{r.get('company', r['ticker'])[:18]}</td>
                    <td style='color:{self.get_zone_color(zone)};'>{self.get_zone_emoji(zone)}</td>
                    <td>{self.get_momentum_display(r.get('psar_momentum', 5))}</td>
                    <td>${r['price']:.2f}</td><td style='color:{self.get_zone_color(zone)};'>{r['psar_distance']:+.1f}%</td>
                    <td><strong>{r['dividend_yield']:.1f}%</strong></td><td>{r['signal_weight']}</td></tr>"""
            html += "</table>"
        
        # FOOTER
        html += """
        <hr>
        <p style='font-size: 10px; color: #7f8c8d;'>
        <strong>IR (Indicator Rating):</strong> MACD(30) + Ultimate(30) + Williams %R(20) + Bollinger(10) + Coppock(10) = Max 100<br>
        <strong>Momentum (1-10):</strong> Trajectory since signal start. 8-10=Strong, 4-7=Neutral, 1-3=Weak<br>
        <strong>⭐ = IBD Stock</strong> (Investor's Business Daily growth stock list)<br>
        Generated by PSAR Zone Scanner
        </p>
        </body></html>
        """
        
        return html
    
    def get_atr_display(self, result):
        """Get ATR status display with % from EMA8"""
        atr_status = result.get('atr_status', 'NORMAL')
        atr_pct = result.get('atr_pct', 0)
        if atr_status == 'OVERBOUGHT':
            return f'🔥{atr_pct:+.0f}%'
        elif atr_status == 'OVERSOLD':
            return f'❄️{atr_pct:+.0f}%'
        else:
            return f'{atr_pct:+.0f}%'
    
    def get_prsi_display(self, result):
        """Get PRSI display"""
        prsi_bullish = result.get('prsi_bullish', True)
        return '↗️' if prsi_bullish else '↘️'
    
    def _build_zone_table(self, stocks, zone_class):
        th_class = f'th-{zone_class}'
        
        html = f"""<table><tr>
            <th class='{th_class}'>Ticker</th><th class='{th_class}'>Company</th><th class='{th_class}'>Zone</th>
            <th class='{th_class}'>Mom</th><th class='{th_class}'>Price</th><th class='{th_class}'>PSAR %</th>
            <th class='{th_class}'>ATR</th><th class='{th_class}'>PRSI</th>
            <th class='{th_class}'>OBV</th><th class='{th_class}'>IR</th><th class='{th_class}'>50MA</th>
            <th class='{th_class}'>Indicators</th></tr>"""
        
        for r in stocks:
            zone = r.get('psar_zone', 'UNKNOWN')
            zone_color = self.get_zone_color(zone)
            momentum = r.get('psar_momentum', 5)
            
            above_ma = r.get('above_ma50', False)
            ma_html = "<span style='color:#27ae60;'>↑</span>" if above_ma else "<span style='color:#e74c3c;'>↓</span>"
            
            obv_html = self.get_obv_display(r.get('obv_status', 'NEUTRAL'))
            atr_html = self.get_atr_display(r)
            prsi_html = self.get_prsi_display(r)
            
            is_ibd = 'IBD' in r.get('source', '')
            ticker_display = f"⭐{r['ticker']}" if is_ibd else r['ticker']
            
            html += f"""<tr>
                <td><strong>{ticker_display}</strong></td><td>{r.get('company', r['ticker'])[:16]}</td>
                <td style='color:{zone_color};'>{self.get_zone_emoji(zone)}</td>
                <td>{self.get_momentum_display(momentum)}</td>
                <td>${r['price']:.2f}</td>
                <td style='color:{zone_color}; font-weight:bold;'>{r['psar_distance']:+.1f}%</td>
                <td>{atr_html}</td>
                <td>{prsi_html}</td>
                <td>{obv_html}</td>
                <td>{r['signal_weight']}</td><td>{ma_html}</td>
                <td style='font-size:10px;'>{self.get_indicator_symbols(r)}</td></tr>"""
        
        html += "</table>"
        return html
    
    def send_email(self, additional_email=None):
        sender_email = os.getenv("GMAIL_EMAIL")
        sender_password = os.getenv("GMAIL_PASSWORD")
        recipient_email = os.getenv("RECIPIENT_EMAIL")
        
        if not all([sender_email, sender_password, recipient_email]):
            print("✗ Missing email credentials")
            return
        
        # Count tiers for subject
        all_strong = [r for r in self.all_results if r.get('psar_zone') == 'STRONG_BUY']
        top_tier = len([r for r in all_strong if 
                    r.get('psar_momentum', 0) >= 7 and 
                    r.get('signal_weight', 0) >= 40 and 
                    r.get('above_ma50', False) and
                    r.get('obv_status', 'NEUTRAL') == 'CONFIRM'])
        strong_buy = len(all_strong) - top_tier
        buy = len([r for r in self.all_results if r.get('psar_zone') == 'BUY'])
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"📈 Market: {top_tier} Top Tier, {strong_buy} Strong, {buy} Buy - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        msg['From'] = sender_email
        
        # Build recipient list
        recipients = [recipient_email]
        if additional_email:
            recipients.append(additional_email)
        msg['To'] = ", ".join(recipients)
        
        msg.attach(MIMEText(self.build_email_body(), 'html'))
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
            print(f"\n✓ Email sent to: {', '.join(recipients)}")
            print(f"  Top Tier: {top_tier}, Strong Buy: {strong_buy}, Buy: {buy}")
        except Exception as e:
            print(f"\n✗ Failed to send email: {e}")
