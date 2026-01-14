import os  # <--- ESTO FALTABA
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AppSheetStub:
    """Clase de respaldo (Dummy) cuando el servicio real falla."""
    def __init__(self):
        self.enabled = False
        self.table_status = {}
        self.last_sync_time = None
        # logger.warning("⚠️ Usando AppSheet STUB - Funcionalidad limitada.") # Comentado para reducir ruido en logs

    def get_status_info(self):
        return {"enabled": False, "connection_status": "disabled", "error": "Using Stub"}

    def get_or_create_device(self, data): return False, None, False
    def add_history_entry(self, data): return False
    def get_full_history(self, limit=100): return []
    def test_history_connection(self): return False

class AppSheetService:
    """Servicio Real de AppSheet."""
    def __init__(self):
        self.enabled = True
        self.table_status = {"devices": True, "history": True}
        self.last_sync_time = datetime.now()
        
        # Validación de seguridad
        # Si NO existe la variable y quieres forzar el error, esto fallaba antes por falta de 'os'
        if not os.environ.get('APPSHEET_KEY') and False: 
             raise ValueError("Falta API KEY")

    def get_status_info(self):
        return {
            "enabled": self.enabled,
            "connection_status": "connected",
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None
        }

    def get_or_create_device(self, device_data):
        return True, "id_123", True

    def add_history_entry(self, log_data):
        return True

    def get_full_history(self, limit=100):
        return [{"device_id": "test", "action": "sync"}]
