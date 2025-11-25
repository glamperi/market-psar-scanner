import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import config

class EmailReport:
    def __init__(self, results):
        self.results = results
        
    def generate_watchlist_section(self, watchlist_results):
        """Generate YOUR POSITIONS section at top of email"""
        if not watchlist_results:
            return ""
        
        html = """
        <div class="section">
            <h2>🎯 YOUR WATCH LIST STATUS</h2>
            <p>Your priority tickers - always shown first, regardless of signal strength</p>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>Status</th>
                    <th>PSAR Dist %</th>
                    <th>Sig Wt</th>
                    <th>Day Chg %</th>
                    <th>Signals</th>
                    <th>RSI</th>
                    <th>Action</th>
                </tr>
        """
        
        # Sort: PSAR buys first, then by signal weight
        watchlist_results_sorted = sorted(watchlist_results, key=lambda x: (not x['psar_bullish'], -x.get('signal_weight', 0)))
        
        for result in watchlist_results_sorted:
            psar_status = "PSAR BUY ✓" if result['psar_bullish'] else "PSAR SELL ❌"
            status_class = "psar-buy" if result['psar_bullish'] else "psar-sell"
            
            # Build signals list
            signals = []
            if result.get('has_macd'): signals.append('MACD')
            if result.get('has_bb'): signals.append('BB')
            if result.get('has_willr'): signals.append('WillR')
            if result.get('has_coppock'): signals.append('Copp')
            if result.get('has_ultimate'): signals.append('Ult')
            signals_str = ', '.join(signals) if signals else 'None yet'
            
            # Determine action
            if result['psar_bullish']:
                dist = abs(result['psar_distance'])
                sig_wt = result.get('signal_weight', 0)
                
                if sig_wt == 0:
                    action = "🔔 FRESH ENTRY!"
                elif dist < 5:
                    action = "🟢 BUY/HOLD"
                elif dist < 10:
                    action = "🟡 GOOD ENTRY"
                elif dist < 15:
                    action = "🟠 EXTENDED"
                else:
                    action = "🔴 VERY EXTENDED"
            else:
                action = "⚠️ CONSIDER EXIT"
            
            day_chg_class = "positive" if result['day_change'] > 0 else "negative"
            
            html += f"""
                <tr class="{status_class}">
                    <td><strong>{result['ticker']}</strong></td>
                    <td>{result['company'][:30]}</td>
                    <td>${result['price']:.2f}</td>
                    <td>{psar_status}</td>
                    <td>{abs(result['psar_distance']):.2f}%</td>
                    <td>{result.get('signal_weight', 0)}</td>
                    <td class="{day_chg_class}">{result['day_change']:+.2f}%</td>
                    <td style="font-size: 11px;">{signals_str}</td>
                    <td>{result['rsi']:.0f}</td>
                    <td><strong>{action}</strong></td>
                </tr>
            """
        
        html += """
            </table>
            <p class="tip">💡 Tip: Watchlist tickers are scanned first and always shown here. Edit custom_watchlist.txt to add/remove tickers.</p>
        </div>
        """
        
        return html
    
    def generate_dividend_table(self, all_results, limit=50):
        """Generate top 50 dividend plays (PSAR + Early signals)"""
        min_yield = getattr(config, 'MIN_DIVIDEND_YIELD', 1.5)
        
        # Filter: dividend yield > min_yield, either PSAR buy or has early signals
        dividend_stocks = []
        
        for result in all_results:
            div_yield = result.get('dividend_yield', 0)
            if div_yield >= min_yield:
                # Include if PSAR buy OR has early signals
                if result['psar_bullish'] or result.get('signal_weight', 0) > 0:
                    dividend_stocks.append(result)
        
        if not dividend_stocks:
            return ""
        
        # Score and sort: (Div Yield * 50) + (Signal Weight * 0.5)
        for stock in dividend_stocks:
            stock['div_score'] = (stock['dividend_yield'] * 50) + (stock.get('signal_weight', 0) * 0.5)
        
        dividend_stocks.sort(key=lambda x: x['div_score'], reverse=True)
        
        # Limit to top 50
        dividend_stocks = dividend_stocks[:limit]
        
        html = """
        <div class="section">
            <h2>💰 TOP 50 DIVIDEND PLAYS</h2>
            <p>Dividend-paying stocks in PSAR buy or building momentum. Sorted by dividend score.</p>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>Div Yield %</th>
                    <th>Signal Type</th>
                    <th>PSAR Dist %</th>
                    <th>Sig Wt</th>
                    <th>Day Chg %</th>
                    <th>M</th>
                    <th>B</th>
                    <th>W</th>
                    <th>C</th>
                    <th>U</th>
                    <th>RSI</th>
                </tr>
        """
        
        for result in dividend_stocks:
            if result.get('is_watchlist', False):
                continue  # Skip watchlist items (already shown above)
                
            signal_type = "PSAR ✓" if result['psar_bullish'] else "Early 🟡"
            signal_class = "psar-buy" if result['psar_bullish'] else "early-signal"
            
            day_chg_class = "positive" if result['day_change'] > 0 else "negative"
            
            html += f"""
                <tr class="{signal_class}">
                    <td><strong>{result['ticker']}</strong></td>
                    <td>{result['company'][:25]}</td>
                    <td>${result['price']:.2f}</td>
                    <td><strong>{result['dividend_yield']:.2f}%</strong></td>
                    <td>{signal_type}</td>
                    <td>{abs(result['psar_distance']):.2f}%</td>
                    <td>{result.get('signal_weight', 0)}</td>
                    <td class="{day_chg_class}">{result['day_change']:+.2f}%</td>
                    <td>{'✓' if result.get('has_macd') else '-'}</td>
                    <td>{'✓' if result.get('has_bb') else '-'}</td>
                    <td>{'✓' if result.get('has_willr') else '-'}</td>
                    <td>{'✓' if result.get('has_coppock') else '-'}</td>
                    <td>{'✓' if result.get('has_ultimate') else '-'}</td>
                    <td>{result['rsi']:.0f}</td>
                </tr>
            """
        
        html += """
            </table>
            <p class="tip">💡 Tip: Dividend Score = (Yield × 50) + (Signal Weight × 0.5). Balances income with technical strength.</p>
        </div>
        """
        
        return html
    
    def generate_fresh_psar_section(self, all_results):
        """Generate Fresh PSAR Flips section (signal weight 0-10)"""
        
        # Filter: PSAR buy + signal weight 0-10 + not watchlist
        fresh_flips = [r for r in all_results 
                       if r['psar_bullish'] 
                       and r.get('signal_weight', 0) <= 10
                       and not r.get('is_watchlist', False)]
        
        if not fresh_flips:
            return ""
        
        # Sort by distance (freshest first)
        fresh_flips.sort(key=lambda x: abs(x['psar_distance']))
        
        # Limit to top 30
        fresh_flips = fresh_flips[:30]
        
        html = """
        <div class="section">
            <h2>🔔 FRESH PSAR REVERSALS (No Early Signals Yet)</h2>
            <p>These just flipped to PSAR buy without early indicator confirmation. This is the pattern we discussed - PSAR confirms real trend change after early signals already fired at the bottom!</p>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Source</th>
                    <th>Price</th>
                    <th>PSAR Dist %</th>
                    <th>Day Chg %</th>
                    <th>RSI</th>
                    <th>Why No Early Signals?</th>
                </tr>
        """
        
        for result in fresh_flips:
            day_chg_class = "positive" if result['day_change'] > 0 else "negative"
            
            # Explain why no early signals
            rsi = result['rsi']
            if rsi < 30:
                reason = "RSI very low - bottom just forming"
            elif rsi < 40:
                reason = "Early signals fired at bottom weeks ago"
            elif rsi < 50:
                reason = "PSAR confirming early reversal"
            else:
                reason = "Strong momentum - PSAR late to confirm"
            
            html += f"""
                <tr>
                    <td><strong>{result['ticker']}</strong></td>
                    <td>{result['company'][:25]}</td>
                    <td>{result['source']}</td>
                    <td>${result['price']:.2f}</td>
                    <td>{abs(result['psar_distance']):.2f}%</td>
                    <td class="{day_chg_class}">{result['day_change']:+.2f}%</td>
                    <td>{rsi:.0f}</td>
                    <td style="font-size: 11px;">{reason}</td>
                </tr>
            """
        
        html += """
            </table>
            <p class="tip">🎯 Remember: PSAR is a LATE indicator with VERY HIGH accuracy. These flips confirm real trend changes.</p>
        </div>
        """
        
        return html
    
    def generate_psar_table(self, psar_results, limit=50):
        """Generate top 50 PSAR buy signals"""
        
        # Filter: PSAR buy + signal weight > 10 (exclude fresh flips) + not watchlist
        psar_signals = [r for r in psar_results 
                        if r['psar_bullish'] 
                        and r.get('signal_weight', 0) > 10
                        and not r.get('is_watchlist', False)]
        
        # Sort by distance (freshest/closest first)
        psar_signals.sort(key=lambda x: abs(x['psar_distance']))
        
        # Limit to top 50
        psar_signals = psar_signals[:limit]
        
        if not psar_signals:
            return ""
        
        html = """
        <div class="section">
            <h2>🟢 TOP 50 CURRENT BUY SIGNALS (PSAR Confirmed)</h2>
            <p>Stocks in confirmed PSAR buy mode with supporting indicators. Sorted by distance (freshest first).</p>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Source</th>
                    <th>Price</th>
                    <th>Dist %</th>
                    <th>Sig Wt</th>
                    <th>Day Chg %</th>
                    <th>M</th>
                    <th>B</th>
                    <th>W</th>
                    <th>C</th>
                    <th>U</th>
                    <th>RSI</th>
                    <th>Comp</th>
                    <th>RS</th>
                </tr>
        """
        
        for result in psar_signals:
            day_chg_class = "positive" if result['day_change'] > 0 else "negative"
            
            html += f"""
                <tr class="psar-buy">
                    <td><strong>{result['ticker']}</strong></td>
                    <td>{result['company'][:25]}</td>
                    <td>{result['source']}</td>
                    <td>${result['price']:.2f}</td>
                    <td>{abs(result['psar_distance']):.2f}%</td>
                    <td>{result.get('signal_weight', 0)}</td>
                    <td class="{day_chg_class}">{result['day_change']:+.2f}%</td>
                    <td>{'✓' if result.get('has_macd') else '-'}</td>
                    <td>{'✓' if result.get('has_bb') else '-'}</td>
                    <td>{'✓' if result.get('has_willr') else '-'}</td>
                    <td>{'✓' if result.get('has_coppock') else '-'}</td>
                    <td>{'✓' if result.get('has_ultimate') else '-'}</td>
                    <td>{result['rsi']:.0f}</td>
                    <td>{result.get('comp_rating', 'N/A')}</td>
                    <td>{result.get('rs_rating', 'N/A')}</td>
                </tr>
            """
        
        html += """
            </table>
            <p class="tip">💡 M=MACD, B=Bollinger, W=Williams%R, C=Coppock, U=Ultimate Oscillator</p>
        </div>
        """
        
        return html
    
    def generate_early_table(self, early_results, limit=50):
        """Generate top 50 early buy signals"""
        
        # Filter: NOT in PSAR buy yet, but has early signals, not watchlist
        early_signals = [r for r in early_results 
                         if not r['psar_bullish'] 
                         and r.get('signal_weight', 0) > 0
                         and not r.get('is_watchlist', False)]
        
        # Sort by signal weight (strongest first)
        early_signals.sort(key=lambda x: x.get('signal_weight', 0), reverse=True)
        
        # Limit to top 50
        early_signals = early_signals[:limit]
        
        if not early_signals:
            return ""
        
        html = """
        <div class="section">
            <h2>🟡 TOP 50 EARLY BUY SIGNALS (Building Momentum)</h2>
            <p>Stocks showing early buy signals but not yet in PSAR buy mode. Sorted by signal weight.</p>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Source</th>
                    <th>Price</th>
                    <th>Day Chg %</th>
                    <th>Sig Wt</th>
                    <th>M</th>
                    <th>B</th>
                    <th>W</th>
                    <th>C</th>
                    <th>U</th>
                    <th>RSI</th>
                    <th>Comp</th>
                    <th>RS</th>
                </tr>
        """
        
        for result in early_signals:
            day_chg_class = "positive" if result['day_change'] > 0 else "negative"
            
            html += f"""
                <tr class="early-signal">
                    <td><strong>{result['ticker']}</strong></td>
                    <td>{result['company'][:25]}</td>
                    <td>{result['source']}</td>
                    <td>${result['price']:.2f}</td>
                    <td class="{day_chg_class}">{result['day_change']:+.2f}%</td>
                    <td>{result.get('signal_weight', 0)}</td>
                    <td>{'✓' if result.get('has_macd') else '-'}</td>
                    <td>{'✓' if result.get('has_bb') else '-'}</td>
                    <td>{'✓' if result.get('has_willr') else '-'}</td>
                    <td>{'✓' if result.get('has_coppock') else '-'}</td>
                    <td>{'✓' if result.get('has_ultimate') else '-'}</td>
                    <td>{result['rsi']:.0f}</td>
                    <td>{result.get('comp_rating', 'N/A')}</td>
                    <td>{result.get('rs_rating', 'N/A')}</td>
                </tr>
            """
        
        html += """
            </table>
            <p class="tip">💡 These stocks are building momentum. Watch for PSAR flip to confirm entry.</p>
        </div>
        """
        
        return html
    
    def generate_summary_stats(self, results):
        """Generate summary statistics"""
        all_results = results['all_results']
        watchlist_results = results['watchlist_results']
        
        psar_buy = [r for r in all_results if r['psar_bullish']]
        early_signals = [r for r in all_results if not r['psar_bullish'] and r.get('signal_weight', 0) > 0]
        
        html = f"""
        <div class="section">
            <h2>📊 Summary Statistics</h2>
            <table style="width: auto; margin: 0 auto;">
                <tr>
                    <td><strong>Confirmed Buy Signals (PSAR Green)</strong></td>
                    <td style="text-align: right;"><strong>{len(psar_buy)}</strong></td>
                </tr>
                <tr>
                    <td><strong>Early Buy Signals (Building)</strong></td>
                    <td style="text-align: right;"><strong>{len(early_signals)}</strong></td>
                </tr>
                <tr>
                    <td><strong>Your Watchlist Tracked</strong></td>
                    <td style="text-align: right;"><strong>{len(watchlist_results)}</strong></td>
                </tr>
            </table>
        </div>
        """
        
        return html
    
    def get_html_header(self):
        """Generate HTML header with CSS"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                    text-align: center;
                }
                .section {
                    background: white;
                    padding: 25px;
                    margin-bottom: 25px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                    font-size: 13px;
                }
                th {
                    background-color: #667eea;
                    color: white;
                    padding: 12px 8px;
                    text-align: left;
                    font-weight: bold;
                    position: sticky;
                    top: 0;
                }
                td {
                    padding: 10px 8px;
                    border-bottom: 1px solid #ddd;
                }
                tr:hover {
                    background-color: #f5f5f5;
                }
                .psar-buy {
                    background-color: #e8f5e9;
                }
                .psar-sell {
                    background-color: #ffebee;
                }
                .early-signal {
                    background-color: #fff9e6;
                }
                .positive {
                    color: #2e7d32;
                    font-weight: bold;
                }
                .negative {
                    color: #c62828;
                    font-weight: bold;
                }
                .tip {
                    background-color: #e3f2fd;
                    padding: 12px;
                    border-left: 4px solid #2196f3;
                    margin-top: 15px;
                    font-size: 14px;
                }
                h2 {
                    color: #667eea;
                    border-bottom: 2px solid #667eea;
                    padding-bottom: 10px;
                    margin-top: 0;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Market-Wide PSAR Scanner Report</h1>
                <p>Date: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
            </div>
        """
    
    def get_html_footer(self):
        """Generate HTML footer"""
        return """
            <div class="section" style="text-align: center; color: #666; font-size: 12px;">
                <p>Automated report from Market-Wide PSAR Scanner</p>
                <p>Tip: Focus on stocks with multiple ✓ marks for stronger confirmation</p>
            </div>
        </body>
        </html>
        """
    
    def generate_html_report(self):
        """Generate complete HTML email report"""
        
        results = self.results
        watchlist_results = results['watchlist_results']
        all_results = results['all_results']
        
        # Separate PSAR buy vs Early signals
        psar_buy = [r for r in all_results if r['psar_bullish']]
        early_signals = [r for r in all_results if not r['psar_bullish'] and r.get('signal_weight', 0) > 0]
        
        # Build email in order
        html = self.get_html_header()
        
        # 1. YOUR WATCHLIST (always shown first)
        html += self.generate_watchlist_section(watchlist_results)
        
        # 2. DIVIDEND TABLE (top 50)
        html += self.generate_dividend_table(all_results, limit=50)
        
        # 3. FRESH PSAR FLIPS (signal weight 0-10)
        html += self.generate_fresh_psar_section(all_results)
        
        # 4. CURRENT PSAR SIGNALS (top 50)
        html += self.generate_psar_table(psar_buy, limit=50)
        
        # 5. EARLY SIGNALS (top 50)
        html += self.generate_early_table(early_signals, limit=50)
        
        # 6. Summary stats
        html += self.generate_summary_stats(results)
        
        html += self.get_html_footer()
        
        return html
    
    def send_email(self, to_email=None):
        """Send the email report"""
        if not to_email:
            to_email = config.EMAIL_TO
        
        html_content = self.generate_html_report()
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"PSAR Scanner Report - {datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = config.EMAIL_FROM
        msg['To'] = to_email
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        try:
            with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as server:
                server.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
                server.send_message(msg)
            
            print(f"\n✓ Email sent successfully to {to_email}")
            return True
        except Exception as e:
            print(f"\n✗ Failed to send email: {e}")
            return False

if __name__ == "__main__":
    # For testing
    pass
