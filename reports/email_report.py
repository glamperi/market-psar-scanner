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

# Import the fixed Cboe script
from data.cboe import get_cboe_ratios_and_analyze 

EXIT_HISTORY_FILE = 'exit_history.json'

class EmailReport:
    def __init__(self, scan_results, eps_filter=None, rev_filter=None, mc_filter=None):
        self.scan_results = scan_results
        self.all_results = scan_results['all_results']
        self.watchlist_results = scan_results['watchlist_results']
        self.eps_filter = eps_filter
        self.rev_filter = rev_filter
        self.mc_filter = mc_filter if mc_filter else 10
        
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
        """
        Updates the exit history with any stocks that have moved out of a bullish zone.
        Returns a list of recent exits (last 7 days).
        """
        now = datetime.now()
        recent_exits = []
        
        # Tickers that are no longer bullish
        non_bullish_tickers = {r['ticker']: r for r in self.all_results if not r.get('psar_bullish', True)}
        
        # Tickers that were previously a buy but are no longer
        previous_buys = set(self.exit_history.get('previous_buys', []))
        
        # Check for new exits
        for ticker in previous_buys:
            if ticker in non_bullish_tickers:
                result = non_bullish_tickers[ticker]
                
                # Check if this exit is new today (to avoid duplicates from the same run)
                # This logic assumes the main scan runs once per day/session
                is_new_exit = True
                if self.exit_history.get('exits'):
                    last_exit = next(
                        (e for e in reversed(self.exit_history['exits']) if e['ticker'] == ticker), 
                        None
                    )
                    if last_exit:
                        last_exit_date = datetime.fromisoformat(last_exit['exit_date'])
                        if (now - last_exit_date).total_seconds() < 3600: # Exit recorded in the last hour
                            is_new_exit = False

                if is_new_exit:
                    exit_record = {
                        'ticker': ticker,
                        'exit_date': now.isoformat(),
                        'exit_price': result['current_price'],
                        'psar_zone': result.get('psar_zone'),
                        'psar_momentum': result.get('psar_momentum')
                    }
                    self.exit_history.setdefault('exits', []).append(exit_record)
                    recent_exits.append(exit_record)
        
        # Update previous_buys list for the next run
        current_buys = {r['ticker'] for r in self.all_results if r.get('psar_bullish', True)}
        self.exit_history['previous_buys'] = list(current_buys)
        
        self.save_exit_history()

        # Filter recent exits to only show those in the last 7 days
        seven_days_ago = now - timedelta(days=7)
        return [
            e for e in self.exit_history.get('exits', []) 
            if datetime.fromisoformat(e['exit_date']) >= seven_days_ago
        ]

    # --- NEW MARKET SENTIMENT METHOD ---
    def get_market_sentiment_html(self):
        """
        Calls the CBOE analysis function, gets its string return, and formats it
        to match the style of the previous reports (using <pre> tag).
        """
        try:
            # The imported function handles the fetching, analysis, and returns the formatted string
            analysis_output = get_cboe_ratios_and_analyze()
            if not analysis_output: return ""
            
            # Use <pre> tag and specific styling to ensure text formatting/line breaks are preserved 
            # and it stands out in the report. This recreates the look from your PDFs.
            html = f"""
            <div style='margin-bottom: 15px; border-bottom: 2px solid #ccc; padding-bottom: 10px; border-top: 2px solid #ccc; padding-top: 10px; background-color: #ecf0f1;'>
                <pre style='font-family: monospace; white-space: pre-wrap; margin: 0; padding: 0; font-size: 13px; color: #333;'>{analysis_output}</pre>
            </div>
            """
            return html
        except Exception as e:
            # If the CBOE fetch fails, still generate the rest of the report
            return f"<div style='color: red;'>MARKET SENTIMENT ANALYSIS ERROR: {e}</div>"
    # --- END NEW METHOD ---
    
    def _generate_table_html(self, results, table_class):
        """Generates the HTML table block for a given set of results."""
        # ... (implementation of _generate_table_html is assumed to be in your original file)
        # Placeholder for brevity, but this should contain your full table generation logic
        
        # This is a simplified example based on your PDF column headers, your actual logic is more complex.
        if not results: return ""
        
        html = f"<table class='{table_class}'><thead><tr><th>Ticker</th><th>Zone</th><th>Days</th><th>PSAR %</th><th>OBV</th><th>PRSI</th><th>MACD</th><th>50MA</th><th>Price</th></tr></thead><tbody>"
        
        # Sort by confirmation strength: freshest signals with best confirmation first
        results.sort(key=lambda r: (
            r.get('days_since_signal', 99),              # 1. Day 1 first
            -(r.get('obv_status') == 'CONFIRM'),         # 2. OBV confirms
            -r.get('prsi_bullish', False),               # 3. PRSI bullish
            -r.get('has_macd', False),                   # 4. MACD bullish
            -r.get('above_ma50', False),                 # 5. Above 50MA
        ))
        
        for r in results:
            ticker = r['ticker']
            zone = r['psar_zone']
            days = r.get('days_since_signal', 'N/A')
            psar_perc = f"{r.get('psar_distance_percent', r.get('psar_distance', 0.0)):.1f}%"
            obv = '🟢' if r.get('obv_status') == 'CONFIRM' else ('🔴' if r.get('obv_status') == 'DIVERGE' else '⚪')
            prsi = '↗️' if r.get('prsi_bullish') else '↘️'
            macd = '✓' if r.get('has_macd') else ''
            ma50 = '✓' if r.get('above_ma50', False) else ''
            price = f"${r.get('current_price', r.get('price', 0.0)):.2f}"
            
            # Add IBD Star if available and configured in your scanner
            star = '⭐' if r.get('ibd_url') else ''
            
            html += f"<tr><td><a href='https://finance.yahoo.com/quote/{ticker}'>{ticker}</a>{star}</td><td>{zone}</td><td>{days}</td><td>{psar_perc}</td><td>{obv}</td><td>{prsi}</td><td>{macd}</td><td>{ma50}</td><td>{price}</td></tr>"

        html += "</tbody></table>"
        return html


    def build_email_body(self):
        """Generates the full HTML body for the email report."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M')

        # NOTE: Your full html_style is assumed to be defined elsewhere or imported/built within a larger class structure
        # Since I don't have the full dependencies, I'll keep the variable placeholder.
        html_style = """
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f4f4; color: #333; margin: 0; padding: 20px; }
            .section-header { font-size: 14px; font-weight: bold; padding: 5px 10px; margin-top: 20px; margin-bottom: 5px; border-radius: 3px; }
            .section-top-tier { background-color: #4CAF50; color: white; }
            .section-strong-buy { background-color: #8BC34A; color: white; }
            .section-buy { background-color: #CDDC39; color: black; }
            .section-neutral { background-color: #FFEB3B; color: black; }
            .section-weak { background-color: #FF9800; color: white; }
            .section-sell { background-color: #F44336; color: white; }
            .section-exits { background-color: #795548; color: white; }
            .section-sentiment { background-color: #2c3e50; color: white; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 12px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #ecf0f1; font-weight: bold; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f1f1f1; }
            pre { white-space: pre-wrap; } /* For sentiment block */
        </style>
        """

        html = f"""
        <html>
        <head>{html_style}</head>
        <body>
        
        <div style='font-size: 18px; font-weight: bold; margin-bottom: 15px;'>Market Scanner Report - {now}</div>
        
        """
        
        # Filters description
        filter_parts = [f"${self.mc_filter}B+ market cap"]
        if self.eps_filter: filter_parts.append(f"EPS > {self.eps_filter}%")
        if self.rev_filter: filter_parts.append(f"REV > {self.rev_filter}%")
        filter_desc = " | ".join(filter_parts)
        html += f"<p style='color:#7f8c8d; font-size:11px;'>Scanned ~2,500 stocks from S&P 500, NASDAQ 100, Russell 2000, IBD | Filtered: {filter_desc} | {len(self.all_results)} stocks passed</p>"

        # --- INSERT MARKET SENTIMENT HERE ---
        html += self.get_market_sentiment_html()
        # ------------------------------------

        html += "<div class='section-header section-sentiment'>HPSAR ZONE & MOMENTUM GUIDE</div>"
        # Assuming you have a _generate_guide_table_html method or a static guide string
        html += """
        <table class='guide-table'>
            <thead><tr><th>Zone</th><th>PSAR %</th><th>Criteria</th><th>Action</th></tr></thead>
            <tbody>
                <tr><td>🟢🟢🟢 TOP TIER</td><td>> +5%</td><td>+ Mom≥7 + IR≥40 + Above 50MA + OBV=CONFIRM</td><td>BUY with confidence</td></tr>
                <tr><td>🟢🟢 STRONG BUY</td><td>> +5%</td><td>Strong uptrend</td><td>BUY / Hold</td></tr>
                <tr><td>🟢 BUY</td><td>+2% to +5%</td><td>Healthy uptrend</td><td>Hold / Add on dips</td></tr>
                <tr><td>🟡 NEUTRAL</td><td>-2% to +2%</td><td>Could go either way</td><td>Watch closely</td></tr>
                <tr><td>🟠 WEAK</td><td>-2% to -5%</td><td>Downtrend, might reverse</td><td>Caution / Covered calls</td></tr>
                <tr><td>🔴 SELL</td><td>< -5%</td><td>Confirmed downtrend</td><td>Exit or hedge</td></tr>
            </tbody>
        </table>
        """

        # Prepare grouped results
        all_strong = [r for r in self.all_results if r.get('psar_zone') == 'STRONG_BUY']
        top_tier = [r for r in all_strong if 
                    r.get('psar_momentum', 0) >= 7 and 
                    r.get('signal_weight', 0) >= 40 and 
                    r.get('above_ma50', False) and
                    r.get('obv_status', 'NEUTRAL') == 'CONFIRM']
        
        # Remove top_tier from strong_buy list
        strong_buy_tickers = {r['ticker'] for r in all_strong}
        top_tier_tickers = {r['ticker'] for r in top_tier}
        strong_buy = [r for r in all_strong if r['ticker'] not in top_tier_tickers]

        buy = [r for r in self.all_results if r.get('psar_zone') == 'BUY']
        neutral = [r for r in self.all_results if r.get('psar_zone') == 'NEUTRAL']
        weak = [r for r in self.all_results if r.get('psar_zone') == 'WEAK']
        sell = [r for r in self.all_results if r.get('psar_zone') == 'SELL']

        # Recent Exits 
        if self.recent_exits:
            html += "<div class='section-header section-exits'>🛑 RECENT EXITS (Last 7 Days)</div>"
            html += "<table><thead><tr><th>Ticker</th><th>Date</th><th>Exit Price</th><th>Zone</th><th>Mom</th></tr></thead><tbody>"
            for r in self.recent_exits:
                exit_date = datetime.fromisoformat(r['exit_date']).strftime('%Y-%m-%d')
                price = f"${r['exit_price']:.2f}"
                html += f"<tr><td>{r['ticker']}</td><td>{exit_date}</td><td>{price}</td><td>{r['psar_zone']}</td><td>{r['psar_momentum']}</td></tr>"
            html += "</tbody></table>"

        # 1. TOP TIER BUYS
        if top_tier:
            html += f"<div class='section-header section-top-tier'>🟢🟢🟢 TOP TIER BUYS ({len(top_tier)} positions)</div>"
            html += self._generate_table_html(top_tier, 'top-tier')
            
        # 2. STRONG BUYS
        if strong_buy:
            html += f"<div class='section-header section-strong-buy'>🟢🟢 STRONG BUY ZONE ({len(strong_buy)} positions)</div>"
            html += self._generate_table_html(strong_buy, 'strong-buy')

        # 3. BUYS
        if buy:
            html += f"<div class='section-header section-buy'>🟢 BUY ZONE ({len(buy)} positions)</div>"
            html += self._generate_table_html(buy, 'buy')
            
        # 4. NEUTRAL
        if neutral:
            html += f"<div class='section-header section-neutral'>🟡 NEUTRAL ZONE ({len(neutral)} positions)</div>"
            html += self._generate_table_html(neutral, 'neutral')

        # 5. WEAK
        if weak:
            html += f"<div class='section-header section-weak'>🟠 WEAK ZONE (Covered Call Opportunities) ({len(weak)} positions)</div>"
            html += self._generate_table_html(weak, 'weak')

        # 6. SELL
        if sell:
            html += f"<div class='section-header section-sell'>🔴 SELL ZONE (Recommend Exit / Hedge) ({len(sell)} positions)</div>"
            html += self._generate_table_html(sell, 'sell')

        # Watchlist Results
        if self.watchlist_results:
            html += f"<div class='section-header section-sentiment'>⭐ WATCHLIST SCAN ({len(self.watchlist_results)} stocks)</div>"
            html += self._generate_table_html(self.watchlist_results, 'watchlist')

        html += "</body></html>"
        return html


    def send_email(self, additional_email=None):
        """Sends the HTML report via email."""
        # Get email credentials from environment variables (assuming you use these)
        sender_email = os.environ.get('GMAIL_EMAIL')
        sender_password = os.environ.get('GMAIL_PASSWORD')
        recipient_email = os.environ.get('RECIPIENT_EMAIL')

        if not sender_email or not sender_password or not recipient_email:
            print("\n❌ ERROR: Missing email credentials")
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
            
            print(f"\n✓ Market report sent to: {', '.join(recipients)}")
            
        except Exception as e:
            print(f"\n❌ ERROR sending email: {e}")
