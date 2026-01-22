import streamlit as st
import pandas as pd
from PIL import Image

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Op. Trajes Españoles",
    page_icon="🧵",
    layout="wide"
)

# --- 2. LÓGICA FISCAL Y FINANCIERA (2026) ---

def calcular_isr_con_subsidio(base_gravable, uma_valor):
    """
    Calcula ISR, aplica Subsidio 2026 (Tope $11,492.66)
    y devuelve el ISR Neto (positivo = retener, negativo = entregar subsidio).
    """
    # A. Tabla ISR 2026 (Estimada)
    tabla = [
        (0.01, 0.0, 0.0192), (746.05, 14.32, 0.0640), (6332.06, 371.83, 0.1088),
        (11128.02, 893.63, 0.1600), (12935.83, 1182.88, 0.1792), (26988.51, 3701.24, 0.2136)
    ]
    
    # 1. ISR Bruto
    isr_bruto = 0.0
    for lim, cuota, porc in tabla:
        if base_gravable >= lim:
            isr_bruto = cuota + ((base_gravable - lim) * porc)
        else:
            break
            
    # B. Subsidio al Empleo 2026
    tope_ingresos_subsidio = 11492.66
    monto_subsidio = 0.0
    
    if base_gravable <= tope_ingresos_subsidio:
        uma_mensual = uma_valor * 30.4
        monto_subsidio = uma_mensual * 0.1182
        
    # 3. ISR Neto (Lo que se descuenta o se paga)
    isr_neto = isr_bruto - monto_subsidio
    
    return isr_bruto, monto_subsidio, isr_neto

def calcular_fi(dias_ag, dias_vac, prima_vac):
    return (365 + dias_ag + (dias_vac * prima_vac)) / 365

def calcular_todo(puesto, cant, sd, bono, uma, fi, tasa_isn, d_ag, d_vac, t_prima):
    dias_mes = 30.4
    
    # --- MENSUAL ---
    bruto_men = (sd * dias_mes) + ((bono/7) * dias_mes)
    
    # Cálculo Fiscal
    isr_bruto, subsidio, isr_neto_mensual = calcular_isr_con_subsidio(bruto_men, uma)
    
    # NETO A PAGAR AL TRABAJADOR
    # Si isr_neto_mensual es positivo, se le resta al bruto.
    # Si es negativo (porque el subsidio fue mayor), matemáticamente se suma (menos por menos da más).
    neto_a_recibir = bruto_men - isr_neto_mensual
    
    # Costo Empresa
    sbc = (sd * fi) + (bono/7)
    tope = 25 * uma
    if sbc > tope: sbc = tope
    
    cuota_patronal = (uma * 0.204 * dias_mes)
    if sbc > (3*uma): cuota_patronal += (sbc - (3*uma)) * 0.011 * dias_mes
    
    factor_ramas = 0.007 + 0.0105 + 0.0175 + 0.01 + 0.0113065 + 0.065 + 0.05
    carga_social = cuota_patronal + (sbc * factor_ramas * dias_mes)
    
    isn = bruto_men * tasa_isn
    costo_men = bruto_men + carga_social + isn
    
    # --- ANUAL ---
    aguinaldo = sd * d_ag
    prima = sd * d_vac * t_prima
    isn_anuales = (aguinaldo + prima) * tasa_isn
    
    # ISR Anual (Promedio estimado)
    grav_ag = max(0, aguinaldo - (30*uma))
    grav_pv = max(0, prima - (15*uma))
    base_anual_promedio = bruto_men + (grav_ag/12) + (grav_pv/12)
    _, _, isr_neto_promedio_anual = calcular_isr_con_subsidio(base_anual_promedio, uma)
    isr_total_anual_trabajador = isr_neto_promedio_anual * 12
    
    costo_anual = (costo_men * 12) + aguinaldo + prima + isn_anuales
    
    return {
        "Puesto": puesto, "Cantidad": cant,
        "Nómina Bruta (Men)": bruto_men,
        # FISCAL
        "ISR a Retener (Final)": isr_neto_mensual,
        "Neto a Recibir (Mensual)": neto_a_recibir, # <--- NUEVA COLUMNA
        # FINANCIERO
        "Costo Mensual (Empresa)": costo_men,
        "Aguinaldo (18 Días)": aguinaldo,
        "Prima Vacacional": prima,
        "COSTO ANUAL TOTAL": costo_anual,
        "Total_Grupo": costo_anual * cant,
        "Total_ISR_Grupo": isr_total_anual_trabajador * cant
    }

