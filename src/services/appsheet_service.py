@app.route('/api/debug/appsheet')
def debug_appsheet():
    """Página de debug para AppSheet"""
    from src.services.appsheet_service import AppSheetService
    
    service = AppSheetService()
    status = service.get_status_info()
    
    # Probar conexión manualmente
    test_results = []
    
    # Probar tablas comunes
    test_tables = ["devices", "device_history", "latency_history", "alerts"]
    
    for table in test_tables:
        try:
            url = f"https://api.appsheet.com/api/v2/apps/{service.app_id}/tables/{table}/Action"
            payload = {"Action": "Find", "Properties": {"Locale": "es-MX", "Top": 1}}
            
            response = requests.post(
                url,
                headers=service.headers,
                json=payload,
                timeout=10
            )
            
            test_results.append({
                "table": table,
                "status_code": response.status_code,
                "exists": response.status_code == 200
            })
            
        except Exception as e:
            test_results.append({
                "table": table,
                "error": str(e),
                "exists": False
            })
    
    return jsonify({
        "status": status,
        "table_tests": test_results,
        "app_id_full": service.app_id if request.args.get('show_full') else "hidden",
        "api_key_preview": service.api_key[:5] + "..." if service.api_key else "none"
    })
