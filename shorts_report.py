"""
Shorts Report Generator
Analyzes potential short candidates with squeeze risk warnings
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

class ShortsReport:
    def __init__(self, scan_results):
        self.scan_results = scan_results
        self.all_results = scan_results['all_results']
    
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
        html += f"""
        <div class="header">
            <h1>🐻 Short Candidates Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
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
        
        subject = f"🐻 Short Candidates: {good_shorts} Good, {high_risk} Squeeze Risk"
        
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
