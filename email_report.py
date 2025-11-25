def send_email(self, to_email=None):
    """Send the email report"""
    import os
    
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
