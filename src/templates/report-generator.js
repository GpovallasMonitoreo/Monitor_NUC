// Generador de reportes PDF reales
class ReportGenerator {
    constructor() {
        this.apiKey = SUPABASE_ANON_KEY;
        this.apiUrl = SUPABASE_URL;
    }

    async generateScreenReport(screenId, options = {}) {
        try {
            console.log('📊 Generando reporte para pantalla:', screenId);
            
            // Obtener datos de la pantalla
            const screen = await this.getScreenData(screenId);
            if (!screen) {
                throw new Error('Pantalla no encontrada');
            }
            
            // Obtener mantenimientos
            const maintenances = await this.getScreenMaintenances(screenId);
            
            // Obtener gastos
            const expenses = await this.getScreenExpenses(screenId);
            
            // Generar PDF
            const pdfData = this.createPDFData(screen, maintenances, expenses, options);
            
            // Enviar a API de generación de PDF (implementar según tu backend)
            const pdfUrl = await this.generatePDF(pdfData);
            
            return {
                success: true,
                pdfUrl: pdfUrl,
                screen: screen,
                stats: this.calculateStats(screen, maintenances, expenses)
            };
            
        } catch (error) {
            console.error('Error generando reporte:', error);
            throw error;
        }
    }

    async getScreenData(screenId) {
        const { data, error } = await window.supabaseClient
            .from('pantallas')
            .select('*')
            .eq('id', screenId)
            .single();
            
        if (error) throw error;
        return data;
    }

    async getScreenMaintenances(screenId) {
        const { data, error } = await window.supabaseClient
            .from('mantenimientos')
            .select('*')
            .eq('pantalla_id', screenId)
            .order('fecha', { ascending: false });
            
        if (error) throw error;
        return data || [];
    }

    async getScreenExpenses(screenId) {
        const { data, error } = await window.supabaseClient
            .from('gastos_mensuales')
            .select('*')
            .eq('pantalla_id', screenId)
            .order('mes', { ascending: false });
            
        if (error) throw error;
        return data || [];
    }

    calculateStats(screen, maintenances, expenses) {
        // Calcular estadísticas avanzadas
        const totalMaintenanceCost = maintenances.reduce((sum, m) => sum + (m.costo_total || 0), 0);
        const avgMaintenanceCost = maintenances.length > 0 ? totalMaintenanceCost / maintenances.length : 0;
        
        const totalMonthlyExpenses = expenses.reduce((sum, e) => sum + (e.total_mensual || 0), 0);
        const avgMonthlyExpenses = expenses.length > 0 ? totalMonthlyExpenses / expenses.length : 0;
        
        const roiMonths = screen.roi || 0;
        const profitMargin = screen.ingresos_mensuales > 0 
            ? ((screen.ingresos_mensuales - screen.gastos_mensuales) / screen.ingresos_mensuales) * 100 
            : 0;
        
        return {
            totalMaintenanceCost,
            avgMaintenanceCost,
            totalMonthlyExpenses,
            avgMonthlyExpenses,
            roiMonths,
            profitMargin: profitMargin.toFixed(1),
            uptime: screen.uptime || '0%',
            daysOnline: this.calculateDaysOnline(screen, maintenances)
        };
    }

    calculateDaysOnline(screen, maintenances) {
        // Calcular días en línea basado en mantenimientos
        const installDate = new Date(screen.fecha_instalacion || screen.created_at);
        const today = new Date();
        const totalDays = Math.floor((today - installDate) / (1000 * 60 * 60 * 24));
        
        // Calcular días de mantenimiento
        const maintenanceDays = maintenances.reduce((sum, m) => {
            const duration = m.duracion_horas || 0;
            return sum + (duration / 24);
        }, 0);
        
        return Math.floor(totalDays - maintenanceDays);
    }

    createPDFData(screen, maintenances, expenses, options) {
        const reportDate = new Date().toLocaleDateString('es-MX', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });

