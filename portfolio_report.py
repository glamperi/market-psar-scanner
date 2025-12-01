"""
Portfolio Report Generator - PSAR Zones with Momentum Score
Supports both -mystocks mode (with position values) and -friends mode (without)
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import yfinance as yf

from cboe import get_cboe_ratios_and_analyze 


class PortfolioReport:
    def __init__(self, scan_results, position_values=None, is_friends_mode=False, custom_title=None):
        self.all_results = scan_results['all_results']
        self.position_values = position_values or {}
        self.is_friends_mode = is_friends_mode
        self.report_title = custom_title if custom_title else "Portfolio"
        
        for r in self.all_results:
            r['position_value'] = self.position_values.get(r['ticker'], 0)
        
        if not is_friends_mode:
            self.exit_history = self.load_exit_history()
            self.recent_exits = self.update_exit_history()
        else:
            self.exit_history = {}
            self.recent_exits = []
        
        self.group_by_zones()
    
    def load_exit_history(self):
        exit_file = 'exit_history.json'
        if os.path.exists(exit_file):
            try:
                with open(exit_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    # ... (other helper methods like save_exit_history, update_exit_history, format_value, get_zone_color, get_zone_emoji, group_by_zones) ...
    
    def get_zone_color(self, zone):
        colors = {
            'STRONG_BUY': '#27ae60', 'BUY': '#2ecc71', 'NEUTRAL': '#f1c40f', 
            'WEAK': '#e67e22', 'SELL': '#e74c3c', 'UNKNOWN': '#95a5a6'
        }
        return colors.get(zone, '#95a5a6')
        
    def get_zone_emoji(self, zone):
        return {'STRONG_BUY': '🟢🟢', 'BUY': '🟢', 'NEUTRAL': '🟡', 'WEAK': '🟠', 'SELL': '🔴'}.get(zone, '⚪')
    
    def format_value(self, value):
        return f"${value:,.0f}"

    def _generate_table_html(self, stocks, zone_class, show_value=True):
        if not stocks:
            return ""

        html = f"""
        <table class='{zone_class}-table'>
            <tr>
                <th class='th-{zone_class}'>Ticker</th>
                <th class='th-{zone_class}'>Zone</th>
                <th class='th-{zone_class}'>Mom</th>
                <th class='th-{zone_class}'>PSAR %</th>
                <th class='th-{zone_class}'>IR</th>
                <th class='th-{zone_class}'>RSI</th>
                <th class='th-{zone_class}'>50MA</th>
                <th class='th-{zone_class}'>Price</th>
                {"<th class='th-value'>Value</th>" if show_value else ""}
            </tr>
        """
        for r in stocks:
            zone = r.get('psar_zone', 'UNKNOWN')
            
            # --- IBD Star Restoration ---
            is_ibd = r.get('composite', 'N/A') != 'N/A'
            ticker_display = f"⭐{r['ticker']}" if is_ibd else r['ticker']
            # --------------------------

            ma50_symbol = '↑' if r.get('above_ma50') else '↓'
            ma50_color = '#27ae60' if r.get('above_ma50') else '#e74c3c'
            
            html += f"""
            <tr>
                <td><strong>{ticker_display}</strong></td>
                <td style='color:{self.get_zone_color(zone)};'>{self.get_zone_emoji(zone)} {zone.replace('_', ' ')}</td>
                <td>{r.get('psar_momentum', 0)}</td>
                <td>{r.get('psar_distance', 0):.1f}%</td>
                <td>{r.get('signal_weight', 0)}</td>
                <td>{r.get('rsi', 0):.0f}</td>
                <td style='color:{ma50_color};'><strong>{ma50_symbol}</strong></td>
                <td>${r.get('price', 0):.2f}</td>
                {"<td>"+self.format_value(r.get('position_value', 0))+"</td>" if show_value else ""}
            </tr>
            """
        html += "</table>"
        return html

    def build_email_body(self):
        
        # NOTE: Styles assumed to be correct from previous versions
        html = """
        <html><head>
        <style>
        .section {
            border: 1px solid #ddd;
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 8px;
            font-family: monospace;
            white-space: pre-wrap;
        }
        /* ... (rest of the styles) ... */
        </style>
        </head>
        <body>
        """

        # --- MARKET SENTIMENT INDICATOR (New Cboe logic) ---
        try:
            pc_analysis_text = get_cboe_ratios_and_analyze()
            
            if pc_analysis_text:
                pc_html = pc_analysis_text.replace('\n', '<br>')
                html += f"""
                <div class="section" style="background-color: #ecf0f1; padding: 15px; margin: 15px 0; border-radius: 5px;">
                    {pc_html}
                </div>
                """
        except Exception as e:
            html += f"<p style='color:#e74c3c;'>⚠️ Failed to load Cboe Market Sentiment: {type(e).__name__}</p>"
            pass
        # ----------------------------------------------------
        
        # ... (rest of the build_email_body logic, generating portfolio tables, etc.) ...
        
        return html
    
    # ... (rest of the PortfolioReport class methods, including send_email) ...   
















     
        # ALL POSITIONS BY ZONE
   ###################################################################### 
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
        """Get PRSI (PSAR on RSI) display"""
        prsi_bullish = result.get('prsi_bullish', True)
        return '↗️' if prsi_bullish else '↘️'
    
    def _build_table_with_value(self, stocks, zone_class):
        """Full table with Value column and Indicators"""
        html = f"<table><tr><th class='th-{zone_class}'>Ticker</th><th class='th-{zone_class}'>Value</th><th class='th-{zone_class}'>Price</th><th class='th-{zone_class}'>PSAR%</th><th class='th-{zone_class}'>Mom</th><th class='th-{zone_class}'>ATR</th><th class='th-{zone_class}'>PRSI</th><th class='th-{zone_class}'>OBV</th><th class='th-{zone_class}'>IR</th><th class='th-{zone_class}'>Indicators</th></tr>"
        for r in stocks:
            zone_color = self.get_zone_color(r.get('psar_zone', 'UNKNOWN'))
            obv_html = self.get_obv_display(r.get('obv_status', 'NEUTRAL'))
            atr_html = self.get_atr_display(r)
            prsi_html = self.get_prsi_display(r)
            html += f"<tr><td><strong>{r['ticker']}</strong></td><td><strong>{self.format_value(r['position_value'])}</strong></td><td>${r['price']:.2f}</td><td style='color:{zone_color};font-weight:bold;'>{r['psar_distance']:+.1f}%</td><td>{self.get_momentum_display(r.get('psar_momentum', 5))}</td><td>{atr_html}</td><td>{prsi_html}</td><td>{obv_html}</td><td>{r['signal_weight']}</td><td style='font-size:10px;'>{self.get_indicator_symbols(r)}</td></tr>"
        return html + "</table>"
    
    def _build_zone_table(self, stocks, zone_class):
        """Table with Value column for mystocks mode"""
        html = f"<table><tr><th class='th-{zone_class}'>Ticker</th><th class='th-{zone_class}'>Value</th><th class='th-{zone_class}'>Price</th><th class='th-{zone_class}'>PSAR%</th><th class='th-{zone_class}'>Mom</th><th class='th-{zone_class}'>ATR</th><th class='th-{zone_class}'>PRSI</th><th class='th-{zone_class}'>OBV</th><th class='th-{zone_class}'>IR</th></tr>"
        for r in stocks:
            zone_color = self.get_zone_color(r.get('psar_zone', 'UNKNOWN'))
            val_str = self.format_value(r.get('position_value', 0))
            obv_html = self.get_obv_display(r.get('obv_status', 'NEUTRAL'))
            atr_html = self.get_atr_display(r)
            prsi_html = self.get_prsi_display(r)
            html += f"<tr><td><strong>{r['ticker']}</strong></td><td>{val_str}</td><td>${r['price']:.2f}</td><td style='color:{zone_color};'>{r['psar_distance']:+.1f}%</td><td>{self.get_momentum_display(r.get('psar_momentum', 5))}</td><td>{atr_html}</td><td>{prsi_html}</td><td>{obv_html}</td><td>{r['signal_weight']}</td></tr>"
        return html + "</table>"
    
    def _build_zone_table_no_value(self, stocks, zone_class):
        """Table without Value column for friends mode"""
        html = f"<table><tr><th class='th-{zone_class}'>Ticker</th><th class='th-{zone_class}'>Price</th><th class='th-{zone_class}'>PSAR%</th><th class='th-{zone_class}'>Mom</th><th class='th-{zone_class}'>ATR</th><th class='th-{zone_class}'>PRSI</th><th class='th-{zone_class}'>OBV</th><th class='th-{zone_class}'>IR</th></tr>"
        for r in stocks:
            zone_color = self.get_zone_color(r.get('psar_zone', 'UNKNOWN'))
            obv_html = self.get_obv_display(r.get('obv_status', 'NEUTRAL'))
            atr_html = self.get_atr_display(r)
            prsi_html = self.get_prsi_display(r)
            html += f"<tr><td><strong>{r['ticker']}</strong></td><td>${r['price']:.2f}</td><td style='color:{zone_color};'>{r['psar_distance']:+.1f}%</td><td>{self.get_momentum_display(r.get('psar_momentum', 5))}</td><td>{atr_html}</td><td>{prsi_html}</td><td>{obv_html}</td><td>{r['signal_weight']}</td></tr>"
        return html + "</table>"
    
    def send_email(self, additional_email=None, custom_title=None):
        sender_email = os.getenv("GMAIL_EMAIL")
        sender_password = os.getenv("GMAIL_PASSWORD")
        recipient_email = os.getenv("RECIPIENT_EMAIL")
        
        if not all([sender_email, sender_password, recipient_email]):
            print("✗ Missing email credentials")
            return
        
        # Use custom title if provided
        self.report_title = custom_title if custom_title else "Portfolio"
        
        # Build subject line - different for friends vs mystocks
        if self.is_friends_mode:
            msg_subject = f"📊 {self.report_title}: {len(self.strong_buys)} Strong Buy, {len(self.buys)} Buy - {datetime.now().strftime('%m/%d %H:%M')}"
        else:
            strong_buy_val = self.format_value(sum(r['position_value'] for r in self.strong_buys))
            buy_val = self.format_value(sum(r['position_value'] for r in self.buys))
            msg_subject = f"📊 {self.report_title}: {strong_buy_val} Strong Buy, {buy_val} Buy - {datetime.now().strftime('%m/%d %H:%M')}"
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = msg_subject
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
            print(f"\n✓ {self.report_title} report sent to: {', '.join(recipients)}")
            print(f"  SB:{len(self.strong_buys)}, B:{len(self.buys)}, N:{len(self.neutrals)}, W:{len(self.weak)}, S:{len(self.sells)}")
        except Exception as e:
            print(f"\n✗ Failed: {e}")
