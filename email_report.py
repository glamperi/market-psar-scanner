import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

class EmailReport:
    def __init__(self, scan_results):
        self.scan_results = scan_results
        self.all_results = scan_results['all_results']
        self.watchlist_results = scan_results['watchlist_results']
        
    def get_indicator_symbols(self, result):
        """Get checkmark/X symbols for indicators"""
        macd_sym = "✓" if result['has_macd'] else "✗"
        bb_sym = "✓" if result['has_bb'] else "✗"
        willr_sym = "✓" if result['has_willr'] else "✗"
        copp_sym = "✓" if result['has_coppock'] else "✗"
        ult_sym = "✓" if result['has_ultimate'] else "✗"
        
        return f"MACD {macd_sym}, BB {bb_sym}, Williams {willr_sym}, Coppock {copp_sym}, Ultimate {ult_sym}"
    
    def build_email_body(self):
        """Build email in the EXACT order specified"""
        
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; font-size: 12px; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th { background-color: #2c3e50; color: white; padding: 8px; text-align: left; font-size: 11px; }
                td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }
                tr:hover { background-color: #f5f5f5; }
                .buy { color: green; font-weight: bold; }
                .sell { color: red; font-weight: bold; }
                .section-header { 
                    background-color: #34495e; 
                    color: white; 
                    padding: 10px; 
                    margin: 20px 0 10px 0;
                    font-size: 14px;
                    font-weight: bold;
                }
                .guide { background-color: #ecf0f1; padding: 10px; margin: 10px 0; }
            </style>
        </head>
        <body>
        """
        
        html += f"<h2>📊 Market Scanner Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>"
        
        # ==========================================
        # SECTION 1: TECHNICAL INDICATORS GUIDE
        # ==========================================
        html += """
        <div class='section-header'>📖 TECHNICAL INDICATORS COMPARISON GUIDE</div>
        <div class='guide'>
        <table>
            <tr>
                <th>Indicator</th>
                <th>Entry Timing</th>
                <th>Accuracy</th>
                <th>Best Use Case</th>
            </tr>
            <tr>
                <td><strong>RSI</strong></td>
                <td>Early</td>
                <td>Medium</td>
                <td>Oversold bounces</td>
            </tr>
            <tr>
                <td><strong>Stochastic</strong></td>
                <td>Very Early</td>
                <td>Low</td>
                <td>Day trading</td>
            </tr>
            <tr>
                <td><strong>MACD ⭐</strong></td>
                <td>Medium</td>
                <td>High</td>
                <td>Trend reversals</td>
            </tr>
            <tr>
                <td><strong>PSAR</strong></td>
                <td>Late</td>
                <td>Very High</td>
                <td>Confirmed trends (use this for primary signals)</td>
            </tr>
            <tr>
                <td><strong>Bollinger Bands</strong></td>
                <td>Early</td>
                <td>Medium</td>
                <td>Volatility plays</td>
            </tr>
            <tr>
                <td><strong>Williams %R</strong></td>
                <td>Very Early</td>
                <td>Low-Medium</td>
                <td>Short-term reversals</td>
            </tr>
            <tr>
                <td><strong>Coppock Curve</strong></td>
                <td>Very Late</td>
                <td>High</td>
                <td>Major bottoms (long-term only)</td>
            </tr>
            <tr>
                <td><strong>Ultimate Oscillator</strong></td>
                <td>Early-Medium</td>
                <td>High</td>
                <td>Multi-timeframe confirmation</td>
            </tr>
        </table>
        </div>
        """
        
        # ==========================================
        # SECTION 2: RECENT EXITS (Last 7 Days)
        # ==========================================
        html += "<div class='section-header'>🚨 RECENT EXITS (Last 7 Days - Stocks Changed from BUY → SELL)</div>"
        html += "<p><em>Note: Exit tracking requires historical scan data (not yet implemented)</em></p>"
        
        # TODO: This requires storing previous scan results and comparing
        # For now, show current SELL signals
        recent_sells = [r for r in self.all_results if not r['psar_bullish']]
        recent_sells = sorted(recent_sells, key=lambda x: x.get('signal_weight', 0), reverse=True)[:50]
        
        if recent_sells:
            html += """
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>Day %</th>
                    <th>PSAR Distance</th>
                    <th>Indicators</th>
                </tr>
            """
            
            for r in recent_sells:
                day_color = "green" if r['day_change'] > 0 else "red"
                html += f"""
                <tr>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['company'][:30]}</td>
                    <td>${r['price']:.2f}</td>
                    <td style='color: {day_color};'>{r['day_change']:+.2f}%</td>
                    <td>{r['psar_distance']:.2f}%</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p>No recent exits to report</p>"
        
        # ==========================================
        # SECTION 3: NEW PSAR ENTRIES (All Indices)
        # ==========================================
        html += "<div class='section-header'>🟢 NEW PSAR BUY SIGNALS (All Indices)</div>"
        
        psar_buys = [r for r in self.all_results if r['psar_bullish']]
        psar_buys = sorted(psar_buys, key=lambda x: (x.get('signal_weight', 0), -x.get('psar_distance', 999)), reverse=True)
        
        if psar_buys:
            html += f"<p><strong>Total PSAR Buy Signals: {len(psar_buys)}</strong></p>"
            html += """
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Source</th>
                    <th>Price</th>
                    <th>Day %</th>
                    <th>PSAR Dist</th>
                    <th>Weight</th>
                    <th>RSI</th>
                    <th>Indicators</th>
                    <th>IBD Comp</th>
                </tr>
            """
            
            for r in psar_buys:
                day_color = "green" if r['day_change'] > 0 else "red"
                html += f"""
                <tr>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['company'][:30]}</td>
                    <td>{r['source']}</td>
                    <td>${r['price']:.2f}</td>
                    <td style='color: {day_color};'>{r['day_change']:+.2f}%</td>
                    <td>{r['psar_distance']:.2f}%</td>
                    <td>{r['signal_weight']}</td>
                    <td>{r['rsi']:.1f}</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                    <td>{r['composite']}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p>No PSAR buy signals found</p>"
        
        # ==========================================
        # SECTION 4: PERSONAL WATCHLIST
        # ==========================================
        html += "<div class='section-header'>⭐ PERSONAL WATCHLIST (All Indicators Displayed)</div>"
        
        if self.watchlist_results:
            html += """
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Signal</th>
                    <th>Price</th>
                    <th>Day %</th>
                    <th>PSAR Dist</th>
                    <th>Weight</th>
                    <th>RSI</th>
                    <th>All Indicators</th>
                    <th>Div %</th>
                </tr>
            """
            
            for r in self.watchlist_results:
                signal_class = "buy" if r['psar_bullish'] else "sell"
                signal_text = "BUY" if r['psar_bullish'] else "SELL"
                day_color = "green" if r['day_change'] > 0 else "red"
                div_text = f"{r['dividend_yield']:.2f}%" if r['dividend_yield'] > 0 else "-"
                
                html += f"""
                <tr>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['company'][:30]}</td>
                    <td class='{signal_class}'>{signal_text}</td>
                    <td>${r['price']:.2f}</td>
                    <td style='color: {day_color};'>{r['day_change']:+.2f}%</td>
                    <td>{r['psar_distance']:.2f}%</td>
                    <td>{r['signal_weight']}</td>
                    <td>{r['rsi']:.1f}</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                    <td>{div_text}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p>No watchlist data available</p>"
        
        # ==========================================
        # SECTION 5: TOP 50 BUYS (Sorted by PSAR Distance & Weight)
        # ==========================================
        html += "<div class='section-header'>🏆 TOP 50 BUY SIGNALS (Sorted by PSAR Distance & Weight)</div>"
        
        top_buys = [r for r in self.all_results if r['psar_bullish'] and not r.get('is_watchlist', False)]
        top_buys = sorted(top_buys, key=lambda x: (x.get('signal_weight', 0), -x.get('psar_distance', 999)), reverse=True)[:50]
        
        if top_buys:
            html += """
            <table>
                <tr>
                    <th>#</th>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Source</th>
                    <th>Price</th>
                    <th>PSAR Dist</th>
                    <th>Weight</th>
                    <th>Indicators</th>
                    <th>IBD</th>
                    <th>Div %</th>
                </tr>
            """
            
            for idx, r in enumerate(top_buys, 1):
                div_text = f"{r['dividend_yield']:.2f}%" if r['dividend_yield'] > 0 else "-"
                ibd_text = f"{r['composite']}/{r['eps']}/{r['rs']}" if r['composite'] != 'N/A' else "-"
                
                html += f"""
                <tr>
                    <td>{idx}</td>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['company'][:30]}</td>
                    <td>{r['source']}</td>
                    <td>${r['price']:.2f}</td>
                    <td>{r['psar_distance']:.2f}%</td>
                    <td>{r['signal_weight']}</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                    <td>{ibd_text}</td>
                    <td>{div_text}</td>
                </tr>
                """
            
            html += "</table>"
        
        # ==========================================
        # SECTION 6: DIVIDEND STOCKS (Up to 30)
        # ==========================================
        html += "<div class='section-header'>💰 DIVIDEND STOCKS (PSAR Buys + High Weight, Max 30)</div>"
        
        # Get dividend stocks with PSAR buy OR high weight
        div_stocks = [r for r in self.all_results if r['dividend_yield'] > 0 and not r.get('is_watchlist', False)]
        
        # PSAR buys first
        psar_div_buys = [r for r in div_stocks if r['psar_bullish']]
        psar_div_buys = sorted(psar_div_buys, key=lambda x: x['dividend_yield'], reverse=True)
        
        # High weight stocks next
        high_weight_div = [r for r in div_stocks if not r['psar_bullish'] and r['signal_weight'] >= 50]
        high_weight_div = sorted(high_weight_div, key=lambda x: (x['signal_weight'], x['dividend_yield']), reverse=True)
        
        # Combine up to 30 total
        dividend_list = (psar_div_buys + high_weight_div)[:30]
        
        if dividend_list:
            html += f"<p><strong>Showing {len(dividend_list)} dividend stocks</strong></p>"
            html += """
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Signal</th>
                    <th>Div Yield</th>
                    <th>Price</th>
                    <th>Weight</th>
                    <th>PSAR Dist</th>
                    <th>Indicators</th>
                </tr>
            """
            
            for r in dividend_list:
                signal_class = "buy" if r['psar_bullish'] else "sell"
                signal_text = "BUY" if r['psar_bullish'] else "SELL"
                
                html += f"""
                <tr>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['company'][:30]}</td>
                    <td class='{signal_class}'>{signal_text}</td>
                    <td><strong>{r['dividend_yield']:.2f}%</strong></td>
                    <td>${r['price']:.2f}</td>
                    <td>{r['signal_weight']}</td>
                    <td>{r['psar_distance']:.2f}%</td>
                    <td>{self.get_indicator_symbols(r)}</td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p>No dividend stocks found</p>"
        
        html += """
        <hr>
        <p style='font-size: 10px; color: #7f8c8d;'>
        Generated by Market PSAR Scanner | Data from Yahoo Finance
        </p>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self):
        """Send email report"""
        sender_email = os.getenv("GMAIL_USER")
        sender_password = os.getenv("GMAIL_APP_PASSWORD")
        recipient_email = os.getenv("RECIPIENT_EMAIL")
        
        if not all([sender_email, sender_password, recipient_email]):
            print("✗ Missing email credentials in environment variables")
            return
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Market Scanner Report - {datetime.now().strftime('%Y-%m-%d')}"
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
