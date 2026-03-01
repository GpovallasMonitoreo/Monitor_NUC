import os
import aiohttp
import io
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

class DriveService:
    def __init__(self):
        # Buscamos las credenciales en la raíz del proyecto
        self.creds_path = os.path.join(os.getcwd(), 'credentials.json')
        # Obtenemos el ID de la carpeta desde settings o env
        self.folder_id = os.getenv("DRIVE_FOLDER_ID")
        self.service = self._authenticate()

    def _authenticate(self):
        try:
            if not os.path.exists(self.creds_path):
                logger.error(f"❌ No se encontró el archivo {self.creds_path}")
                return None
                
            scopes = ['https://www.googleapis.com/auth/drive.file']
            creds = service_account.Credentials.from_service_account_file(
                self.creds_path, scopes=scopes
            )
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"❌ Error de autenticación Drive: {e}")
            return None

    async def subir_imagen_ticket(self, attachment: discord.Attachment, ticket_id: str, tipo="incidencia"):
        """
        Descarga la foto de Discord y la sube a la carpeta compartida de Drive.
        """
        if not self.service or not self.folder_id:
            logger.warning("⚠️ Servicio de Drive no disponible. Usando URL original.")
            return attachment.url

        try:
            # 1. Descargar imagen de Discord
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200: return attachment.url
                    data = await resp.read()

            # 2. Preparar subida
            file_metadata = {
                'name': f"{ticket_id}_{tipo}.jpg",
                'parents': [self.folder_id]
            }
            media = MediaIoBaseUpload(io.BytesIO(data), mimetype='image/jpeg', resumable=True)

            # 3. Ejecutar subida
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()

            # 4. Hacer el link público (solo lectura) para que se vea en Supabase/AppSheet
            self.service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            return file.get('webViewLink')

        except Exception as e:
            logger.error(f"🔥 Error subiendo a Drive: {e}")
            return attachment.url
