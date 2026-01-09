import os
import smtplib
import logging
import threading
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo # Fallback

# Configuración de Zona Horaria
try:
    TZ_CDMX = ZoneInfo("America/Mexico_City")
except:
    TZ_CDMX = ZoneInfo("UTC")

class AlertService:
    def __init__(self, app):
        self.app = app
        # Recuperamos configuración de variables de entorno
        self.sender = os.getenv('EMAIL_SENDER_1') or os.getenv('MAIL_USERNAME')
        self.password = os.getenv('EMAIL_PASSWORD_1') or os.getenv('MAIL_PASSWORD')
        self.server = 'smtp.gmail.com'
        self.port = 587
        # Lista de destinatarios
        recipients_str = os.getenv('MAIL_RECIPIENTS', 'incidencias.vallas@gpovallas.com')
        self.recipients = [r.strip() for r in recipients_str.split(',')]

    def _send_async(self, msg):
        """Envía el correo en un hilo separado para no bloquear la API."""
        def send_task():
            if not self.sender or not self.password:
                logging.warning("⚠️ No hay credenciales de correo configuradas.")
                return
            try:
                with smtplib.SMTP(self.server, self.port) as s:
                    s.starttls()
                    s.login(self.sender, self.password)
                    s.send_message(msg)
                    logging.info(f"✅ Correo enviado a {self.recipients}")
            except Exception as e:
                logging.error(f"🔥 Error SMTP: {e}")

        threading.Thread(target=send_task).start()

    def send_offline_alert(self, pc_name, last_info):
        """Genera y envía el correo de ALERTA DE DESCONEXIÓN (Rojo)."""
        msg = MIMEMultipart()
        msg['From'] = f"Argos Monitor <{self.sender}>"
        msg['To'] = ", ".join(self.recipients)
        msg['Subject'] = f"🔥 ALERTA: {pc_name} Desconectado"

        last_ip = last_info.get('public_ip', 'N/A')
        last_local = last_info.get('ip', 'N/A')
        hora = datetime.now(TZ_CDMX).strftime('%d/%m/%Y %H:%M:%S')

        body = f"""
        <!DOCTYPE html><html lang="es"><body style="font-family: Arial, sans-serif;">
        <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
        <div style="background-color: #d9534f; color: white; padding: 20px; text-align: center;"><h1>ALERTA DE DESCONEXIÓN</h1></div>
        <div style="padding: 20px;"><p>Se ha detectado que el equipo <strong>{pc_name}</strong> ha perdido conexión.</p>
        <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
        <tr><td style="padding: 8px; border: 1px solid #ddd; bg-color: #f9f9f9;">IP Pública:</td><td style="padding: 8px; border: 1px solid #ddd;">{last_ip}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd; bg-color: #f9f9f9;">IP Local:</td><td style="padding: 8px; border: 1px solid #ddd;">{last_local}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd; bg-color: #f9f9f9;">Hora Detección:</td><td style="padding: 8px; border: 1px solid #ddd;">{hora} (CDMX)</td></tr>
        </table></div>
        <div style="background-color: #f0f0f0; color: #777; padding: 15px; font-size: 12px; text-align: center;"><p>Argos System</p></div>
        </div></body></html>"""
        
        msg.attach(MIMEText(body, 'html'))
        self._send_async(msg)

    def send_online_alert(self, pc_name, current_info):
        """Genera y envía el correo de RECONEXIÓN (Verde)."""
        msg = MIMEMultipart()
        msg['From'] = f"Argos Monitor <{self.sender}>"
        msg['To'] = ", ".join(self.recipients)
        msg['Subject'] = f"✅ RESTAURADO: {pc_name} Online"

        ip = current_info.get('public_ip', 'N/A')
        local = current_info.get('ip', 'N/A')
        hora = datetime.now(TZ_CDMX).strftime('%d/%m/%Y %H:%M:%S')

        body = f"""
        <!DOCTYPE html><html lang="es"><body style="font-family: Arial, sans-serif;">
        <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
        <div style="background-color: #5cb85c; color: white; padding: 20px; text-align: center;"><h1>CONEXIÓN RESTABLECIDA</h1></div>
        <div style="padding: 20px;"><p>El equipo <strong>{pc_name}</strong> está operativo nuevamente.</p>
        <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
        <tr><td style="padding: 8px; border: 1px solid #ddd; bg-color: #f9f9f9;">IP Pública:</td><td style="padding: 8px; border: 1px solid #ddd;">{ip}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd; bg-color: #f9f9f9;">IP Local:</td><td style="padding: 8px; border: 1px solid #ddd;">{local}</td></tr>
        <tr><td style="padding: 8px; border: 1px solid #ddd; bg-color: #f9f9f9;">Hora Reconexión:</td><td style="padding: 8px; border: 1px solid #ddd;">{hora} (CDMX)</td></tr>
        </table></div>
        <div style="background-color: #f0f0f0; color: #777; padding: 15px; font-size: 12px; text-align: center;"><p>Argos System</p></div>
        </div></body></html>"""
        
        msg.attach(MIMEText(body, 'html'))
        self._send_async(msg)

    def send_inventory_report(self, data):
        # Lógica para reportes de inventario si la necesitas
        pass