# --- 3. INTERFAZ GRÁFICA ---
st.title("🏭 Tablero de Costos - Op. Trajes Españoles")

with st.sidebar:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        st.warning("⚠️ Sin logo.png")
        
    st.header("Configuración 2026")
    uma = st.number_input("UMA ($)", value=113.14)
    st.markdown("---")
    smg = st.number_input("SM General ($)", value=316.04)
    sm_cost = st.number_input("SM Costurero ($)", value=326.38)
    sm_plan = st.number_input("SM Planchador ($)", value=326.84)
    st.markdown("---")
    d_ag = st.number_input("Días Aguinaldo", value=18)
    d_vac = st.number_input("Días Vacaciones", value=19)
    t_prima = st.number_input("Tasa Prima", value=0.25)
    t_isn = st.number_input("Tasa ISN", value=0.03)
    
    fi = calcular_fi(d_ag, d_vac, t_prima)

st.subheader("Definición de Plantilla")
c1, c2, c3 = st.columns(3)

c1.info("1. Ayudante")
n1_c = c1.number_input("Cant. Ayudantes", 0, value=1)
n1_b = c1.number_input("Bono Ayudante ($)", 0.0, value=198.0)

c2.success("2. Costurero")
n2_c = c2.number_input("Cant. Costureros", 0, value=1)
n2_b = c2.number_input("Bono Costurero ($)", 0.0, value=339.0)

c3.warning("3. Planchador")
n3_c = c3.number_input("Cant. Planchadores", 0, value=1)
n3_b = c3.number_input("Bono Planchador ($)", 0.0, value=339.0)

st.divider()

if st.button("CALCULAR REPORTE 🚀", type="primary", use_container_width=True):
    data = []
    if n1_c > 0: data.append(calcular_todo("1. Ayudante", n1_c, smg, n1_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    if n2_c > 0: data.append(calcular_todo("2. Costurero", n2_c, sm_cost, n2_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    if n3_c > 0: data.append(calcular_todo("3. Planchador", n3_c, sm_plan, n3_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    
    if data:
        df = pd.DataFrame(data)
        
        st.subheader("1. Análisis del Trabajador (Neto a Bolsillo)")
        # AQUI AGREGAMOS LA NUEVA COLUMNA DE NETO A RECIBIR
        cols_fiscal = ["Puesto", "Nómina Bruta (Men)", "ISR a Retener (Final)", "Neto a Recibir (Mensual)"]
        df_fiscal = df[cols_fiscal].copy()
        for c in cols_fiscal[1:]: df_fiscal[c] = df_fiscal[c].map('${:,.2f}'.format)
        st.dataframe(df_fiscal, use_container_width=True)
        
        st.subheader("2. Costos Empresa y Pasivos")
        cols_fin = ["Puesto", "Costo Mensual (Empresa)", "Aguinaldo (18 Días)", "Prima Vacacional", "COSTO ANUAL TOTAL"]
        df_fin = df[cols_fin].copy()
        for c in cols_fin[1:]: df_fin[c] = df_fin[c].map('${:,.2f}'.format)
        st.dataframe(df_fin, use_container_width=True)
        
        # --- SECCIÓN DE TOTALES (DISEÑO MÁS ANCHO) ---
        gasto_total = df["Total_Grupo"].sum()
        isr_total = df["Total_ISR_Grupo"].sum()
        flujo_men = (df["Costo Mensual (Empresa)"] * df["Cantidad"]).sum()
        
        st.markdown("---")
        st.markdown("### 📊 Totales Globales")
        
        # Fila 1: Flujo mensual e ISR (2 Columnas anchas)
        k1, k2 = st.columns(2)
        k1.metric("Flujo Mensual Requerido", f"${flujo_men:,.2f}", "Salida de Banco Mes")
        k2.metric("ISR Retenido Anual", f"${isr_total:,.2f}", "Enterar al SAT")
        
        # Fila 2: EL GRAN TOTAL (1 Columna completa para que no se corte)
        st.metric("GASTO ANUAL FÁBRICA (TOTAL)", f"${gasto_total:,.2f}", "Costo Real de la Operación")
        
    else:
        st.error("Selecciona al menos 1 empleado.")