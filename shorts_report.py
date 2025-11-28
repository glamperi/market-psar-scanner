"""
Shorts Report Generator
Analyzes potential short candidates with squeeze risk warnings
Includes deep ITM put recommendations for bearish positions
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import yfinance as yf

class ShortsReport:
    def __init__(self, scan_results, mc_filter=None, include_adr=False):
        self.scan_results = scan_results
        self.all_results = scan_results['all_results']
        self.mc_filter = mc_filter
        self.include_adr = include_adr
        self.is_market_scan = mc_filter is not None  # True if -shortscan, False if -shorts
    
    def get_put_recommendation(self, ticker, current_price, psar_distance):
        """
        Get deep ITM put recommendation for bearish position.
        
        Strategy:
        - Buy deep ITM put (delta > 0.97) = minimal time premium, moves ~1:1 with stock
        - To get delta 0.97+, need to be ~30-40% ITM
        - Optionally sell OTM put at support level to reduce cost (put debit spread)
        
        Expiration: 30-45 days typically best for SELL signals
        """
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            if not expirations:
                return None
            
            today = datetime.now()
            best_exp = None
            
            # Look for 30-45 day expiration (optimal for SELL signal duration)
            for exp_str in expirations:
                dte = (datetime.strptime(exp_str, '%Y-%m-%d') - today).days
                if 28 <= dte <= 50:
                    best_exp = exp_str
                    break
            
            # Fallback to anything 21+ days
            if not best_exp:
                for exp_str in expirations:
                    dte = (datetime.strptime(exp_str, '%Y-%m-%d') - today).days
                    if dte >= 21:
                        best_exp = exp_str
                        break
            
            if not best_exp:
                return None
            
            puts = stock.option_chain(best_exp).puts
            if puts.empty:
                return None
            
            dte = (datetime.strptime(best_exp, '%Y-%m-%d') - today).days
            
            # Find deep ITM put (delta > 0.97)
            # Delta 0.97+ requires ~30-40% ITM
            target_strike_min = current_price * 1.30  # At least 30% ITM for high delta
            target_strike_max = current_price * 1.50  # Up to 50% ITM
            
            itm_puts = puts[puts['strike'] >= target_strike_min]
            
            if itm_puts.empty:
                # Try less deep ITM (25%+)
                itm_puts = puts[puts['strike'] >= current_price * 1.25]
            
            if itm_puts.empty:
                # Fallback to any ITM
                itm_puts = puts[puts['strike'] > current_price]
                if itm_puts.empty:
                    return None
            
            # Get the put in our target range, or closest available
            deep_itm = itm_puts[itm_puts['strike'] <= target_strike_max]
            if deep_itm.empty:
                deep_itm = itm_puts.head(3)  # Take deepest available
            
            # Select put with best liquidity (highest open interest or volume)
            if 'openInterest' in deep_itm.columns and deep_itm['openInterest'].sum() > 0:
                best_put = deep_itm.loc[deep_itm['openInterest'].fillna(0).idxmax()]
            elif 'volume' in deep_itm.columns and deep_itm['volume'].sum() > 0:
                best_put = deep_itm.loc[deep_itm['volume'].fillna(0).idxmax()]
            else:
                best_put = deep_itm.iloc[0]
            
            long_strike = best_put['strike']
            long_bid = best_put['bid'] if best_put['bid'] > 0 else best_put['lastPrice']
            long_ask = best_put['ask'] if best_put['ask'] > 0 else best_put['lastPrice']
            long_mid = (long_bid + long_ask) / 2 if long_bid > 0 else long_ask
            
            # Calculate intrinsic vs extrinsic value
            intrinsic = max(0, long_strike - current_price)
            extrinsic = max(0, long_mid - intrinsic)
            extrinsic_pct = (extrinsic / long_mid) * 100 if long_mid > 0 else 0
            
            # ITM percentage
            itm_pct = ((long_strike - current_price) / current_price) * 100
            
            # Estimate delta based on ITM%
            # Rough: 30% ITM ≈ 0.95 delta, 40% ITM ≈ 0.97, 50%+ ≈ 0.99
            if itm_pct >= 50:
                est_delta = 0.99
            elif itm_pct >= 40:
                est_delta = 0.97
            elif itm_pct >= 30:
                est_delta = 0.95
            elif itm_pct >= 20:
                est_delta = 0.90
            else:
                est_delta = 0.80
            
            result = {
                'expiration': best_exp,
                'dte': dte,
                'long_strike': long_strike,
                'long_mid': long_mid,
                'long_bid': long_bid,
                'long_ask': long_ask,
                'intrinsic': intrinsic,
                'extrinsic': extrinsic,
                'extrinsic_pct': extrinsic_pct,
                'itm_pct': itm_pct,
                'est_delta': est_delta,
            }
            
            # Find potential short put for spread (at support / safe level)
            # Use 20-25% below current price for more cushion
            short_target = current_price * 0.75  # 25% below current
            short_min = current_price * 0.70     # Don't go below 30% OTM
            
            otm_puts = puts[(puts['strike'] < current_price * 0.85) & 
                           (puts['strike'] >= short_min)]
            
            if not otm_puts.empty:
                # Find put closest to our target (25% below)
                otm_puts = otm_puts.copy()
                otm_puts['dist_to_target'] = abs(otm_puts['strike'] - short_target)
                short_put = otm_puts.loc[otm_puts['dist_to_target'].idxmin()]
                
                short_strike = short_put['strike']
                short_bid = short_put['bid'] if short_put['bid'] > 0 else 0
                short_mid = (short_put['bid'] + short_put['ask']) / 2 if short_put['bid'] > 0 else short_put['ask'] / 2
                
                if short_bid > 0:  # Only include if there's a bid
                    result['short_strike'] = short_strike
                    result['short_mid'] = short_mid
                    result['short_bid'] = short_bid
                    result['spread_cost'] = long_mid - short_mid
                    result['spread_width'] = long_strike - short_strike
                    result['max_profit'] = result['spread_width'] - result['spread_cost']
                    result['downside_to_short'] = ((current_price - short_strike) / current_price) * 100
            
            return result
            
        except Exception as e:
            return None
    
    def get_short_score(self, result):
        """Calculate short score (higher = better short candidate)
        
        Scoring (max 100):
        - Deep SELL zone (PSAR < -5%): +25
        - Below 50MA: +15
        - Low momentum (1-4): +20
        - OBV confirms downtrend: +15
        - Negative EPS growth: +15
        - Short interest < 15%: +10 (not crowded)
        
        Penalties:
        - High short interest (>20%): -30 (squeeze risk)
        - High momentum (7+): -20 (improving)
        - RSI < 30: -15 (oversold bounce risk)
        """
        score = 0
        warnings = []
        
        # PSAR zone scoring
        psar_dist = result.get('psar_distance', 0)
        if psar_dist < -5:
            score += 25  # Deep sell
        elif psar_dist < -2:
            score += 15  # Weak/sell
        elif psar_dist < 2:
            score += 5   # Neutral
        else:
            score -= 20  # In buy zone - bad short
            warnings.append("In BUY zone")
        
        # Below 50MA
        if not result.get('above_ma50', True):
            score += 15
        else:
            warnings.append("Above 50MA")
        
        # Momentum (low = still deteriorating = good for shorts)
        momentum = result.get('psar_momentum', 5)
        if momentum <= 4:
            score += 20  # Still getting worse
        elif momentum >= 7:
            score -= 20  # Improving - could reverse
            warnings.append(f"High momentum ({momentum})")
        
        # OBV for downtrend confirmation
        obv = result.get('obv_status', 'NEUTRAL')
        if not result.get('psar_bullish', True):  # In sell zone
            if obv == 'CONFIRM':
                score += 15  # Volume confirms downtrend
            elif obv == 'DIVERGE':
                score -= 10  # Volume diverging - could reverse
                warnings.append("OBV diverging")
        
        # EPS growth (negative = fundamental weakness = good for shorts)
        eps = result.get('eps_growth')
        if eps is not None and eps < 0:
            score += 15
        elif eps is not None and eps > 20:
            score -= 10  # Strong growth - bad short
            warnings.append(f"EPS growth {eps:.0f}%")
        
        # Short interest analysis
        si = result.get('short_percent')
        if si is not None:
            if si > 25:
                score -= 30  # Major squeeze risk
                warnings.append(f"⚠️ HIGH SI {si:.1f}%")
            elif si > 15:
                score -= 15  # Elevated squeeze risk
                warnings.append(f"SI {si:.1f}%")
            elif si < 5:
                score += 10  # Not crowded
        
        # RSI (oversold = bounce risk)
        rsi = result.get('rsi', 50)
        if rsi < 30:
            score -= 15
            warnings.append(f"RSI oversold ({rsi:.0f})")
        
        return max(0, min(100, score)), warnings
    
    def get_squeeze_risk(self, result):
        """Determine squeeze risk level"""
        si = result.get('short_percent')
        if si is None:
            return 'UNKNOWN', '❓'
        elif si > 25:
            return 'HIGH', '🔴'
        elif si > 15:
            return 'MODERATE', '🟡'
        else:
            return 'LOW', '🟢'
    
    def get_obv_display(self, status):
        if status == 'CONFIRM':
            return '🟢'
        elif status == 'DIVERGE':
            return '🔴'
        else:
            return '🟡'
    
    def build_email_body(self):
        """Build HTML email body for shorts report"""
        
        # Calculate short scores for all results
        scored_results = []
        for r in self.all_results:
            score, warnings = self.get_short_score(r)
            r['short_score'] = score
            r['short_warnings'] = warnings
            scored_results.append(r)
        
        # Sort by short score (highest first)
        scored_results.sort(key=lambda x: x['short_score'], reverse=True)
        
        # Categorize
        good_shorts = [r for r in scored_results if r['short_score'] >= 50 and not r.get('psar_bullish', True)]
        risky_shorts = [r for r in scored_results if r.get('short_percent') and r.get('short_percent') > 20]
        in_sell_zone = [r for r in scored_results if not r.get('psar_bullish', True)]
        in_buy_zone = [r for r in scored_results if r.get('psar_bullish', True)]
        
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin: 15px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #4a4a4a; color: white; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .header { background-color: #d32f2f; color: white; padding: 15px; margin-bottom: 20px; }
                .section { margin: 20px 0; padding: 10px; background-color: #f5f5f5; border-radius: 5px; }
                .warning { background-color: #fff3cd; border: 1px solid #ffc107; padding: 10px; margin: 10px 0; }
                .good { background-color: #d4edda; }
                .bad { background-color: #f8d7da; }
                .score-high { color: #28a745; font-weight: bold; }
                .score-low { color: #dc3545; }
            </style>
        </head>
        <body>
        """
        
        # Header
        if self.is_market_scan:
            scan_type = "Market-Wide Short Scan"
            filter_parts = [f"${self.mc_filter}B+ market cap"]
            if self.include_adr:
                filter_parts.append("incl. ADRs")
            filter_desc = " | ".join(filter_parts)
        else:
            scan_type = "Short Watchlist Scan"
            filter_desc = "shorts.txt"
        
        html += f"""
        <div class="header">
            <h1>🐻 {scan_type}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Filters: {filter_desc} | {len(scored_results)} stocks analyzed</p>
        </div>
        """
        
        # Guide
        html += """
        <div class="section">
            <h3>📊 Short Score Guide</h3>
            <p><b>Score Components (max 100):</b></p>
            <ul>
                <li>Deep SELL zone (PSAR < -5%): +25 pts</li>
                <li>Below 50-day MA: +15 pts</li>
                <li>Low momentum (1-4): +20 pts</li>
                <li>OBV confirms downtrend: +15 pts</li>
                <li>Negative EPS growth: +15 pts</li>
                <li>Low short interest (<5%): +10 pts</li>
            </ul>
            <p><b>Penalties:</b></p>
            <ul>
                <li>🔴 High short interest (>25%): -30 pts (SQUEEZE RISK!)</li>
                <li>High momentum (7+): -20 pts (improving)</li>
                <li>RSI oversold (<30): -15 pts (bounce risk)</li>
            </ul>
            <p><b>Squeeze Risk:</b> 🟢 Low (<15%) | 🟡 Moderate (15-25%) | 🔴 High (>25%)</p>
        </div>
        """
        
        # Summary
        html += f"""
        <div class="section">
            <h3>📈 Summary</h3>
            <p>Total stocks scanned: <b>{len(scored_results)}</b></p>
            <p>🔴 In SELL zone: <b>{len(in_sell_zone)}</b></p>
            <p>🟢 In BUY zone (avoid shorting): <b>{len(in_buy_zone)}</b></p>
            <p>✅ Good short candidates (score ≥50): <b>{len(good_shorts)}</b></p>
            <p>⚠️ High squeeze risk (SI >20%): <b>{len(risky_shorts)}</b></p>
        </div>
        """
        
        # Squeeze risk warning
        if risky_shorts:
            html += """
            <div class="warning">
                <h3>⚠️ SQUEEZE RISK WARNING</h3>
                <p>The following stocks have HIGH short interest (>20%). Shorting these carries significant squeeze risk:</p>
                <ul>
            """
            for r in risky_shorts:
                si = r.get('short_percent', 0)
                html += f"<li><b>{r['ticker']}</b>: {si:.1f}% short interest</li>"
            html += """
                </ul>
            </div>
            """
        
        # Good Short Candidates
        if good_shorts:
            html += """
            <div class="section good">
                <h3>✅ Best Short Candidates (Score ≥50, In SELL Zone)</h3>
            """
            html += self._build_shorts_table(good_shorts)
            html += "</div>"
        
        # PUT OPTIONS SECTION - for stocks in SELL zone
        put_candidates = [r for r in scored_results if not r.get('psar_bullish', True) and r.get('short_score', 0) >= 40]
        if put_candidates:
            html += """
            <div class="section" style="background-color: #e8f4fd;">
                <h3>🎯 PUT OPTIONS STRATEGY</h3>
                <p style="font-size:11px;"><b>Strategy:</b> Buy deep ITM put (delta ~0.97+) for minimal time premium. 
                Optionally sell OTM put to create a debit spread and reduce cost.</p>
                <p style="font-size:11px;"><b>Expiration:</b> 30-45 days optimal for SELL signal duration</p>
            """
            html += self._build_puts_table(put_candidates[:15])
            html += "</div>"
        
        # All Results
        html += """
        <div class="section">
            <h3>📋 All Scanned Stocks</h3>
        """
        html += self._build_shorts_table(scored_results)
        html += "</div>"
        
        # Stocks to Avoid Shorting (in BUY zone)
        if in_buy_zone:
            html += """
            <div class="section bad">
                <h3>🚫 Avoid Shorting (In BUY Zone)</h3>
                <p>These stocks are in uptrends - shorting them is risky:</p>
            """
            html += self._build_shorts_table(in_buy_zone)
            html += "</div>"
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def _build_shorts_table(self, results):
        """Build HTML table for short candidates"""
        html = """
        <table>
            <tr>
                <th>Ticker</th>
                <th>Company</th>
                <th>Zone</th>
                <th>Score</th>
                <th>Price</th>
                <th>PSAR %</th>
                <th>Mom</th>
                <th>SI %</th>
                <th>Squeeze</th>
                <th>OBV</th>
                <th>RSI</th>
                <th>50MA</th>
                <th>Warnings</th>
            </tr>
        """
        
        for r in results:
            zone = r.get('psar_zone', 'UNKNOWN')
            score = r.get('short_score', 0)
            warnings = r.get('short_warnings', [])
            squeeze_risk, squeeze_icon = self.get_squeeze_risk(r)
            obv_display = self.get_obv_display(r.get('obv_status', 'NEUTRAL'))
            
            # Score color
            if score >= 50:
                score_class = 'score-high'
            else:
                score_class = 'score-low'
            
            # Short interest
            si = r.get('short_percent')
            si_str = f"{si:.1f}%" if si else "N/A"
            
            # Days to cover
            days = r.get('short_ratio')
            days_str = f"{days:.1f}" if days else ""
            
            # 50MA
            ma50 = '↓' if not r.get('above_ma50', True) else '↑'
            
            html += f"""
            <tr>
                <td><b>{r['ticker']}</b></td>
                <td>{r.get('company', '')[:20]}</td>
                <td>{zone}</td>
                <td class="{score_class}">{score}</td>
                <td>${r.get('price', 0):.2f}</td>
                <td>{r.get('psar_distance', 0):+.1f}%</td>
                <td>{r.get('psar_momentum', 5)}</td>
                <td>{si_str}</td>
                <td>{squeeze_icon}</td>
                <td>{obv_display}</td>
                <td>{r.get('rsi', 50):.0f}</td>
                <td>{ma50}</td>
                <td style="font-size: 11px;">{', '.join(warnings) if warnings else '✓'}</td>
            </tr>
            """
        
        html += "</table>"
        return html
    
    def _build_puts_table(self, results):
        """Build HTML table for put option recommendations"""
        html = """
        <table>
            <tr>
                <th>Ticker</th>
                <th>Price</th>
                <th>Score</th>
                <th>Exp (DTE)</th>
                <th>Buy Put</th>
                <th>ITM%</th>
                <th>Cost</th>
                <th>Extr%</th>
                <th>Sell Put</th>
                <th>Spread</th>
                <th>Net Cost</th>
                <th>Max Profit</th>
            </tr>
        """
        
        for r in results:
            put = self.get_put_recommendation(r['ticker'], r['price'], r.get('psar_distance', 0))
            score = r.get('short_score', 0)
            
            if put:
                # Format buy put info
                buy_strike = f"${put['long_strike']:.0f}"
                itm_pct = put['itm_pct']
                itm_str = f"{itm_pct:.0f}%"
                cost = f"${put['long_mid']:.2f}"
                extr_pct = put['extrinsic_pct']
                extr_str = f"{extr_pct:.1f}%"
                exp_str = f"{put['expiration']} ({put['dte']}d)"
                
                # ITM% color - green if deep enough (30%+), yellow if ok (20-30%), red if shallow
                if itm_pct >= 30:
                    itm_color = '#28a745'  # Green - deep ITM, high delta
                elif itm_pct >= 20:
                    itm_color = '#ffc107'  # Yellow - moderate
                else:
                    itm_color = '#dc3545'  # Red - too shallow, low delta
                
                # Extrinsic color - green if low (<5%), yellow if ok (<10%), red if high
                if extr_pct < 5:
                    extr_color = '#28a745'  # Green - minimal time premium
                elif extr_pct < 10:
                    extr_color = '#ffc107'  # Yellow
                else:
                    extr_color = '#dc3545'  # Red - too much premium
                
                # Format sell put info if available
                if 'short_strike' in put and put.get('short_bid', 0) > 0:
                    sell_strike = f"${put['short_strike']:.0f}"
                    spread_width = f"${put['spread_width']:.0f}"
                    net_cost = f"${put['spread_cost']:.2f}"
                    max_profit = f"${put['max_profit']:.2f}"
                else:
                    sell_strike = "-"
                    spread_width = "-"
                    net_cost = cost
                    max_profit = "unlimited"
                
                html += f"""
                <tr>
                    <td><b>{r['ticker']}</b></td>
                    <td>${r['price']:.2f}</td>
                    <td>{score}</td>
                    <td>{exp_str}</td>
                    <td><b>{buy_strike}</b></td>
                    <td style="color:{itm_color};">{itm_str}</td>
                    <td>{cost}</td>
                    <td style="color:{extr_color};">{extr_str}</td>
                    <td>{sell_strike}</td>
                    <td>{spread_width}</td>
                    <td><b>{net_cost}</b></td>
                    <td>{max_profit}</td>
                </tr>
                """
            else:
                html += f"""
                <tr>
                    <td><b>{r['ticker']}</b></td>
                    <td>${r['price']:.2f}</td>
                    <td>{score}</td>
                    <td colspan="9" style="color:#999;">No options available</td>
                </tr>
                """
        
        html += "</table>"
        
        # Add legend
        html += """
        <p style="font-size:10px;color:#666;margin-top:10px;">
        <b>Legend:</b> ITM% 🟢 30%+ (delta ~0.97) | 🟡 20-30% | 🔴 <20% (low delta) | 
        Extr% 🟢 <5% ideal | 🟡 5-10% | 🔴 >10% (too much premium) |
        Sell Put = ~25% below price for cushion
        </p>
        """
        
        return html
    
    def send_email(self, additional_email=None):
        """Send the shorts report via email"""
        
        # Get email config
        gmail_email = os.environ.get('GMAIL_EMAIL')
        gmail_password = os.environ.get('GMAIL_PASSWORD')
        recipient = os.environ.get('RECIPIENT_EMAIL', gmail_email)
        
        if not gmail_email or not gmail_password:
            print("⚠️ Email credentials not configured")
            print("Set GMAIL_EMAIL and GMAIL_PASSWORD environment variables")
            return False
        
        # Build subject
        good_shorts = len([r for r in self.all_results if r.get('short_score', 0) >= 50 and not r.get('psar_bullish', True)])
        high_risk = len([r for r in self.all_results if r.get('short_percent') and r.get('short_percent') > 20])
        
        if self.is_market_scan:
            subject = f"🐻 Market Short Scan: {good_shorts} Candidates, {high_risk} Squeeze Risk"
        else:
            subject = f"🐻 Short Watchlist: {good_shorts} Good, {high_risk} Squeeze Risk"
        
        # Build message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = gmail_email
        
        recipients = [recipient]
        if additional_email:
            recipients.append(additional_email)
        msg['To'] = ', '.join(recipients)
        
        # Attach HTML
        html_body = self.build_email_body()
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(gmail_email, gmail_password)
                server.sendmail(gmail_email, recipients, msg.as_string())
            
            print(f"\n✓ Email sent to: {', '.join(recipients)}")
            print(f"  Good shorts: {good_shorts}, Squeeze risk: {high_risk}")
            return True
            
        except Exception as e:
            print(f"\n✗ Failed to send email: {e}")
            return False
