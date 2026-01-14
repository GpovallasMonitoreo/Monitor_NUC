# src/services/appsheet_service.py - VERSIÓN MINIMALISTA SEGURA
import os
import requests
import json
import hashlib
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AppSheetService:
    """Servicio AppSheet simplificado"""
    
    def __init__(self):
        self.api_key = os.getenv('APPSHEET_API_KEY', '').strip()
        self.app_id = os.getenv('APPSHEET_APP_ID', '').strip()
        enabled = os.getenv('APPSHEET_ENABLED', 'true').strip().lower()
        
        self.enabled = enabled in ['true', '1', 'yes', 'on'] and self.api_key and self.app_id
        self.base_url = "https://api.appsheet.com/api/v2"
        self.headers = {'Content-Type': 'application/json', 'ApplicationAccessKey': self.api_key}
        
        logger.info(f"AppSheet Service: {'ENABLED' if self.enabled else 'DISABLED'}")
    
    def _make_request(self, table, action, rows=None):
        if not self.enabled:
            return None
        
        try:
            payload = {"Action": action, "Properties": {"Locale": "es-MX"}}
            if rows:
                payload["Rows"] = rows
            
            url = f"{self.base_url}/apps/{self.app_id}/tables/{table}/Action"
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                try:
                    return response.json()
                except:
                    return {"status": "success"}
            
            logger.error(f"AppSheet error {response.status_code}: {response.text[:100]}")
            return None
            
        except Exception as e:
            logger.error(f"AppSheet exception: {e}")
            return None
    
    def add_history_entry(self, data):
        """Método básico para probar"""
        if not self.enabled:
            return False
        
        test_row = {
            "history_id": str(uuid.uuid4()),
            "device_id": "TEST_" + str(uuid.uuid4())[:8],
            "action": data.get('action', 'test'),
            "desc": data.get('desc', 'Test entry'),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        result = self._make_request("device_history", "Add", [test_row])
        return result is not None
    
    def get_status_info(self):
        return {
            "enabled": self.enabled,
            "has_credentials": bool(self.api_key and self.app_id),
            "app_id_preview": self.app_id[:8] + "..." if self.app_id else "None"
        }
