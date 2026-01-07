import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Tablero Nómina Fábrica 2026",
    page_icon="🏭",
    layout="wide"
)

# --- 2. MÓDULO FISCAL (ISR) ---
def calcular_isr_mensual(base_gravable):
    """Calcula ISR Mensual (Tarifa 2026 est)."""
    tabla_isr = [
        (0.01, 0.0, 0.0192),
        (746.05, 14.32, 0.0640),
        (6332.06, 371.83, 0.1088),
        (11128.02, 893.63, 0.1600),
        (12935.83, 1182.88, 0.1792),
        (26988.51, 3701.24, 0.2136)
    ]
    isr = 0.0
    for limite, cuota, porc in tabla_isr:
        if base_gravable >= limite:
            excedente = base_gravable - limite
            isr = cuota + (excedente * porc)
        else:
            break
    return isr

# --- 3. LÓGICA DE CÁLCULO FINANCIERO ---
def calcular_fi(dias_aguinaldo, dias_vacaciones, prima_vacacional_tasa):
    base = 365 + dias_aguinaldo + (dias_vacaciones * prima_vacacional_tasa)
    return base / 365

def calcular_costo_master(puesto, cantidad, sd, bono, uma, fi, tasa_isn, d_ag, d_vac, t_prima):
    """
    Integra V1 (Operativo), V2 (Anuales) y V3 (Fiscal) en un solo registro.
    """
    dias_mes = 30.4
    
    # --- A. CÁLCULOS MENSUALES ---
    sueldo_mensual = sd * dias_mes
    bono_mensual = (bono / 7) * dias_mes
    nomina_bruta = sueldo_mensual + bono_mensual
    
    # ISR Trabajador
    isr_mensual = calcular_isr_mensual(nomina_bruta)
    sueldo_neto = nomina_bruta - isr_mensual # (Sin considerar retención IMSS obrero para simplificar)
    
    # Carga Social Patronal (Detalle V1)
    sbc_fijo = sd * fi
    sbc_variable = bono / 7
    sbc_total = sbc_fijo + sbc_variable
    
    # Tope 25 UMA
    tope = 25 * uma
    if sbc_total > tope: sbc_total = tope
    
    # Desglose Carga Social
    cuota_fija = (uma * 0.204) * dias_mes
    excedente = (sbc_total - (3*uma))*0.011*dias_mes if sbc_total > (3*uma) else 0
    ramas = sbc_total * (0.007 + 0.0105 + 0.0175 + 0.01 + 0.0113065) * dias_mes
    retiro_cv = sbc_total * 0.065 * dias_mes
    infonavit = sbc_total * 0.05 * dias_mes
    
    carga_social = cuota_fija + excedente + ramas + retiro_cv + infonavit
    
    isn = nomina_bruta * tasa_isn
    
    costo_mensual = nomina_bruta + carga_social + isn

    # --- B. CÁLCULOS ANUALES ---
    # Aguinaldo
    aguinaldo = sd * d_ag
    # Prima
    prima = sd * d_vac * t_prima
    
    # ISR Anual (Total retenido 12 meses + ajuste anualidades)
    gravado_ag = max(0, aguinaldo - (30*uma))
    gravado_pv = max(0, prima - (15*uma))
    base_anual = nomina_bruta + gravado_ag + gravado_pv
    isr_base_anual = calcular_isr_mensual(base_anual)
    isr_extra = max(0, isr_base_anual - isr_mensual)
    isr_total_anual = (isr_mensual * 12) + isr_extra
    
    isn_anuales = (aguinaldo + prima) * tasa_isn
    
    costo_anual = (costo_mensual * 12) + aguinaldo + prima + isn_anuales
    
    return {
        "Puesto": puesto,
        "Cantidad": cantidad,
        # V1: Datos Operativos
        "SBC Diario": sbc_total,
        "Nómina Bruta (Men)": nomina_bruta,
        "Carga Social IMSS (Men)": carga_social,
        "ISN Estatal (Men)": isn,
        # V3: Retenciones
        "ISR a Retener (Men)": isr_mensual,
        "ISR Total Año (Trab)": isr_total_anual,
        # Resultados Finales
        "Costo Mensual (Empresa)": costo_mensual,
        "Aguinaldo + Prima (Neto)": aguinaldo + prima,
        "COSTO ANUAL TOTAL": costo_anual,
        # Totales para sumatorias
        "Total_Grupo_Anual": costo_anual * cantidad,
        "Total_ISR_Grupo": isr_total_anual * cantidad
    }

