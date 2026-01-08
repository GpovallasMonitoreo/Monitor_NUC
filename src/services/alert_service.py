import smtplib
import os
import threading
from email.message import EmailMessage
from flask import render_template

class AlertService:
    def __init__(self, app):
        self.app = app
        self.username = os.getenv('MAIL_USERNAME')
        self.password = os.getenv('MAIL_PASSWORD')
        self.server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        self.port = int(os.getenv('MAIL_PORT', 587))
        self.recipients = os.getenv('MAIL_RECIPIENTS', '').split(',')

    def send_inventory_report(self, log):
        subject = f"📝 REGISTRO DE CAMBIO: {log['pc_name']}"
        content = f"Actividad: {log['activity']}\nTecnico: {log['tech_name']}\nNotas: {log['notes']}\nFecha: {log['timestamp']}"
        self._send_async(subject, content)

    def check_and_alert(self, device, prev_status):
        if prev_status == 'online' and device.status == 'critical':
            self._send_async(f"⚠️ FALLA: {device.pc_name}", f"El equipo {device.pc_name} ha entrado en estado CRÍTICO.")

    def _send_async(self, subject, content):
        if not self.username: return
        threading.Thread(target=self._execute_send, args=(subject, content)).start()

    def _execute_send(self, subject, content):
        try:
            msg = EmailMessage()
            msg.set_content(content)
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = ", ".join(self.recipients)
            with smtplib.SMTP(self.server, self.port) as s:
                s.starttls()
                s.login(self.username, self.password)
                s.send_message(msg)
        except Exception as e: print(f"Error SMTP: {e}")