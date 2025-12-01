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

from cboe import get_cboe_ratios_and_analyze 

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
        return f"M{sym(r.get('has_macd'))} B{sym(r.get('has_bb'))} W{sym(r.get('has_willr'))} U{sym(r.get('has_ultimate'))} C{sym(r.get('has_coppock'))}"
        
    def get_zone_color(self, zone):
        colors = {
            'STRONG_BUY': '#27ae60', 'BUY': '#2ecc71', 'NEUTRAL': '#f1c40f', 
            'WEAK': '#e67e22', 'SELL': '#e74c3c', 'UNKNOWN': '#95a5a6'
        }
        return colors.get(zone, '#95a5a6')
        
    def get_zone_emoji(self, zone):
        return {'STRONG_BUY': '🟢🟢', 'BUY': '🟢', 'NEUTRAL': '🟡', 'WEAK': '🟠', 'SELL': '🔴'}.get(zone, '⚪')

    def _generate_table_html(self, stocks, zone_class, show_momentum_grade=True):
        if not stocks:
            return ""

        html = f"""
        <table class='{zone_class}-table'>
            <tr>
                <th class='th-{zone_class}'>Ticker</th>
                <th class='th-{zone_class}'>Company</th>
                <th class='th-{zone_class}'>Zone</th>
                <th class='th-{zone_class}'>Mom</th>
                <th class='th-{zone_class}'>IR</th>
                <th class='th-{zone_class}'>RSI</th>
                <th class='th-{zone_class}'>PSAR %</th>
                <th class='th-{zone_class}'>50MA</th>
                <th class='th-{zone_class}'>OBV</th>
                <th class='th-{zone-class}'>EPS/REV</th>
                <th class='th-{zone_class}'>SI</th>
                <th class='th-{zone_class}'>Price</th>
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
            
            obv_color = {'CONFIRM': '#27ae60', 'WEAKEN': '#f1c40f', 'DIVERGE': '#e74c3c', 'NEUTRAL': '#95a5a6'}.get(r.get('obv_status'), '#95a5a6')
            
            si_display = f"{r.get('short_percent', 0):.1f}% / {r.get('short_ratio', 0):.1f}"
            si_style = f"style='color:#e74c3c; font-weight:bold;'" if r.get('short_percent', 0) > 15 else ""

            eps_rev_display = f"{r.get('eps_growth', 0):.0f}%/{r.get('rev_growth', 0):.0f}%"
            
            html += f"""
            <tr>
                <td><strong>{ticker_display}</strong></td>
                <td>{r.get('company', r['ticker'])[:18]}</td>
                <td style='color:{self.get_zone_color(zone)};'>{self.get_zone_emoji(zone)} {zone.replace('_', ' ')}</td>
                <td>{r.get('psar_momentum', 0)}</td>
                <td>{r.get('signal_weight', 0)}</td>
                <td>{r.get('rsi', 0):.0f}</td>
                <td>{r.get('psar_distance', 0):.1f}%</td>
                <td style='color:{ma50_color};'><strong>{ma50_symbol}</strong></td>
                <td style='color:{obv_color};'><strong>{r.get('obv_status', 'N/A')[0]}</strong></td>
                <td>{eps_rev_display}</td>
                <td {si_style}>{si_display}</td>
                <td>${r.get('price', 0):.2f}</td>
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
        
        # Group and sort results
        all_strong = [r for r in self.all_results if r.get('psar_zone') == 'STRONG_BUY']
        top_tier = sorted([r for r in all_strong if 
                            r.get('psar_momentum', 0) >= 7 and 
                            r.get('signal_weight', 0) >= 40 and 
                            r.get('above_ma50', False) and
                            r.get('obv_status', 'NEUTRAL') == 'CONFIRM' and
                            r.get('atr_status', 'NORMAL') != 'OVERBOUGHT'],
                            key=lambda x: -x.get('psar_momentum', 0))
        strong_buy = sorted([r for r in all_strong if r not in top_tier], key=lambda x: -x.get('psar_momentum', 0))
        buy = sorted([r for r in self.all_results if r.get('psar_zone') == 'BUY'], key=lambda x: -x.get('psar_momentum', 0))
        
        html += f"<h1>📈 Market Scan Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h1>"
        
        # Summary and Filter Info
        filter_parts = []
        if self.mc_filter: filter_parts.append(f"MC > ${self.mc_filter}B")
        if self.eps_filter: filter_parts.append(f"EPS > {self.eps_filter}%")
        if self.rev_filter: filter_parts.append(f"REV > {self.rev_filter}%")
        filter_desc = " | ".join(filter_parts)
        html += f"<p style='color:#7f8c8d; font-size:11px;'>Scanned ~2,500 stocks from S&P 500, NASDAQ 100, Russell 2000, IBD | Filtered: {filter_desc} | {len(self.all_results)} stocks passed</p>"


        # Recent Exits (Logic assumed to be elsewhere but placeholder kept)
        if self.recent_exits:
            html += "<div class='section-exits'>🛑 RECENT EXITS (Last 7 Days)</div>"
            # Logic to generate exit table here


        # 1. TOP TIER BUYS
        if top_tier:
            html += "<div class='section-top-tier'>🟢🟢🟢 TOP TIER BUYS (Momentum 7+, Weight 40+, OBV Confirm)</div>"
            html += self._generate_table_html(top_tier, 'top-tier')
            
        # 2. STRONG BUYS
        if strong_buy:
            html += "<div class='section-strong-buy'>🟢🟢 STRONG BUY ZONE</div>"
            html += self._generate_table_html(strong_buy, 'strong-buy')

        # 3. BUYS
        if buy:
            html += "<div class='section-buy'>🟢 BUY ZONE</div>"
            html += self._generate_table_html(buy, 'buy')

        # ... (rest of the report sections - NEUTRAL, WEAK, SELL) ...
        
        html += "</body></html>"
        return html
    
    def send_email(self, additional_email=None, custom_subject=None):
        # ... (implementation of send_email assumed to be present) ...
        pass