# --- 4. INTERFAZ GRÁFICA ---

st.title("🏭 Tablero de Costos de Fábrica (Master)")
st.markdown("### Análisis Integral: Operativo + Fiscal + Pasivos")

with st.sidebar:
    st.header("⚙️ Configuración 2026")
    uma = st.number_input("UMA ($)", value=113.14)
    st.markdown("---")
    smg = st.number_input("SM General ($)", value=315.04)
    sm_cost = st.number_input("SM Costurero ($)", value=326.38)
    sm_plan = st.number_input("SM Planchador ($)", value=326.84)
    st.markdown("---")
    d_ag = st.number_input("Días Aguinaldo", value=18)
    d_vac = st.number_input("Días Vacaciones", value=19)
    t_prima = st.number_input("Tasa Prima", value=0.25)
    t_isn = st.number_input("Tasa ISN", value=0.03)
    
    fi = calcular_fi(d_ag, d_vac, t_prima)

# Inputs en columnas
c1, c2, c3 = st.columns(3)
with c1:
    n1_c = st.number_input("Cant. Ayudantes", 0, value=1)
    n1_b = st.number_input("Bono Ayudante ($)", 0.0, value=350.0)
with c2:
    n2_c = st.number_input("Cant. Costureros", 0, value=1)
    n2_b = st.number_input("Bono Costurero ($)", 0.0, value=500.0)
with c3:
    n3_c = st.number_input("Cant. Planchadores", 0, value=1)
    n3_b = st.number_input("Bono Planchador ($)", 0.0, value=600.0)

st.divider()

if st.button("Generar Reporte Completo 🚀", type="primary", use_container_width=True):
    
    data = []
    
    if n1_c > 0: data.append(calcular_costo_master("1. Ayudante", n1_c, smg, n1_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    if n2_c > 0: data.append(calcular_costo_master("2. Costurero", n2_c, sm_cost, n2_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    if n3_c > 0: data.append(calcular_costo_master("3. Planchador", n3_c, sm_plan, n3_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    
    if len(data) > 0:
        df = pd.DataFrame(data)
        
        # --- TABLA 1: ANÁLISIS MENSUAL DETALLADO (Regresan las columnas V1) ---
        st.subheader("1. Detalle Operativo Mensual (Desglose)")
        cols_mensual = [
            "Puesto", "Cantidad", "SBC Diario", "Nómina Bruta (Men)", 
            "Carga Social IMSS (Men)", "ISN Estatal (Men)", "Costo Mensual (Empresa)"
        ]
        df_men = df[cols_mensual].copy()
        for c in cols_mensual[2:]: df_men[c] = df_men[c].map('${:,.2f}'.format)
        st.dataframe(df_men, use_container_width=True)
        
        # --- TABLA 2: ANÁLISIS FISCAL Y ANUAL (V2 y V3) ---
        st.subheader("2. Impuestos y Pasivos Anuales")
        cols_anual = [
            "Puesto", "ISR a Retener (Men)", "ISR Total Año (Trab)", 
            "Aguinaldo + Prima (Neto)", "COSTO ANUAL TOTAL"
        ]
        df_an = df[cols_anual].copy()
        for c in cols_anual[1:]: df_an[c] = df_an[c].map('${:,.2f}'.format)
        st.dataframe(df_an, use_container_width=True)
        
        # --- KPIs FINALES ---
        total_gasto = df["Total_Grupo_Anual"].sum()
        total_isr = df["Total_ISR_Grupo"].sum()
        mensual_flow = (df["Costo Mensual (Empresa)"] * df["Cantidad"]).sum()
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Flujo Mensual Requerido", f"${mensual_flow:,.2f}", "Salida de banco mes a mes")
        k2.metric("ISR Retenido Anual", f"${total_isr:,.2f}", "Impuesto de trabajadores al SAT")
        k3.metric("GASTO ANUAL TOTAL", f"${total_gasto:,.2f}", "Costo Real Fábrica")
        
    else:
        st.warning("Selecciona personal para calcular.")