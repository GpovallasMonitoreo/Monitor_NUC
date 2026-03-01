import os
import aiohttp
import io
import discord
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

class DriveService:
    def __init__(self):
        self.creds_path = os.path.join(os.getcwd(), 'credentials.json')
        self.folder_id = os.getenv("DRIVE_FOLDER_ID")
        self.service = self._authenticate()

    def _authenticate(self):
        try:
            if not os.path.exists(self.creds_path): return None
            scopes = ['https://www.googleapis.com/auth/drive.file']
            creds = service_account.Credentials.from_service_account_file(self.creds_path, scopes=scopes)
            return build('drive', 'v3', credentials=creds)
        except: return None

    async def subir_imagen_ticket(self, attachment: discord.Attachment, ticket_id: str, tipo="incidencia"):
        if not self.service or not self.folder_id: return attachment.url
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200: return attachment.url
                    data = await resp.read()

            file_metadata = {'name': f"{ticket_id}_{tipo}.jpg", 'parents': [self.folder_id]}
            media = MediaIoBaseUpload(io.BytesIO(data), mimetype='image/jpeg', resumable=True)
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            
            self.service.permissions().create(fileId=file.get('id'), body={'type': 'anyone', 'role': 'reader'}).execute()
            return file.get('webViewLink')
        except: return attachment.url
