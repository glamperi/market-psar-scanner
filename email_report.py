import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import EMAIL_CONFIG

class EmailReport:
    def __init__(self, changes, all_buys, all_early):
        self.changes = changes
        self.all_buys = all_buys
        self.all_early = all_early

    def format_ticker(self, ticker, source):
        """Add a star to the ticker if it's from an IBD list"""
        if source and 'IBD' in str(source):
            return f"★ {ticker}"
        return ticker

    def generate_html(self):
        """Generate the HTML content for the email"""
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>📊 Market-Wide PSAR Scanner Report</h2>
            <h3>Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</h3>
            <hr>
        """
        
        # 1. Recent Exits (7-day history)
        if self.changes.get('recent_exits_7day'):
            html += """
            <div style="background-color: #FFE0E0; border: 3px solid #FF0000; padding: 15px; margin: 10px 0;">
                <h2 style="color: red;">⚠️ RECENT EXITS: Stocks That Left PSAR Buy in Last 7 Days ⚠️</h2>
                <p style="color: #8B0000;"><strong>Don't miss these sell signals! Check if you own any of these stocks.</strong></p>
                <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                    <tr style="background-color: #FFB6C1;">
                        <th>Ticker</th><th>Company</th><th>Exited</th><th>Exit Price</th><th>Current Price</th><th>Change Since Exit</th><th>Distance to PSAR</th><th>Day Chg %</th><th>RSI</th>
                    </tr>
            """
            for pos in self.changes['recent_exits_7day']:
                ticker_display = self.format_ticker(pos['Ticker'], pos.get('Source', ''))
                
                days_ago = pos.get('days_ago', 0)
                hours_ago = pos.get('hours_ago', 0)
                time_str = "Just now"
                if days_ago == 1: time_str = "Yesterday"
                elif days_ago > 1: time_str = f"{days_ago} days ago"
                elif hours_ago > 0: time_str = f"{hours_ago}h ago"
                
                exit_price = pos.get('exit_price', pos['Price'])
                change_since = ((pos['Price'] - exit_price) / exit_price * 100) if exit_price else 0
                
                html += f"""
                <tr>
                    <td><strong>{ticker_display}</strong></td>
                    <td>{pos.get('Company', 'N/A')[:25]}</td>
                    <td><strong style="color: #8B0000;">{time_str}</strong></td>
                    <td>${exit_price:.2f}</td>
                    <td>${pos['Price']:.2f}</td>
                    <td style="color: {'green' if change_since > 0 else 'red'};">{change_since:+.2f}%</td>
                    <td style="color: red;">{pos.get('Distance %', 0):.2f}%</td>
                    <td style="color: {'green' if pos.get('Day Change %', 0) > 0 else 'red'};">{pos.get('Day Change %', 0):+.2f}%</td>
                    <td>{pos.get('RSI', 'N/A')}</td>
                </tr>
                """
            html += "</table></div><hr>"

        # 2. New Exits (Immediate)
        if self.changes.get('new_exits'):
            html += """
            <div style="background-color: #FFE0E0; border: 3px solid #FF0000; padding: 15px; margin: 10px 0;">
                <h2 style="color: red;">⚠️ WARNING: The Following Went from PSAR Buy to Sell Recently! ⚠️</h2>
                <table border="1" cellpadding="5" style="border-collapse: collapse;">
                    <tr style="background-color: #FFB6C1;">
                        <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>Distance %</th><th>Day Chg %</th>
                    </tr>
            """
            for pos in self.changes['new_exits']:
                ticker_display = self.format_ticker(pos['Ticker'], pos.get('Source', ''))
                html += f"""
                <tr>
                    <td><strong>{ticker_display}</strong></td>
                    <td>{pos.get('Company', 'N/A')[:30]}</td>
                    <td><small>{pos.get('Source', 'N/A')[:20]}</small></td>
                    <td>${pos['Price']}</td>
                    <td>{pos.get('Distance %', 0)}%</td>
                    <td style="color: {'green' if pos.get('Day Change %', 0) > 0 else 'red'};">{pos.get('Day Change %', 0):+.2f}%</td>
                </tr>
                """
            html += "</table></div><hr>"

        # 3. New Entries
        if self.changes.get('new_entries'):
            html += """
            <h2>🚨 NEW POSITION CHANGES</h2>
            <h3 style="color: green;">🟢 NEW BUY SIGNALS (Recently Entered PSAR Buy)</h3>
            <table border="1" cellpadding="5" style="border-collapse: collapse;">
                <tr style="background-color: #90EE90;">
                    <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>Dist %</th><th>Day %</th><th>Wt</th><th>MACD</th><th>BB</th><th>WillR</th><th>Cop</th><th>Ult</th><th>RSI</th>
                </tr>
            """
            sorted_entries = sorted(self.changes['new_entries'], key=lambda x: x.get('signal_weight', 0), reverse=True)
            for pos in sorted_entries:
                ticker_display = self.format_ticker(pos['Ticker'], pos.get('Source', ''))
                html += f"""
                <tr>
                    <td><strong>{ticker_display}</strong></td>
                    <td>{pos.get('Company', 'N/A')[:25]}</td>
                    <td><small>{pos.get('Source', 'N/A')[:15]}</small></td>
                    <td>${pos['Price']}</td>
                    <td>{pos.get('Distance %', 0)}%</td>
                    <td style="color: {'green' if pos.get('Day Change %', 0) > 0 else 'red'};">{pos.get('Day Change %', 0):+.2f}%</td>
                    <td><strong>{pos.get('signal_weight', 0)}</strong></td>
                    <td>{'✓' if pos.get('MACD_Buy') else ''}</td>
                    <td>{'✓' if pos.get('BB_Buy') else ''}</td>
                    <td>{'✓' if pos.get('WillR_Buy') else ''}</td>
                    <td>{'✓' if pos.get('Coppock_Buy') else ''}</td>
                    <td>{'✓' if pos.get('Ultimate_Buy') else ''}</td>
                    <td>{pos.get('RSI', 'N/A')}</td>
                </tr>
                """
            html += "</table><br><hr>"

        # 4. Summary Stats
        html += f"""
        <h2>📈 Summary Statistics</h2>
        <table border="1" cellpadding="8" style="border-collapse: collapse;">
            <tr><td style="background-color: #90EE90;"><strong>🟢 Confirmed Buy Signals</strong></td><td><strong>{len(self.all_buys)}</strong></td></tr>
            <tr><td style="background-color: #FFFF99;"><strong>🟡 Early Buy Signals</strong></td><td><strong>{len(self.all_early)}</strong></td></tr>
            <tr><td><strong>🚨 New Entries</strong></td><td><strong>{len(self.changes.get('new_entries', []))}</strong></td></tr>
            <tr><td><strong>⚠️ New Exits</strong></td><td><strong>{len(self.changes.get('new_exits', []))}</strong></td></tr>
        </table><br>
        """

        # 5. Top 50 Current Buys
        if self.all_buys:
            top_buys = sorted(self.all_buys, key=lambda x: x.get('Distance %', 0), reverse=True)[:50]
            html += """
            <h3>🟢 CURRENT BUY SIGNALS (Top 50 by Distance)</h3>
            <table border="1" cellpadding="5" style="border-collapse: collapse;">
                <tr style="background-color: #E0FFE0;">
                    <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>Dist %</th><th>Day %</th><th>MACD</th><th>BB</th><th>Cop</th><th>Ult</th><th>RSI</th>
                </tr>
            """
            for pos in top_buys:
                ticker_display = self.format_ticker(pos['Ticker'], pos.get('Source', ''))
                html += f"""
                <tr>
                    <td><strong>{ticker_display}</strong></td>
                    <td>{pos.get('Company', 'N/A')[:25]}</td>
                    <td><small>{pos.get('Source', 'N/A')[:15]}</small></td>
                    <td>${pos['Price']}</td>
                    <td>{pos.get('Distance %', 0)}%</td>
                    <td style="color: {'green' if pos.get('Day Change %', 0) > 0 else 'red'};">{pos.get('Day Change %', 0):+.2f}%</td>
                    <td>{'✓' if pos.get('MACD_Buy') else ''}</td>
                    <td>{'✓' if pos.get('BB_Buy') else ''}</td>
                    <td>{'✓' if pos.get('Coppock_Buy') else ''}</td>
                    <td>{'✓' if pos.get('Ultimate_Buy') else ''}</td>
                    <td>{pos.get('RSI', 'N/A')}</td>
                </tr>
                """
            html += "</table><br>"

        # 6. Top 30 Early Signals
        if self.all_early:
            top_early = sorted(self.all_early, key=lambda x: x.get('signal_weight', 0), reverse=True)[:30]
            html += """
            <h3>🟡 EARLY BUY SIGNALS (Top 30 by Weight)</h3>
            <table border="1" cellpadding="5" style="border-collapse: collapse;">
                <tr style="background-color: #FFFFE0;">
                    <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>Day %</th><th>Wt</th><th>MACD</th><th>BB</th><th>WillR</th><th>Cop</th><th>Ult</th><th>RSI</th>
                </tr>
            """
            for pos in top_early:
                ticker_display = self.format_ticker(pos['Ticker'], pos.get('Source', ''))
                html += f"""
                <tr>
                    <td><strong>{ticker_display}</strong></td>
                    <td>{pos.get('Company', 'N/A')[:25]}</td>
                    <td><small>{pos.get('Source', 'N/A')[:15]}</small></td>
                    <td>${pos['Price']}</td>
                    <td style="color: {'green' if pos.get('Day Change %', 0) > 0 else 'red'};">{pos.get('Day Change %', 0):+.2f}%</td>
                    <td><strong>{pos.get('signal_weight', 0)}</strong></td>
                    <td>{'✓' if pos.get('MACD_Buy') else ''}</td>
                    <td>{'✓' if pos.get('BB_Buy') else ''}</td>
                    <td>{'✓' if pos.get('WillR_Buy') else ''}</td>
                    <td>{'✓' if pos.get('Coppock_Buy') else ''}</td>
                    <td>{'✓' if pos.get('Ultimate_Buy') else ''}</td>
                    <td>{pos.get('RSI', 'N/A')}</td>
                </tr>
                """
            html += "</table><br>"

        html += "</body></html>"
        return html

    def send_email(self, subject):
        try:
            print(f"Attempting to send email to {EMAIL_CONFIG['recipient_email']}...")
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['sender_email']
            msg['To'] = EMAIL_CONFIG['recipient_email']
            msg['Subject'] = subject
            
            html_content = self.generate_html()
            msg.attach(MIMEText(html_content, 'html'))
            
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.send_message(msg)
            server.quit()
            print(f"✓ Email sent successfully: {subject}")
            return True
        except Exception as e:
            print(f"✗ Email failed: {e}")
            return False
