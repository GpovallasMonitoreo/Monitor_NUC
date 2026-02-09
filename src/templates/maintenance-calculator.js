// Cálculos reales para mantenimientos
class MaintenanceCalculator {
    constructor() {
        // Tarifas predefinidas por hora según tipo de técnico
        this.hourlyRates = {
            'tecnico_regular': 120,    // $120/hora
            'tecnico_especializado': 180, // $180/hora
            'ingeniero': 250,          // $250/hora
            'contratista': 150         // $150/hora
        };
        
        // Costos de materiales predefinidos
        this.materialCosts = {
            'dioxido_titanio': 45,     // $45/kg
            'modulo_led': 250,         // $250/unidad
            'fuente_poder': 180,       // $180/unidad
            'cable_fat': 45,           // $45/metro
            'novastar_mctrl300': 350,  // $350/unidad
            'ventilador': 85,          // $85/unidad
            'tarjeta_control': 120     // $120/unidad
        };
        
        // Costos adicionales
        this.additionalCosts = {
            'traslado': 150,           // $150 por traslado
            'herramienta_especial': 75, // $75 por uso
            'material_consumible': 30   // $30 base
        };
    }
    
    calculateMaintenanceCost(data) {
        const {
            hours,
            technicianType = 'tecnico_regular',
            materials = [],
            additionalServices = [],
            travelDistance = 0
        } = data;
        
        let total = 0;
        
        // 1. Costo de mano de obra
        const hourlyRate = this.hourlyRates[technicianType] || this.hourlyRates.tecnico_regular;
        total += hours * hourlyRate;
        
        // 2. Costo de materiales
        materials.forEach(material => {
            const unitCost = this.materialCosts[material.type] || 0;
            total += unitCost * (material.quantity || 1);
        });
        
        // 3. Costos adicionales
        additionalServices.forEach(service => {
            total += this.additionalCosts[service] || 0;
        });
        
        // 4. Costo de traslado (si aplica)
        if (travelDistance > 0) {
            const travelCost = Math.ceil(travelDistance / 50) * this.additionalCosts.traslado;
            total += travelCost;
        }
        
        return {
            laborCost: hours * hourlyRate,
            materialsCost: materials.reduce((sum, m) => {
                return sum + ((this.materialCosts[m.type] || 0) * (m.quantity || 1));
            }, 0),
            additionalCosts: additionalServices.reduce((sum, s) => {
                return sum + (this.additionalCosts[s] || 0);
            }, 0),
            travelCost: travelDistance > 0 ? 
                Math.ceil(travelDistance / 50) * this.additionalCosts.traslado : 0,
            totalCost: total,
            hourlyRate: hourlyRate
        };
    }
    
    calculateROIImpact(screenData, maintenanceCost) {
        const monthlyRevenue = screenData.ingresos_mensuales || 0;
        const monthlyExpenses = screenData.gastos_mensuales || 0;
        const capex = this.calculateCapexTotal(screenData);
        
        const monthlyProfit = monthlyRevenue - monthlyExpenses;
        const roiBefore = capex / monthlyProfit;
        
        // Ajustar ROI considerando el costo de mantenimiento
        const adjustedCapex = capex + maintenanceCost;
        const roiAfter = adjustedCapex / monthlyProfit;
        
        return {
            roiBefore: roiBefore.toFixed(1),
            roiAfter: roiAfter.toFixed(1),
            impact: ((roiAfter - roiBefore) / roiBefore * 100).toFixed(1),
            monthsToRecover: (maintenanceCost / monthlyProfit).toFixed(1),
            recommendation: this.getROIRecommendation(roiAfter)
        };
    }
    
    calculateCapexTotal(screenData) {
        try {
            const capex = screenData.capex_data ? JSON.parse(screenData.capex_data) : {};
            return Object.values(capex).reduce((sum, val) => sum + (Number(val) || 0), 0);
        } catch (error) {
            return 0;
        }
    }
    
    getROIRecommendation(roi) {
        if (roi <= 12) return 'Excelente - Mantenimiento altamente rentable';
        if (roi <= 18) return 'Bueno - Impacto positivo en ROI';
        if (roi <= 24) return 'Aceptable - Dentro de parámetros esperados';
        if (roi <= 36) return 'Regular - Evaluar necesidad del mantenimiento';
        return 'Crítico - Reconsiderar la inversión';
    }
    
    // Método para guardar mantenimiento en Supabase
    async saveMaintenanceToDB(maintenanceData) {
        try {
            if (!window.supabaseClient) {
                throw new Error('Supabase no está inicializado');
            }
            
            // Calcular costo total
            const costBreakdown = this.calculateMaintenanceCost({
                hours: maintenanceData.horas,
                technicianType: maintenanceData.tipo_tecnico,
                materials: maintenanceData.materiales || [],
                additionalServices: maintenanceData.servicios_adicionales || [],
                travelDistance: maintenanceData.distancia_traslado || 0
            });
            
            const maintenanceRecord = {
                pantalla_id: maintenanceData.pantalla_id,
                fecha: maintenanceData.fecha || new Date().toISOString().split('T')[0],
                tipo: maintenanceData.tipo || 'preventivo',
                horas: maintenanceData.horas,
                tipo_tecnico: maintenanceData.tipo_tecnico,
                descripcion: maintenanceData.descripcion,
                materiales: JSON.stringify(maintenanceData.materiales || []),
                servicios_adicionales: JSON.stringify(maintenanceData.servicios_adicionales || []),
                distancia_traslado: maintenanceData.distancia_traslado || 0,
                costo_mano_obra: costBreakdown.laborCost,
                costo_materiales: costBreakdown.materialsCost,
                costo_adicional: costBreakdown.additionalCosts + costBreakdown.travelCost,
                costo_total: costBreakdown.totalCost,
                tasa_horaria: costBreakdown.hourlyRate,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };
            
            const { data, error } = await window.supabaseClient
                .from('mantenimientos')
                .insert([maintenanceRecord])
                .select()
                .single();
                
            if (error) throw error;
            
            // Actualizar ROI de la pantalla
            await this.updateScreenROI(maintenanceData.pantalla_id, costBreakdown.totalCost);
            
            return {
                success: true,
                data: data,
                costBreakdown: costBreakdown
            };
            
        } catch (error) {
            console.error('Error guardando mantenimiento:', error);
            throw error;
        }
    }
    
    async updateScreenROI(screenId, maintenanceCost) {
        try {
            // Obtener pantalla actual
            const { data: screen } = await window.supabaseClient
                .from('pantallas')
                .select('*')
                .eq('id', screenId)
                .single();
                
            if (!screen) return;
            
            // Calcular nuevo ROI
            const capex = this.calculateCapexTotal(screen);
            const monthlyProfit = (screen.ingresos_mensuales || 0) - (screen.gastos_mensuales || 0);
            
            if (monthlyProfit <= 0) return;
            
            const adjustedCapex = capex + maintenanceCost;
            const newROI = adjustedCapex / monthlyProfit;
            
            // Actualizar pantalla
            await window.supabaseClient
                .from('pantallas')
                .update({ 
                    roi: newROI,
                    updated_at: new Date().toISOString()
                })
                .eq('id', screenId);
                
        } catch (error) {
            console.error('Error actualizando ROI:', error);
        }
    }
}

// Exportar para uso global
window.MaintenanceCalculator = MaintenanceCalculator;
