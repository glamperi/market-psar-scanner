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
        """Generate the HTML content with original styling"""
        
        # Original CSS Styling
        style = """
        <style>
            body { font-family: Arial, sans-serif; color: #333; }
            h2 { color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }
            h3 { color: #34495e; margin-top: 20px; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; font-size: 14px; }
            th { background-color: #f8f9fa; border: 1px solid #ddd; padding: 8px; text-align: left; }
            td { border: 1px solid #ddd; padding: 8px; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .up { color: green; font-weight: bold; }
            .down { color: red; font-weight: bold; }
            .alert-box { background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; color: #721c24; }
        </style>
        """

        html = f"""
        <html>
        <head>{style}</head>
        <body>
            <h2>📊 Market-Wide PSAR Scanner Report</h2>
            <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        """
        
        # 1. Recent Exits
        if self.changes.get('recent_exits_7day'):
            html += """
            <div class="alert-box">
                <h3>⚠️ RECENT EXITS (Last 7 Days)</h3>
                <table>
                    <tr style="background-color: #eebbba;">
                        <th>Ticker</th><th>Company</th><th>When</th><th>Exit Price</th><th>Current</th><th>Change</th>
                    </tr>
            """
            for pos in self.changes['recent_exits_7day']:
                display_ticker = self.format_ticker(pos['Ticker'], pos.get('Source'))
                days = pos.get('days_ago', 0)
                when = f"{days} days ago" if days > 0 else "Today"
                
                exit_p = pos.get('exit_price', 0)
                curr_p = pos.get('Price', 0)
                drop = ((curr_p - exit_p) / exit_p * 100) if exit_p else 0
                drop_cls = "up" if drop > 0 else "down"

                html += f"""
                <tr>
                    <td><strong>{display_ticker}</strong></td>
                    <td>{pos.get('Company', 'N/A')[:20]}</td>
                    <td>{when}</td>
                    <td>${exit_p:.2f}</td>
                    <td>${curr_p:.2f}</td>
                    <td class="{drop_cls}">{drop:+.2f}%</td>
                </tr>
                """
            html += "</table></div>"

        # 2. New Entries
        if self.changes.get('new_entries'):
            html += """
            <h3 style="color: green;">🟢 NEW BUY SIGNALS (Entered Today)</h3>
            <table>
                <tr style="background-color: #c3e6cb;">
                    <th>Ticker</th><th>Company</th><th>Price</th><th>Day %</th><th>Score</th><th>Why?</th>
                </tr>
            """
            sorted_entries = sorted(self.changes['new_entries'], key=lambda x: x.get('signal_weight', 0), reverse=True)
            for pos in sorted_entries:
                display_ticker = self.format_ticker(pos['Ticker'], pos.get('Source'))
                day_cls = "up" if pos.get('Day Change %', 0) > 0 else "down"
                
                indicators = []
                if pos.get('MACD_Buy'): indicators.append("MACD")
                if pos.get('BB_Buy'): indicators.append("BB")
                
                html += f"""
                <tr>
                    <td><strong>{display_ticker}</strong></td>
                    <td>{pos.get('Company', 'N/A')[:20]}</td>
                    <td>${pos['Price']:.2f}</td>
                    <td class="{day_cls}">{pos.get('Day Change %', 0):+.2f}%</td>
                    <td><strong>{pos.get('signal_weight', 0)}</strong></td>
                    <td>{', '.join(indicators)}</td>
                </tr>
                """
            html += "</table>"

        # 3. Top Current Buys
        if self.all_buys:
            html += """
            <h3>🚀 TOP CURRENT BUYS</h3>
            <table>
                <tr>
                    <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>Dist %</th><th>Day %</th>
                </tr>
            """
            top_buys = sorted(self.all_buys, key=lambda x: x.get('Distance %', 0), reverse=True)[:30]
            for pos in top_buys:
                display_ticker = self.format_ticker(pos['Ticker'], pos.get('Source'))
                day_cls = "up" if pos.get('Day Change %', 0) > 0 else "down"
                
                html += f"""
                <tr>
                    <td><strong>{display_ticker}</strong></td>
                    <td>{pos.get('Company', 'N/A')[:20]}</td>
                    <td>{pos.get('Source', 'N/A')[:15]}</td>
                    <td>${pos['Price']:.2f}</td>
                    <td>{pos.get('Distance %', 0)}%</td>
                    <td class="{day_cls}">{pos.get('Day Change %', 0):+.2f}%</td>
                </tr>
                """
            html += "</table>"

        html += "</body></html>"
        return html

    def send_email(self, subject):
        try:
            print(f"Sending email to {EMAIL_CONFIG['recipient_email']}...")
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
            print(f"✓ Email sent successfully.")
            return True
        except Exception as e:
            print(f"✗ Email failed: {e}")
            return False
