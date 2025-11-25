import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import os

class EmailReport:
    def __init__(self, results):
        self.results = results
        
    def generate_html_report(self):
        """Generate HTML email report"""
        
        watchlist_results = self.results['watchlist_results']
        broad_market_results = self.results['broad_market_results']
        all_results = self.results['all_results']
        
        # Separate into categories
        psar_exits = [r for r in all_results if not r['psar_bullish']]
        psar_signals = [r for r in all_results if r['psar_bullish'] and r['signal_weight'] > 0]
        early_signals = [r for r in all_results if r['psar_bullish'] and r['signal_weight'] == 0]
        
        # Sort
        psar_exits.sort(key=lambda x: x['psar_distance'], reverse=True)
        psar_signals.sort(key=lambda x: x['signal_weight'], reverse=True)
        early_signals.sort(key=lambda x: x['psar_distance'])
        
        # Get dividends (top 50, yield > 1.5%)
        dividend_stocks = [r for r in all_results if r['psar_bullish'] and r['dividend_yield'] > 1.5]
        dividend_stocks.sort(key=lambda x: x['dividend_yield'], reverse=True)
        dividend_stocks = dividend_stocks[:50]
        
        # Limit tables (except exits)
        psar_signals = psar_signals[:50]
        early_signals = early_signals[:50]
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th {{ background-color: #3498db; color: white; padding: 12px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .summary {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .watchlist {{ background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; }}
                .exit {{ color: #e74c3c; font-weight: bold; }}
                .buy {{ color: #27ae60; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>📊 Market PSAR Scanner Report</h1>
            <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="summary">
                <h3>📈 Summary</h3>
                <p><strong>Total Stocks Scanned:</strong> {len(all_results)}</p>
                <p><strong>PSAR Exit Signals:</strong> {len(psar_exits)}</p>
                <p><strong>PSAR Buy Signals (with confirmations):</strong> {len(psar_signals)}</p>
                <p><strong>Early PSAR Signals (0 weight):</strong> {len(early_signals)}</p>
                <p><strong>High Dividend Plays:</strong> {len(dividend_stocks)}</p>
            </div>
        """
        
        # Watchlist Status
        if watchlist_results:
            html += """
            <h2 class="watchlist">🎯 Your Watchlist Status</h2>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>PSAR Status</th>
                    <th>Distance</th>
                    <th>Signal Weight</th>
                    <th>Dividend %</th>
                </tr>
            """
            
            for stock in watchlist_results:
                status = "🟢 BUY" if stock['psar_bullish'] else "🔴 SELL"
                status_class = "buy" if stock['psar_bullish'] else "exit"
                
                html += f"""
                <tr>
                    <td><strong>{stock['ticker']}</strong></td>
                    <td>{stock['company']}</td>
                    <td>${stock['price']:.2f}</td>
                    <td class="{status_class}">{status}</td>
                    <td>{stock['psar_distance']:.2f}%</td>
                    <td>{stock['signal_weight']}</td>
                    <td>{stock['dividend_yield']:.2f}%</td>
                </tr>
                """
            
            html += "</table>"
        
        # PSAR Exits
        if psar_exits:
            html += f"""
            <h2>🔴 PSAR Exit Signals ({len(psar_exits)})</h2>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>Distance</th>
                    <th>Source</th>
                    <th>Comp</th>
                    <th>RS</th>
                </tr>
            """
            
            for stock in psar_exits:
                html += f"""
                <tr>
                    <td><strong>{stock['ticker']}</strong></td>
                    <td>{stock['company']}</td>
                    <td>${stock['price']:.2f}</td>
                    <td class="exit">{stock['psar_distance']:.2f}%</td>
                    <td>{stock['source']}</td>
                    <td>{stock['comp_rating']}</td>
                    <td>{stock['rs_rating']}</td>
                </tr>
                """
            
            html += "</table>"
        
        # PSAR Buy Signals
        if psar_signals:
            html += f"""
            <h2>🟢 PSAR Buy Signals - Top 50 (Weight > 0)</h2>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>Distance</th>
                    <th>Weight</th>
                    <th>RSI</th>
                    <th>Source</th>
                    <th>Comp</th>
                    <th>RS</th>
                </tr>
            """
            
            for stock in psar_signals:
                html += f"""
                <tr>
                    <td><strong>{stock['ticker']}</strong></td>
                    <td>{stock['company']}</td>
                    <td>${stock['price']:.2f}</td>
                    <td>{stock['psar_distance']:.2f}%</td>
                    <td><strong>{stock['signal_weight']}</strong></td>
                    <td>{stock['rsi']:.1f}</td>
                    <td>{stock['source']}</td>
                    <td>{stock['comp_rating']}</td>
                    <td>{stock['rs_rating']}</td>
                </tr>
                """
            
            html += "</table>"
        
        # Early Signals
        if early_signals:
            html += f"""
            <h2>⚠️ Fresh PSAR Flips - Top 50 (0 Weight)</h2>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>Distance</th>
                    <th>RSI</th>
                    <th>Source</th>
                    <th>Comp</th>
                    <th>RS</th>
                </tr>
            """
            
            for stock in early_signals:
                html += f"""
                <tr>
                    <td><strong>{stock['ticker']}</strong></td>
                    <td>{stock['company']}</td>
                    <td>${stock['price']:.2f}</td>
                    <td>{stock['psar_distance']:.2f}%</td>
                    <td>{stock['rsi']:.1f}</td>
                    <td>{stock['source']}</td>
                    <td>{stock['comp_rating']}</td>
                    <td>{stock['rs_rating']}</td>
                </tr>
                """
            
            html += "</table>"
        
        # Dividend Table
        if dividend_stocks:
            html += f"""
            <h2>💰 High Dividend Plays - Top 50 (Yield > 1.5%)</h2>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Price</th>
                    <th>Dividend %</th>
                    <th>Distance</th>
                    <th>Weight</th>
                    <th>Source</th>
                </tr>
            """
            
            for stock in dividend_stocks:
                html += f"""
                <tr>
                    <td><strong>{stock['ticker']}</strong></td>
                    <td>{stock['company']}</td>
                    <td>${stock['price']:.2f}</td>
                    <td><strong>{stock['dividend_yield']:.2f}%</strong></td>
                    <td>{stock['psar_distance']:.2f}%</td>
                    <td>{stock['signal_weight']}</td>
                    <td>{stock['source']}</td>
                </tr>
                """
            
            html += "</table>"
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def send_email(self, to_email=None):
        """Send the email report"""
        
        # Get credentials from environment
        email_from = os.environ.get('GMAIL_EMAIL')
        email_password = os.environ.get('GMAIL_PASSWORD')
        email_to = to_email or os.environ.get('RECIPIENT_EMAIL')
        
        if not email_from or not email_password or not email_to:
            print("✗ Email credentials not configured!")
            return False
        
        html_content = self.generate_html_report()
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Market PSAR Scanner - {datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = email_from
        msg['To'] = email_to
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(email_from, email_password)
                server.send_message(msg)
            
            print(f"\n✓ Email sent successfully to {email_to}")
            return True
        except Exception as e:
            print(f"\n✗ Failed to send email: {e}")
            return False
