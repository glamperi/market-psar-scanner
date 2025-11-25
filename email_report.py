import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# File to track exits over 7 days
EXIT_HISTORY_FILE = 'exit_history.json'

class EmailReport:
    def __init__(self, scan_results):
        self.scan_results = scan_results
        self.all_results = scan_results['all_results']
        self.watchlist_results = scan_results['watchlist_results']
        self.data_warnings = scan_results.get('data_warnings', [])
        
        # Load and update exit history
        self.exit_history = self.load_exit_history()
        self.recent_exits = self.update_exit_history()
        
    def load_exit_history(self):
        """Load exit history from JSON file"""
        if os.path.exists(EXIT_HISTORY_FILE):
            try:
                with open(EXIT_HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_exit_history(self):
        """Save exit history to JSON file"""
        try:
            with open(EXIT_HISTORY_FILE, 'w') as f:
                json.dump(self.exit_history, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save exit history: {e}")
    
    def update_exit_history(self):
        """
        Track stocks that changed from BUY to SELL.
        Returns list of exits in the last 7 days.
        """
        now = datetime.now()
        cutoff = now - timedelta(days=7)
        
        # Get current PSAR buy tickers
        current_buys = set(r['ticker'] for r in self.all_results if r['psar_bullish'])
        current_sells = {r['ticker']: r for r in self.all_results if not r['psar_bullish']}
        
        # Check previous buys that are now sells (new exits)
        previous_buys = set(self.exit_history.get('previous_buys', []))
        
        new_exits = []
        for ticker in previous_buys:
            if ticker in current_sells and ticker not in current_buys:
                # This stock was a buy before, now it's a sell = EXIT
                result = current_sells[ticker]
                exit_entry = {
                    'ticker': ticker,
                    'exit_date': now.isoformat(),
                    'exit_price': result['price'],
                    'company': result.get('company', ticker),
                    'psar_distance': result.get('psar_distance', 0),
                    'day_change': result.get('day_change', 0),
                    'indicators': {
                        'macd': result.get('has_macd', False),
                        'bb': result.get('has_bb', False),
                        'willr': result.get('has_willr', False),
                        'coppock': result.get('has_coppock', False),
                        'ultimate': result.get('has_ultimate', False)
                    }
                }
                new_exits.append(exit_entry)
        
        # Add new exits to history
        exits_list = self.exit_history.get('exits', [])
        exits_list.extend(new_exits)
        
        # Filter to last 7 days only
        recent_exits = []
        for exit_entry in exits_list:
            try:
                exit_date = datetime.fromisoformat(exit_entry['exit_date'])
                if exit_date >= cutoff:
                    recent_exits.append(exit_entry)
            except:
                continue
        
        # Update history
        self.exit_history = {
            'previous_buys': list(current_buys),
            'exits': recent_exits,
            'last_updated': now.isoformat()
        }
        
        self.save_exit_history()
        
        # Sort by exit date, most recent first
        recent_exits.sort(key=lambda x: x['exit_date'], reverse=True)
        
        return recent_exits
    
    def get_indicator_symbols(self, result):
        """Get checkmark/X symbols for indicators with colors"""
        def sym(val):
            return "<span style='color:#27ae60;'>✓</span>" if val else "<span style='color:#e74c3c;'>✗</span>"
        
        macd_sym = sym(result.get('has_macd', False))
        bb_sym = sym(result.get('has_bb', False))
        willr_sym = sym(result.get('has_willr', False))
        copp_sym = sym(result.get('has_coppock', False))
        ult_sym = sym(result.get('has_ultimate', False))
        
        return f"MACD {macd_sym} | BB {bb_sym} | Will {willr_sym} | Copp {copp_sym} | Ult {ult_sym}"
    
    def get_exit_indicator_symbols(self, indicators_dict):
        """Get indicator symbols from exit history format"""
        def sym(val):
            return "<span style='color:#27ae60;'>✓</span>" if val else "<span style='color:#e74c3c;'>✗</span>"
        
        macd_sym = sym(indicators_dict.get('macd', False))
        bb_sym = sym(indicators_dict.get('bb', False))
        willr_sym = sym(indicators_dict.get('willr', False))
        copp_sym = sym(indicators_dict.get('coppock', False))
        ult_sym = sym(indicators_dict.get('ultimate', False))
        
        return f"MACD {macd_sym} | BB {bb_sym} | Will {willr_sym} | Copp {copp_sym} | Ult {ult_sym}"
    
    def build_email_body(self):
        """Build email in the EXACT order specified with proper colors"""
        
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; font-size: 12px; }
                table { border-collapse: collapse; width: 100%; margin: 15px 0; }
                th { padding: 8px; text-align: left; font-size: 11px; }
                td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }
                tr:hover { background-color: #f5f5f5; }
                
                /* Color coded section headers */
                .section-green { background-color: #27ae60; color: white; padding: 12px; margin: 25px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-red { background-color: #c0392b; color: white; padding: 12px; margin: 25px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-yellow { background-color: #f39c12; color: white; padding: 12px; margin: 25px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-blue { background-color: #2980b9; color: white; padding: 12px; margin: 25px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-purple { background-color: #8e44ad; color: white; padding: 12px; margin: 25px 0 10px 0; font-size: 14px; font-weight: bold; }
                .section-gray { background-color: #7f8c8d; color: white; padding: 12px; margin: 25px 0 10px 0; font-size: 14px; font-weight: bold; }
                
                /* Table header colors */
                .th-green { background-color: #27ae60; color: white; }
                .th-red { background-color: #c0392b; color: white; }
                .th-yellow { background-color: #e67e22; color: white; }
                .th-blue { background-color: #2980b9; color: white; }
                .th-purple { background-color: #8e44ad; color: white; }
                .th-gray { background-color: #7f8c8d; color: white; }
                
                /* Signal badges */
                .buy { color: #27ae60; font-weight: bold; }
                .sell { color: #c0392b; font-weight: bold; }
                
                /* Warning/alert boxes */
                .warning { background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }
                .exit-alert { background-color: #f8d7da; border-left: 4px solid #c0392b; padding: 10px; margin: 10px 0; }
                
                .guide { background-color: #ecf0f1; padding: 10px; margin: 10px 0; border-radius: 4px; }
            </style>
        </head>
        <body>
        """
        
        html += f"<h2>📊 Market Scanner Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>"
        
        # DATA QUALITY WARNINGS (if any)
        if self.data_warnings:
            html += """
            <div class='warning'>
                <strong>⚠️ DATA QUALITY WARNINGS:</strong><br>
            """
            for warning in self.data_warnings:
                html += f"• {warning}<br>"
            html += "</div>"
        
        # ==========================================
        # SECTION 1: TECHNICAL INDICATORS GUIDE (Gray)
        # ==========================================
        html += "<div class='section-gray'>📖 TECHNICAL INDICATORS COMPARISON GUIDE</div>"
        html += """
        <div class='guide'>
        <table>
            <tr>
                <th class='th-gray'>Indicator</th>
                <th class='th-gray'>Entry Timing</th>
                <th class='th-gray'>Accuracy</th>
                <th class='th-gray'>Best Use Case</th>
            </tr>
            <tr><td><strong>RSI</strong></td><td>Early</td><td>Medium</td><td>Oversold bounces</td></tr>
            <tr><td><strong>Stochastic</strong></td><td>Very Early</td><td>Low</td><td>Day trading</td></tr>
            <tr><td><strong>MACD ⭐</strong></td><td>Medium</td><td>High</td><td>Trend reversals</td></tr>
            <tr><td><strong>PSAR</strong></td><td>Late</td><td>Very High</td><td>Confirmed trends</td></tr>
            <tr><td><strong>Bollinger Bands</strong></td><td>Early</td><td>Medium</td><td>Volatility plays</td></tr>
            <tr><td><strong>Williams %R</strong></td><td>Very Early</td><td>Low-Medium</td><td>Short-term reversals</td></tr>
            <tr><td><strong>Coppock Curve</strong></td><td>Very Late</td><td>High</td><td>Major bottoms (long-term)</td></tr>
            <tr><td><strong>Ultimate Oscillator</strong></td><td>Early-Medium</td><td>High</td><td>Multi-timeframe confirm</td></tr>
        </table>
        </div>
        """
        
        # ==========================================
        # SECTION 2: RECENT EXITS - Last 7 Days (RED)
        # ==========================================
        html += "<div class='section-red'>🚨 RECENT EXITS (Last 7 Days - BUY → SELL)</div>"
        
        if self.recent_exits:
            html += f"""
            <div class='exit-alert'>
                <strong>⚠️ {len(self.recent_exits)} stocks exited PSAR Buy signal in the last 7 days!</strong>
            </div>
            """
            html += """
            <table>
                <tr>
                    <th class='th-red'>Ticker</th>
                    <th class='th-red'>Company</th>
                    <th class='th-red'>Exit Date</th>
                    <th class='th-red'>Exit Price</th>
                    <th class='th-red'>PSAR Dist</th>
                    <th class='th-red'>Indicators at Exit</th>
                </tr>
            """
            
            for exit_entry in self.recent_exits:
                try:
                    exit_date = datetime.fromisoformat(exit_entry['exit_date'])
                    date_str = exit_date.strftime('%m/%d %H:%M')
                except:
                    date_str = "Unknown"
                
                indicators_html = self.get_exit_indicator_symbols(exit_entry.get('indicators', {}))
                
                html += f"""
                <tr style='background-color: #fdf2f2;'>
                    <td><strong style='color:#c0392b;'>{exit_entry['ticker']}</strong></td>
                    <td>{exit_entry.get('company', '')[:25]}</td>
                    <td>{date_str}</td>
                    <td>${exit_entry.get('exit_price', 0):.2f}</td>
                    <td>{exit_entry.get('psar_distance', 0):.2f}%</td>
                    <td>{indicators_html}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p style='color:#27ae60;'>✓ No exits in the last 7 days - all previous buys still active!</p>"
        
        # ==========================================
        # SECTION 3: NEW PSAR ENTRIES - All Indices (GREEN)
        # ==========================================
        html += "<div class='section-green'>🟢 NEW PSAR BUY SIGNALS (All Indices)</div>"
        
        psar_buys = [r for r in self.all_results if r['psar_bullish']]
        # Sort by: 1) Grade (A first), 2) Weight (highest), 3) Volume ratio (highest), 4) PSAR distance (lowest/freshest)
        grade_order = {'A': 0, 'B': 1, 'C': 2}
        psar_buys = sorted(psar_buys, key=lambda x: (
            grade_order.get(x.get('entry_grade', 'C'), 2),  # Grade A=0, B=1, C=2
            -x.get('signal_weight', 0),                      # Weight descending
            -x.get('volume_ratio', 0),                       # Volume ratio descending
            x.get('psar_distance', 999)                      # PSAR distance ascending (freshest first)
        ))
        
        # Identify IBD stocks for highlighting
        ibd_psar_buys = [r for r in psar_buys if 'IBD' in r.get('source', '')]
        
        if psar_buys:
            # Show IBD + PSAR combo section first if any exist
            if ibd_psar_buys:
                html += f"""
                <div style='background-color: #fff9e6; border-left: 4px solid #f1c40f; padding: 10px; margin: 10px 0;'>
                    <strong>⭐ IBD + PSAR COMBOS ({len(ibd_psar_buys)} stocks)</strong> - Quality growth stocks with fresh buy signals:
                    <span style='font-size: 13px;'><strong>
                """
                ibd_tickers = [r['ticker'] for r in ibd_psar_buys[:15]]  # Show first 15
                html += ", ".join(ibd_tickers)
                if len(ibd_psar_buys) > 15:
                    html += f" ... +{len(ibd_psar_buys) - 15} more"
                html += "</strong></span></div>"
            
            html += f"<p><strong>Total PSAR Buy Signals: {len(psar_buys)}</strong></p>"
            html += """
            <table>
                <tr>
                    <th class='th-green'>Ticker</th>
                    <th class='th-green'>Company</th>
                    <th class='th-green'>Grade</th>
                    <th class='th-green'>Days</th>
                    <th class='th-green'>Price</th>
                    <th class='th-green'>PSAR %</th>
                    <th class='th-green'>Off High</th>
                    <th class='th-green'>50MA</th>
                    <th class='th-green'>Vol</th>
                    <th class='th-green'>Wt</th>
                    <th class='th-green'>RSI</th>
                    <th class='th-green'>Indicators</th>
                </tr>
            """
            
            for r in psar_buys:
                # Entry grade styling
                grade = r.get('entry_grade', 'C')
                if grade == 'A':
                    grade_html = "<span style='color:#27ae60; font-weight:bold;'>A</span>"
                elif grade == 'B':
                    grade_html = "<span style='color:#f39c12; font-weight:bold;'>B</span>"
                else:
                    grade_html = "<span style='color:#95a5a6;'>C</span>"
                
                # Days since signal
                days = r.get('days_since_signal', 0)
                if days <= 5:
                    days_html = f"<span style='color:#27ae60; font-weight:bold;'>{days}d</span>"
                elif days <= 15:
                    days_html = f"<span style='color:#f39c12;'>{days}d</span>"
                else:
                    days_html = f"<span style='color:#95a5a6;'>{days}d</span>"
                
                # % off 52w high
                off_high = r.get('pct_off_high', 0)
                if off_high <= 10:
                    off_high_html = f"<span style='color:#e74c3c;'>-{off_high:.0f}%</span>"  # Near highs
                elif off_high <= 25:
                    off_high_html = f"<span style='color:#f39c12;'>-{off_high:.0f}%</span>"
                else:
                    off_high_html = f"<span style='color:#27ae60;'>-{off_high:.0f}%</span>"  # Good pullback
                
                # Above/below 50MA
                above_ma = r.get('above_ma50', False)
                ma_html = "<span style='color:#27ae60;'>↑</span>" if above_ma else "<span style='color:#e74c3c;'>↓</span>"
                
                # Volume ratio
                vol_ratio = r.get('volume_ratio', 1.0)
                if vol_ratio >= 1.5:
                    vol_html = f"<span style='color:#27ae60; font-weight:bold;'>{vol_ratio:.1f}x</span>"
                elif vol_ratio >= 1.0:
                    vol_html = f"{vol_ratio:.1f}x"
                else:
                    vol_html = f"<span style='color:#95a5a6;'>{vol_ratio:.1f}x</span>"
                
                # IBD star marker
                is_ibd = 'IBD' in r.get('source', '')
                ticker_display = f"⭐{r['ticker']}" if is_ibd else r['ticker']
                
                # Row highlighting for Grade A
                row_style = "background-color: #e8f5e9;" if grade == 'A' else ""
                
                html += f"""
                <tr style='{row_style}'>
                    <td><strong>{ticker_display}</strong></td>
                    <td>{r['company'][:20]}</td>
                    <td>{grade_html}</td>
                    <td>{days_html}</td>
                    <td>${r['price']:.2f}</td>
                    <td>{r['psar_distance']:.1f}%</td>
                    <td>{off_high_html}</td>
                    <td>{ma_html}</td>
                    <td>{vol_html}</td>
                    <td>{r['signal_weight']}</td>
                    <td>{r['rsi']:.0f}</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                </tr>
                """
            
            html += "</table>"
            html += """
            <p style='font-size: 10px; color: #7f8c8d;'>
            <strong>Grade:</strong> A=Fresh (≤7d) + weight≥50 or RSI<40 | B=≤20 days + weight≥20 | C=Older/weaker<br>
            <strong>Days:</strong> Days since PSAR flipped to buy | <strong>Off High:</strong> % below 52-week high | <strong>50MA:</strong> ↑=Above, ↓=Below | <strong>Vol:</strong> Today vs 20-day avg
            </p>
            """
        else:
            html += "<p>No PSAR buy signals found</p>"
        
        # ==========================================
        # SECTION 4: PERSONAL WATCHLIST (YELLOW/Gold) - NO DIVIDENDS
        # ==========================================
        html += "<div class='section-yellow'>⭐ PERSONAL WATCHLIST (All Indicators Displayed)</div>"
        
        if self.watchlist_results:
            html += """
            <table>
                <tr>
                    <th class='th-yellow'>Ticker</th>
                    <th class='th-yellow'>Company</th>
                    <th class='th-yellow'>Signal</th>
                    <th class='th-yellow'>Price</th>
                    <th class='th-yellow'>Day %</th>
                    <th class='th-yellow'>PSAR Dist</th>
                    <th class='th-yellow'>Weight</th>
                    <th class='th-yellow'>RSI</th>
                    <th class='th-yellow'>All Indicators</th>
                </tr>
            """
            
            for r in self.watchlist_results:
                signal_class = "buy" if r['psar_bullish'] else "sell"
                signal_text = "BUY" if r['psar_bullish'] else "SELL"
                day_color = "#27ae60" if r['day_change'] > 0 else "#c0392b"
                
                # Color code PSAR distance - green for positive (buy), red for negative (sell)
                psar_dist = r['psar_distance']
                if psar_dist >= 0:
                    psar_color = "#27ae60"
                    psar_display = f"+{psar_dist:.2f}%"
                else:
                    psar_color = "#c0392b"
                    psar_display = f"{psar_dist:.2f}%"
                
                html += f"""
                <tr>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['company'][:25]}</td>
                    <td class='{signal_class}'>{signal_text}</td>
                    <td>${r['price']:.2f}</td>
                    <td style='color: {day_color};'>{r['day_change']:+.2f}%</td>
                    <td style='color: {psar_color};'>{psar_display}</td>
                    <td>{r['signal_weight']}</td>
                    <td>{r['rsi']:.1f}</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p>No watchlist data available</p>"
        
        # ==========================================
        # SECTION 5: TOP 50 BUYS (BLUE) - NO DIVIDENDS
        # ==========================================
        html += "<div class='section-blue'>🏆 TOP 50 BUY SIGNALS (Sorted by PSAR Distance & Weight)</div>"
        
        top_buys = [r for r in self.all_results if r['psar_bullish'] and not r.get('is_watchlist', False)]
        # Sort by HIGHEST distance first, then HIGHEST weight as tiebreaker
        top_buys = sorted(top_buys, key=lambda x: (-x.get('psar_distance', 0), -x.get('signal_weight', 0)))[:50]
        
        if top_buys:
            html += """
            <table>
                <tr>
                    <th class='th-blue'>#</th>
                    <th class='th-blue'>Ticker</th>
                    <th class='th-blue'>Company</th>
                    <th class='th-blue'>Source</th>
                    <th class='th-blue'>Price</th>
                    <th class='th-blue'>PSAR Dist</th>
                    <th class='th-blue'>Weight</th>
                    <th class='th-blue'>RSI</th>
                    <th class='th-blue'>Indicators</th>
                    <th class='th-blue'>IBD</th>
                </tr>
            """
            
            for idx, r in enumerate(top_buys, 1):
                ibd_text = f"{r['composite']}/{r['eps']}/{r['rs']}" if r['composite'] != 'N/A' else "-"
                
                html += f"""
                <tr>
                    <td>{idx}</td>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['company'][:25]}</td>
                    <td>{r['source']}</td>
                    <td>${r['price']:.2f}</td>
                    <td>{r['psar_distance']:.2f}%</td>
                    <td><strong>{r['signal_weight']}</strong></td>
                    <td>{r['rsi']:.1f}</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                    <td>{ibd_text}</td>
                </tr>
                """
            
            html += "</table>"
            html += """
            <p style='font-size: 10px; color: #7f8c8d;'>
            <strong>Weight:</strong> Sum of indicator signals: MACD (+30), Ultimate Osc (+30), Williams %R (+20), Bollinger Band (+10), Coppock (+10). Max=100<br>
            <strong>IBD Column:</strong> Composite/EPS/RS ratings (1-99 scale). <em>Composite</em>=Overall IBD rating, <em>EPS</em>=Earnings strength, <em>RS</em>=Relative Strength vs market. Higher is better, 80+ is strong.
            </p>
            """
        else:
            html += "<p>No buy signals found</p>"
        
        # ==========================================
        # SECTION 6: DIVIDEND STOCKS (PURPLE) - PSAR BUY first, then high weight
        # Excludes REITs and Limited Partnerships
        # ==========================================
        html += "<div class='section-purple'>💰 DIVIDEND STOCKS (Yield 1.5-15%, No REITs/LPs, Max 50)</div>"
        
        # Get dividend stocks with yield between 1.5% and 15% (filter out bad data)
        # Exclude REITs and Limited Partnerships
        div_stocks = [r for r in self.all_results 
                      if 1.5 <= r['dividend_yield'] <= 15.0 
                      and not r.get('is_watchlist', False)
                      and not r.get('is_reit', False)
                      and not r.get('is_lp', False)]
        
        # PSAR buys first, sorted by PSAR distance (freshest signals first)
        psar_div_buys = [r for r in div_stocks if r['psar_bullish']]
        psar_div_buys = sorted(psar_div_buys, key=lambda x: (x.get('psar_distance', 999), -x.get('signal_weight', 0)))
        
        # Non-PSAR with high weight stocks next (weight >= 40), sorted by weight then distance
        high_weight_div = [r for r in div_stocks if not r['psar_bullish'] and r['signal_weight'] >= 40]
        high_weight_div = sorted(high_weight_div, key=lambda x: (-x['signal_weight'], x.get('psar_distance', 999)))
        
        # Combine up to 50 total
        dividend_list = (psar_div_buys + high_weight_div)[:50]
        
        if dividend_list:
            psar_count = len(psar_div_buys)
            html += f"<p><strong>Showing {len(dividend_list)} dividend stocks ({psar_count} with PSAR BUY signal) - REITs/LPs excluded</strong></p>"
            html += """
            <table>
                <tr>
                    <th class='th-purple'>Ticker</th>
                    <th class='th-purple'>Company</th>
                    <th class='th-purple'>PSAR Signal</th>
                    <th class='th-purple'>Price</th>
                    <th class='th-purple'>PSAR Dist</th>
                    <th class='th-purple'>Weight</th>
                    <th class='th-purple'>Div Yield</th>
                    <th class='th-purple'>Indicators</th>
                </tr>
            """
            
            for r in dividend_list:
                if r['psar_bullish']:
                    signal_html = "<span style='color:#27ae60; font-weight:bold;'>🟢 BUY</span>"
                    row_style = "background-color: #e8f5e9;"
                else:
                    signal_html = "<span style='color:#7f8c8d;'>⚪ SELL</span>"
                    row_style = ""
                
                html += f"""
                <tr style='{row_style}'>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['company'][:25]}</td>
                    <td>{signal_html}</td>
                    <td>${r['price']:.2f}</td>
                    <td>{r['psar_distance']:.2f}%</td>
                    <td>{r['signal_weight']}</td>
                    <td>{r['dividend_yield']:.2f}%</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p>No dividend stocks meeting criteria found</p>"
        
        html += """
        <hr>
        <p style='font-size: 10px; color: #7f8c8d;'>
        Generated by Market PSAR Scanner | Data: Yahoo Finance | Exit tracking: 7-day rolling window
        </p>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self):
        """Send email report"""
        sender_email = os.getenv("GMAIL_EMAIL")
        sender_password = os.getenv("GMAIL_PASSWORD")
        recipient_email = os.getenv("RECIPIENT_EMAIL")
        
        if not all([sender_email, sender_password, recipient_email]):
            print("✗ Missing email credentials in environment variables")
            print(f"  GMAIL_EMAIL: {'✓' if sender_email else '✗'}")
            print(f"  GMAIL_PASSWORD: {'✓' if sender_password else '✗'}")
            print(f"  RECIPIENT_EMAIL: {'✓' if recipient_email else '✗'}")
            return
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"📊 Market Scanner - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        msg['From'] = sender_email
        msg['To'] = recipient_email
        
        html_body = self.build_email_body()
        msg.attach(MIMEText(html_body, 'html'))
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
            
            print(f"\n✓ Email sent successfully to {recipient_email}")
        except Exception as e:
            print(f"\n✗ Failed to send email: {e}")
