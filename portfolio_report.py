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


class PortfolioReport:
    def __init__(self, scan_results, position_values=None, is_friends_mode=False):
        self.all_results = scan_results['all_results']
        self.position_values = position_values or {}
        self.is_friends_mode = is_friends_mode
        self.report_title = "Portfolio"
        
        # Only add position values if we have them
        for r in self.all_results:
            r['position_value'] = self.position_values.get(r['ticker'], 0)
        
        # Only track exits for mystocks mode (not friends)
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
    
    def save_exit_history(self):
        try:
            with open('exit_history.json', 'w') as f:
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
                    'position_value': result.get('position_value', 0),
                })
        
        exits_list = self.exit_history.get('exits', []) + new_exits
        recent_exits = [e for e in exits_list if datetime.fromisoformat(e['exit_date']) >= cutoff]
        
        self.exit_history = {'previous_buys': list(current_buys), 'exits': recent_exits, 'last_updated': now.isoformat()}
        self.save_exit_history()
        return sorted(recent_exits, key=lambda x: x['exit_date'], reverse=True)
    
    def group_by_zones(self):
        # Sort by momentum first, then position value
        self.strong_buys = sorted([r for r in self.all_results if r.get('psar_zone') == 'STRONG_BUY'], 
                                   key=lambda x: (-x.get('psar_momentum', 0), -x['position_value']))
        self.buys = sorted([r for r in self.all_results if r.get('psar_zone') == 'BUY'], 
                           key=lambda x: (-x.get('psar_momentum', 0), -x['position_value']))
        self.neutrals = sorted([r for r in self.all_results if r.get('psar_zone') == 'NEUTRAL'], 
                               key=lambda x: (-x.get('psar_momentum', 0), -x['position_value']))
        self.weak = sorted([r for r in self.all_results if r.get('psar_zone') == 'WEAK'], 
                           key=lambda x: (-x.get('psar_momentum', 0), -x['position_value']))
        self.sells = sorted([r for r in self.all_results if r.get('psar_zone') == 'SELL'], 
                            key=lambda x: (-x.get('psar_momentum', 0), -x['position_value']))
    
    def get_zone_color(self, zone):
        return {'STRONG_BUY': '#1e8449', 'BUY': '#27ae60', 'NEUTRAL': '#f39c12', 
                'WEAK': '#e67e22', 'SELL': '#c0392b'}.get(zone, '#7f8c8d')
    
    def get_zone_emoji(self, zone):
        return {'STRONG_BUY': '🟢🟢', 'BUY': '🟢', 'NEUTRAL': '🟡', 
                'WEAK': '🟠', 'SELL': '🔴'}.get(zone, '⚪')
    
    def get_momentum_display(self, momentum):
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
    
    def format_value(self, value):
        if value >= 1000000:
            return f"${value/1000000:.1f}M"
        elif value >= 1000:
            return f"${value/1000:.0f}K"
        elif value > 0:
            return f"${value:.0f}"
        else:
            return ""
    
    def get_covered_call_recommendation(self, ticker, current_price):
        """
        Get covered call recommendation.
        Strike selection: max(8% above price, delta ~0.10 strike)
        Whichever is FURTHER from current price.
        """
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            if not expirations:
                return None
            
            today = datetime.now()
            best_exp = None
            for exp_str in expirations:
                dte = (datetime.strptime(exp_str, '%Y-%m-%d') - today).days
                if 21 <= dte <= 60:
                    best_exp = exp_str
                    break
            
            if not best_exp:
                for exp_str in expirations:
                    if (datetime.strptime(exp_str, '%Y-%m-%d') - today).days >= 14:
                        best_exp = exp_str
                        break
            
            if not best_exp:
                return None
            
            calls = stock.option_chain(best_exp).calls
            if calls.empty:
                return None
            
            otm_calls = calls[calls['strike'] > current_price]
            if otm_calls.empty:
                return None
            
            dte = (datetime.strptime(best_exp, '%Y-%m-%d') - today).days
            
            # Strategy: max(8% above price, delta 0.10 strike)
            # 8% above price
            min_strike_8pct = current_price * 1.08
            
            # Delta 0.10 strike - typically ~15-20% OTM for 30-45 DTE
            # Look for call with delta closest to 0.10 if available
            if 'delta' in otm_calls.columns:
                delta_10_calls = otm_calls[otm_calls['delta'].between(0.08, 0.15)]
                if not delta_10_calls.empty:
                    delta_10_strike = delta_10_calls.iloc[0]['strike']
                else:
                    # Estimate: delta 0.10 is roughly 15-20% OTM
                    delta_10_strike = current_price * 1.15
            else:
                # No delta available, estimate
                delta_10_strike = current_price * 1.15
            
            # Use whichever is FURTHER from current price
            target_min_strike = max(min_strike_8pct, delta_10_strike)
            
            # Find calls at or above our target
            target_calls = otm_calls[otm_calls['strike'] >= target_min_strike]
            
            if not target_calls.empty:
                # Get the first one at or above target with decent bid
                target_calls_with_bid = target_calls[target_calls['bid'] > 0]
                if not target_calls_with_bid.empty:
                    best_call = target_calls_with_bid.iloc[0]
                else:
                    best_call = target_calls.iloc[0]
            else:
                # Fallback to anything 5%+ OTM
                fallback = otm_calls[otm_calls['strike'] >= current_price * 1.05]
                if not fallback.empty:
                    best_call = fallback.iloc[0]
                else:
                    best_call = otm_calls.iloc[0]
            
            strike, bid, ask = best_call['strike'], best_call['bid'], best_call['ask']
            mid_price = (bid + ask) / 2 if bid > 0 else ask
            
            return {
                'expiration': best_exp, 'strike': strike, 'mid_price': mid_price, 'dte': dte,
                'premium_pct': (mid_price / current_price) * 100,
                'annualized_yield': ((mid_price / current_price) * 100 / dte) * 365 if dte > 0 else 0,
                'upside_to_strike': ((strike - current_price) / current_price) * 100
            }
        except:
            return None
    
    def build_email_body(self):
        html = """
        <html><head><style>
            body { font-family: Arial, sans-serif; font-size: 12px; }
            table { border-collapse: collapse; width: 100%; margin: 10px 0; }
            th { padding: 8px; text-align: left; font-size: 11px; }
            td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }
            tr:hover { background-color: #f5f5f5; }
            .section-strongbuy { background-color: #1e8449; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-buy { background-color: #27ae60; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-neutral { background-color: #f39c12; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-weak { background-color: #e67e22; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-sell { background-color: #c0392b; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-blue { background-color: #2980b9; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-gray { background-color: #7f8c8d; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-red { background-color: #c0392b; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .th-strongbuy { background-color: #1e8449; color: white; }
            .th-buy { background-color: #27ae60; color: white; }
            .th-neutral { background-color: #f39c12; color: white; }
            .th-weak { background-color: #e67e22; color: white; }
            .th-sell { background-color: #c0392b; color: white; }
            .th-blue { background-color: #2980b9; color: white; }
            .th-red { background-color: #c0392b; color: white; }
            .th-gray { background-color: #7f8c8d; color: white; }
            .alert-box { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .alert-green { background-color: #d4edda; border-left: 4px solid #27ae60; }
            .alert-red { background-color: #f8d7da; border-left: 4px solid #c0392b; }
            .summary-box { background-color: #ecf0f1; padding: 15px; margin: 15px 0; border-radius: 5px; }
        </style></head><body>
        """
        
        html += f"<h2>📊 {self.report_title} Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>"
        
        # PUT/CALL RATIO SENTIMENT INDICATOR
        try:
            from market_scanner import get_market_put_call_ratio
            pc_data = get_market_put_call_ratio()
            
            if pc_data:
                pc_ratio = pc_data.get('pc_ratio')
                warning = pc_data.get('warning')
                warning_level = pc_data.get('warning_level')
                psar_note = pc_data.get('psar_note', '')
                
                # Color based on warning level
                if warning_level == 'DANGER':
                    box_color = '#f8d7da'
                    border_color = '#dc3545'
                elif warning_level == 'CAUTION':
                    box_color = '#fff3cd'
                    border_color = '#ffc107'
                elif warning_level in ['OPPORTUNITY', 'BULLISH']:
                    box_color = '#d4edda'
                    border_color = '#28a745'
                else:
                    box_color = '#e2e3e5'
                    border_color = '#6c757d'
                
                html += f"""
                <div style='background-color:{box_color}; border-left:4px solid {border_color}; padding:10px; margin:10px 0;'>
                    <strong>🎯 Market Sentiment:</strong> P/C Ratio <strong>{pc_ratio:.2f}</strong> | {psar_note}<br>
                    <span style='font-size:12px;'>{warning}</span>
                </div>
                """
        except Exception as e:
            pass  # Skip if can't get P/C data
        
        # SUMMARY - different format for friends vs mystocks
        if self.is_friends_mode:
            # Friends mode: just show counts, no dollar values
            html += f"""
            <div class='summary-box'>
                <h3 style='margin-top:0;'>Portfolio by PSAR Zone</h3>
                <table style='width:auto;'>
                    <tr><td><strong>Total Positions:</strong></td><td><strong>{len(self.all_results)}</strong></td></tr>
                    <tr><td>🟢🟢 <strong>STRONG BUY:</strong></td><td><strong>{len(self.strong_buys)}</strong></td></tr>
                    <tr><td>🟢 <strong>BUY:</strong></td><td><strong>{len(self.buys)}</strong></td></tr>
                    <tr><td>🟡 <strong>NEUTRAL:</strong></td><td>{len(self.neutrals)}</td></tr>
                    <tr><td>🟠 <strong>WEAK:</strong></td><td>{len(self.weak)}</td></tr>
                    <tr><td>🔴 <strong>SELL:</strong></td><td>{len(self.sells)}</td></tr>
                </table>
            </div>
            """
        else:
            # Mystocks mode: show dollar values
            total_value = sum(r.get('position_value', 0) for r in self.all_results)
            zone_values = {
                'STRONG_BUY': sum(r['position_value'] for r in self.strong_buys),
                'BUY': sum(r['position_value'] for r in self.buys),
                'NEUTRAL': sum(r['position_value'] for r in self.neutrals),
                'WEAK': sum(r['position_value'] for r in self.weak),
                'SELL': sum(r['position_value'] for r in self.sells),
            }
            
            html += f"""
            <div class='summary-box'>
                <h3 style='margin-top:0;'>Portfolio by PSAR Zone</h3>
                <table style='width:auto;'>
                    <tr><td><strong>Total Tracked:</strong></td><td><strong>{self.format_value(total_value)}</strong> ({len(self.all_results)} positions)</td></tr>
                    <tr><td>🟢🟢 <strong>STRONG BUY:</strong></td><td>{self.format_value(zone_values['STRONG_BUY'])} ({len(self.strong_buys)})</td></tr>
                    <tr><td>🟢 <strong>BUY:</strong></td><td>{self.format_value(zone_values['BUY'])} ({len(self.buys)})</td></tr>
                    <tr><td>🟡 <strong>NEUTRAL:</strong></td><td>{self.format_value(zone_values['NEUTRAL'])} ({len(self.neutrals)})</td></tr>
                    <tr><td>🟠 <strong>WEAK:</strong></td><td>{self.format_value(zone_values['WEAK'])} ({len(self.weak)})</td></tr>
                    <tr><td>🔴 <strong>SELL:</strong></td><td>{self.format_value(zone_values['SELL'])} ({len(self.sells)})</td></tr>
                </table>
            </div>
            """
        
        # EXITS - only show for mystocks mode
        if not self.is_friends_mode and self.recent_exits:
            html += "<div class='section-red'>🚨 RECENT ZONE EXITS (Last 7 Days)</div>"
            html += "<table><tr><th class='th-red'>Ticker</th><th class='th-red'>Value</th><th class='th-red'>Date</th><th class='th-red'>Zone</th><th class='th-red'>Mom</th></tr>"
            for e in self.recent_exits[:10]:
                date_str = datetime.fromisoformat(e['exit_date']).strftime('%m/%d') if 'exit_date' in e else "?"
                val_str = self.format_value(e.get('position_value', 0))
                html += f"<tr><td><strong>{e['ticker']}</strong></td><td>{val_str}</td><td>{date_str}</td><td>{self.get_zone_emoji(e.get('psar_zone','?'))}</td><td>{self.get_momentum_display(e.get('psar_momentum', 5))}</td></tr>"
            html += "</table>"
        
        # IMPROVING STOCKS
        improving = [r for r in self.all_results if r.get('psar_zone') in ['SELL', 'WEAK', 'NEUTRAL'] 
                     and r.get('psar_momentum', 0) >= 6 and r.get('psar_distance', 0) < 0]
        if improving:
            html += "<div class='alert-box alert-green'>"
            html += f"<strong>⬆️ {len(improving)} positions improving (Momentum ≥6):</strong> "
            html += ", ".join([f"<strong>{r['ticker']}</strong> (M:{r['psar_momentum']})" 
                              for r in sorted(improving, key=lambda x: -x['psar_momentum'])[:8]])
            html += "</div>"
        
        # 🔥 OVERBOUGHT ALERT - Stocks to sell or write covered calls on
        overbought = [r for r in self.all_results if r.get('atr_status') == 'OVERBOUGHT']
        if overbought:
            overbought.sort(key=lambda x: -x.get('position_value', 0))
            html += "<div class='alert-box' style='background-color:#fff3cd; border-left:4px solid #ffc107;'>"
            html += f"<strong>🔥 {len(overbought)} positions OVERBOUGHT (consider covered calls or trimming):</strong> "
            html += ", ".join([f"<strong>{r['ticker']}</strong>" for r in overbought[:10]])
            if len(overbought) > 10:
                html += f" +{len(overbought)-10} more"
            html += "</div>"
        
        # ❄️ OVERSOLD ALERT - Good positions to add to
        oversold = [r for r in self.all_results if r.get('atr_status') == 'OVERSOLD' 
                   and r.get('psar_zone') in ['STRONG_BUY', 'BUY', 'NEUTRAL']]
        if oversold:
            oversold.sort(key=lambda x: -x.get('position_value', 0))
            html += "<div class='alert-box' style='background-color:#d1ecf1; border-left:4px solid #17a2b8;'>"
            html += f"<strong>❄️ {len(oversold)} positions OVERSOLD (good to add):</strong> "
            html += ", ".join([f"<strong>{r['ticker']}</strong>" for r in oversold[:10]])
            if len(oversold) > 10:
                html += f" +{len(oversold)-10} more"
            html += "</div>"
        
        # CONCENTRATED POSITIONS - only for mystocks mode with position values
        if not self.is_friends_mode:
            concentrated = [r for r in self.all_results if r.get('position_value', 0) >= 10000]
            if concentrated:
                html += f"<div class='section-gray'>💎 CONCENTRATED POSITIONS (>$10K) - {len(concentrated)} positions, {self.format_value(sum(r['position_value'] for r in concentrated))}</div>"
                
                for zone_key, zone_class, zone_list in [
                    ('STRONG_BUY', 'strongbuy', [r for r in concentrated if r.get('psar_zone') == 'STRONG_BUY']),
                    ('BUY', 'buy', [r for r in concentrated if r.get('psar_zone') == 'BUY']),
                    ('NEUTRAL', 'neutral', [r for r in concentrated if r.get('psar_zone') == 'NEUTRAL']),
                    ('WEAK', 'weak', [r for r in concentrated if r.get('psar_zone') == 'WEAK']),
                    ('SELL', 'sell', [r for r in concentrated if r.get('psar_zone') == 'SELL']),
                ]:
                    if zone_list:
                        zone_val = sum(r['position_value'] for r in zone_list)
                        html += f"<h4 style='color:{self.get_zone_color(zone_key)};'>{self.get_zone_emoji(zone_key)} {zone_key} ({len(zone_list)}, {self.format_value(zone_val)})</h4>"
                        html += self._build_table_with_value(zone_list, zone_class)
            
            # COVERED CALLS - only for mystocks mode
            cc_candidates = [r for r in concentrated if r.get('psar_zone') in ['NEUTRAL', 'WEAK', 'SELL']] if concentrated else []
            if cc_candidates:
                html += "<div class='section-blue'>📞 COVERED CALL OPPORTUNITIES</div>"
                html += "<table><tr><th class='th-blue'>Ticker</th><th class='th-blue'>Value</th><th class='th-blue'>Zone</th><th class='th-blue'>Price</th><th class='th-blue'>Exp</th><th class='th-blue'>Strike</th><th class='th-blue'>Upside</th><th class='th-blue'>Ann.Yield</th></tr>"
                
                for r in cc_candidates[:15]:
                    cc = self.get_covered_call_recommendation(r['ticker'], r['price'])
                    zone = r.get('psar_zone', 'UNKNOWN')
                    if cc:
                        html += f"<tr><td><strong>{r['ticker']}</strong></td><td>{self.format_value(r['position_value'])}</td><td style='color:{self.get_zone_color(zone)};'>{self.get_zone_emoji(zone)}</td><td>${r['price']:.2f}</td><td>{cc['expiration']} ({cc['dte']}d)</td><td>${cc['strike']:.2f}</td><td>+{cc['upside_to_strike']:.1f}%</td><td><strong>{cc['annualized_yield']:.0f}%</strong></td></tr>"
                    else:
                        html += f"<tr><td><strong>{r['ticker']}</strong></td><td>{self.format_value(r['position_value'])}</td><td style='color:{self.get_zone_color(zone)};'>{self.get_zone_emoji(zone)}</td><td>${r['price']:.2f}</td><td colspan='4' style='color:#999;'>No options</td></tr>"
                html += "</table>"
        
        # COVERED CALLS FOR FRIENDS MODE
        if self.is_friends_mode:
            cc_candidates = [r for r in self.all_results if r.get('psar_zone') in ['NEUTRAL', 'WEAK', 'SELL']]
            if cc_candidates:
                html += "<div class='section-blue'>📞 POTENTIAL COVERED CALL OPPORTUNITIES</div>"
                html += "<p style='font-size:11px;color:#666;margin:5px 0;'>Stocks in NEUTRAL/WEAK/SELL zones - consider writing covered calls to generate income while waiting</p>"
                html += "<table><tr><th class='th-blue'>Ticker</th><th class='th-blue'>Zone</th><th class='th-blue'>Price</th><th class='th-blue'>PSAR%</th><th class='th-blue'>Exp</th><th class='th-blue'>Strike</th><th class='th-blue'>Upside</th><th class='th-blue'>Ann.Yield</th></tr>"
                
                for r in cc_candidates[:20]:
                    cc = self.get_covered_call_recommendation(r['ticker'], r['price'])
                    zone = r.get('psar_zone', 'UNKNOWN')
                    if cc:
                        html += f"<tr><td><strong>{r['ticker']}</strong></td><td style='color:{self.get_zone_color(zone)};'>{self.get_zone_emoji(zone)}</td><td>${r['price']:.2f}</td><td>{r['psar_distance']:+.1f}%</td><td>{cc['expiration']} ({cc['dte']}d)</td><td>${cc['strike']:.2f}</td><td>+{cc['upside_to_strike']:.1f}%</td><td><strong>{cc['annualized_yield']:.0f}%</strong></td></tr>"
                    else:
                        html += f"<tr><td><strong>{r['ticker']}</strong></td><td style='color:{self.get_zone_color(zone)};'>{self.get_zone_emoji(zone)}</td><td>${r['price']:.2f}</td><td>{r['psar_distance']:+.1f}%</td><td colspan='4' style='color:#999;'>No options available</td></tr>"
                html += "</table>"
        
        # ALL POSITIONS BY ZONE
        html += "<div class='section-gray'>📋 ALL POSITIONS BY ZONE</div>"
        
        for zone_key, zone_class, zone_list, zone_title in [
            ('STRONG_BUY', 'strongbuy', self.strong_buys, '🟢🟢 STRONG BUY'),
            ('BUY', 'buy', self.buys, '🟢 BUY'),
            ('NEUTRAL', 'neutral', self.neutrals, '🟡 NEUTRAL'),
            ('WEAK', 'weak', self.weak, '🟠 WEAK'),
            ('SELL', 'sell', self.sells, '🔴 SELL'),
        ]:
            if zone_list:
                html += f"<h4 style='color:{self.get_zone_color(zone_key)};'>{zone_title} ({len(zone_list)})</h4>"
                if self.is_friends_mode:
                    html += self._build_zone_table_no_value(zone_list, zone_class)
                else:
                    html += self._build_zone_table(zone_list, zone_class)
        
        html += """<hr><p style='font-size:10px;color:#7f8c8d;'>
        <strong>Momentum (1-10):</strong> Trajectory since signal start. 8-10=Strong, 4-7=Neutral, 1-3=Weak<br>
        <strong>ATR:</strong> 🔥=Overbought (price > EMA8+ATR, consider selling/covered calls) | ❄️=Oversold (good to buy) | —=Normal<br>
        <strong>PRSI:</strong> PSAR on RSI. ↗️=RSI trending up | ↘️=RSI trending down<br>
        <strong>IR:</strong> MACD(35)+Ultimate(15)+Williams(15)+Bollinger(15)+Coppock(20)=Max 100
        </p></body></html>"""
        
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