        return {
            header: {
                title: `REPORTE DE PANTALLA: ${screen.nombre}`,
                subtitle: `ID: ${screen.id} | Ubicación: ${screen.ubicacion}`,
                date: reportDate,
                logo: 'https://your-logo-url.com/logo.png'
            },
            
            executiveSummary: {
                roi: `${screen.roi || 0} meses`,
                monthlyRevenue: `$${(screen.ingresos_mensuales || 0).toLocaleString()}`,
                monthlyExpenses: `$${(screen.gastos_mensuales || 0).toLocaleString()}`,
                netProfit: `$${((screen.ingresos_mensuales || 0) - (screen.gastos_mensuales || 0)).toLocaleString()}`,
                profitMargin: `${(((screen.ingresos_mensuales || 0) - (screen.gastos_mensuales || 0)) / (screen.ingresos_mensuales || 1) * 100).toFixed(1)}%`,
                uptime: screen.uptime || '0%',
                status: screen.estado || 'desconocido'
            },
            
            financialAnalysis: {
                capex: this.calculateCapex(screen),
                opex: {
                    monthly: screen.gastos_mensuales || 0,
                    annual: (screen.gastos_mensuales || 0) * 12
                },
                roiAnalysis: this.generateROIAnalysis(screen),
                breakEvenPoint: this.calculateBreakEven(screen)
            },
            
            maintenanceHistory: {
                totalMaintenances: maintenances.length,
                preventive: maintenances.filter(m => m.tipo === 'preventivo').length,
                corrective: maintenances.filter(m => m.tipo === 'correctivo').length,
                totalCost: maintenances.reduce((sum, m) => sum + (m.costo_total || 0), 0),
                avgCostPerMaintenance: maintenances.length > 0 
                    ? maintenances.reduce((sum, m) => sum + (m.costo_total || 0), 0) / maintenances.length 
                    : 0,
                details: maintenances.map(m => ({
                    date: m.fecha,
                    type: m.tipo,
                    hours: m.horas || 0,
                    cost: m.costo_total || 0,
                    description: m.descripcion || ''
                }))
            },
            
            strategicRecommendations: this.generateRecommendations(screen, maintenances),
            
            charts: {
                revenueTrend: this.generateRevenueTrendData(expenses),
                maintenanceFrequency: this.generateMaintenanceFrequencyData(maintenances),
                costBreakdown: this.generateCostBreakdownData(screen, expenses)
            },
            
            footer: {
                generatedBy: 'Sistema Argos DOOH',
                contact: 'contacto@argosdooh.com',
                disclaimer: 'Información confidencial - Uso exclusivo interno'
            }
        };
    }

    calculateCapex(screen) {
        // Extraer costos de instalación del JSON almacenado
        try {
            const capexData = screen.capex_data ? JSON.parse(screen.capex_data) : {};
            return {
                screenCost: capexData.screen || 0,
                installationCost: capexData.installation || 0,
                electricalCost: capexData.electrical || 0,
                structureCost: capexData.structure || 0,
                total: Object.values(capexData).reduce((sum, val) => sum + (Number(val) || 0), 0)
            };
        } catch (error) {
            return { total: 0 };
        }
    }

    generateROIAnalysis(screen) {
        const capex = this.calculateCapex(screen).total;
        const monthlyProfit = (screen.ingresos_mensuales || 0) - (screen.gastos_mensuales || 0);
        
        if (monthlyProfit <= 0 || capex <= 0) {
            return {
                roiMonths: '∞',
                roiPercentage: '0%',
                paybackPeriod: 'No aplica',
                recommendation: 'Pantalla no rentable'
            };
        }
        
        const roiMonths = capex / monthlyProfit;
        const roiPercentage = (monthlyProfit / capex) * 100 * 12; // ROI anualizado
        
        return {
            roiMonths: roiMonths.toFixed(1),
            roiPercentage: roiPercentage.toFixed(1) + '%',
            paybackPeriod: `${Math.ceil(roiMonths / 12)} años ${Math.ceil(roiMonths % 12)} meses`,
            recommendation: roiMonths <= 24 ? 'Excelente inversión' : 'Evaluar mejora de rentabilidad'
        };
    }

    calculateBreakEven(screen) {
        const capex = this.calculateCapex(screen).total;
        const monthlyProfit = (screen.ingresos_mensuales || 0) - (screen.gastos_mensuales || 0);
        
        if (monthlyProfit <= 0) {
            return 'No aplica - Sin ganancias';
        }
        
        const months = Math.ceil(capex / monthlyProfit);
        const date = new Date();
        date.setMonth(date.getMonth() + months);
        
        return {
            months: months,
            date: date.toLocaleDateString('es-MX'),
            status: months <= 24 ? 'Óptimo' : 'Extendido'
        };
    }

    generateRecommendations(screen, maintenances) {
        const recommendations = [];
        
        // Análisis de ROI
        const roi = screen.roi || 0;
        if (roi > 24) {
            recommendations.push({
                priority: 'Alta',
                title: 'Optimizar Rentabilidad',
                description: 'El ROI supera los 24 meses. Considerar aumentar ingresos o reducir gastos.',
                action: 'Revisar contratos publicitarios y costos operativos'
            });
        }
        
        // Análisis de mantenimientos
        const lastMaintenance = maintenances[0];
        if (lastMaintenance) {
            const lastDate = new Date(lastMaintenance.fecha);
            const today = new Date();
            const monthsSince = (today.getFullYear() - lastDate.getFullYear()) * 12 + 
                              (today.getMonth() - lastDate.getMonth());
            
            if (monthsSince > 3) {
                recommendations.push({
                    priority: 'Media',
                    title: 'Programar Mantenimiento Preventivo',
                    description: `Han pasado ${monthsSince} meses desde el último mantenimiento.`,
                    action: 'Agendar mantenimiento preventivo para el próximo mes'
                });
            }
        }
        
        // Análisis de uptime
        const uptime = parseFloat(screen.uptime) || 0;
        if (uptime < 95) {
            recommendations.push({
                priority: 'Alta',
                title: 'Mejorar Disponibilidad',
                description: `El uptime (${uptime}%) está por debajo del estándar industrial (95%).`,
                action: 'Investigar causas de desconexión y mejorar infraestructura'
            });
        }
        
        // Recomendación general si todo está bien
        if (recommendations.length === 0) {
            recommendations.push({
                priority: 'Baja',
                title: 'Mantener Estrategia Actual',
                description: 'La pantalla opera dentro de parámetros óptimos.',
                action: 'Continuar con monitoreo y mantenimientos preventivos programados'
            });
        }
        
        return recommendations;
    }

    async generatePDF(pdfData) {
        // Implementar generación real de PDF
        // Opciones:
        // 1. Usar jsPDF (cliente)
        // 2. Usar un servicio como PDFMonkey, DocRaptor, etc.
        // 3. Usar un backend propio con puppeteer
        
        // Por ahora, simular generación
        console.log('📄 Generando PDF con datos:', pdfData);
        
        // Ejemplo con jsPDF (necesitarías importar la librería)
        /*
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        
        // Agregar contenido al PDF
        doc.setFontSize(20);
        doc.text(pdfData.header.title, 20, 20);
        
        // ... más código para generar el PDF
        
        // Guardar PDF
        doc.save(`reporte-${pdfData.header.subtitle.split('ID: ')[1].split(' ')[0]}.pdf`);
        */
        
        // Retornar URL simulada por ahora
        return `https://your-pdf-service.com/report-${Date.now()}.pdf`;
    }
}

// Exportar para uso global
window.ReportGenerator = ReportGenerator;
