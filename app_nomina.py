import streamlit as st
import pandas as pd
from PIL import Image

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Op. Trajes Españoles",
    page_icon="🧵",
    layout="wide"
)

# --- 2. LÓGICA FISCAL 2026 ---

def calcular_isr_desglosado(base_gravable, uma_valor):
    # Tabla ISR 2026
    tabla = [
        (0.01, 0.0, 0.0192), (746.05, 14.32, 0.0640), (6332.06, 371.83, 0.1088),
        (11128.02, 893.63, 0.1600), (12935.83, 1182.88, 0.1792), (26988.51, 3701.24, 0.2136)
    ]
    
    isr_bruto = 0.0
    for lim, cuota, porc in tabla:
        if base_gravable >= lim:
            isr_bruto = cuota + ((base_gravable - lim) * porc)
        else:
            break
            
    # Subsidio 2026
    tope_ingresos_subsidio = 11492.66
    monto_subsidio = 0.0
    
    if base_gravable <= tope_ingresos_subsidio:
        uma_mensual = uma_valor * 30.4
        monto_subsidio = uma_mensual * 0.1182
        
    difference = isr_bruto - monto_subsidio
    if difference < 0:
        isr_final = 0.0 
    else:
        isr_final = difference
        
    return isr_bruto, monto_subsidio, isr_final

def calcular_fi(dias_ag, dias_vac, prima_vac):
    return (365 + dias_ag + (dias_vac * prima_vac)) / 365

def calcular_todo(puesto, cant, sd, bono, uma, fi, tasa_isn, d_ag, d_vac, t_prima, descontar_imss):
    dias_mes = 30.4
    
    # 1. INGRESOS
    bruto_men = (sd * dias_mes) + ((bono/7) * dias_mes)
    
    # 2. FISCAL (ISR MENSUAL)
    isr_tarifa, subsidio_valor, isr_a_pagar = calcular_isr_desglosado(bruto_men, uma)
    
    # 3. SEGURIDAD SOCIAL (IMSS OBRERO)
    imss_obrero_mensual = 0.0
    sbc = (sd * fi) + (bono/7)
    tope = 25 * uma
    if sbc > tope: sbc = tope
    
    if descontar_imss:
        imss_obrero_mensual = sbc * 0.02375 * dias_mes

    # 4. NETO FINAL
    neto_mensual_real = bruto_men - isr_a_pagar - imss_obrero_mensual
    neto_semanal_real = (neto_mensual_real / 30.4) * 7
    
    # 5. COSTO EMPRESA (UNITARIO)
    cuota_patronal = (uma * 0.204 * dias_mes)
    if sbc > (3*uma): cuota_patronal += (sbc - (3*uma)) * 0.011 * dias_mes
    
    factor_ramas_patron = 0.007 + 0.0105 + 0.0175 + 0.01 + 0.0113065 + 0.065 + 0.05
    carga_social_patron = cuota_patronal + (sbc * factor_ramas_patron * dias_mes)
    isn = bruto_men * tasa_isn
    
    # Carga Social Mensual Unitario
    carga_social_mensual_unit = carga_social_patron + isn
    costo_men_empresa_unit = bruto_men + carga_social_mensual_unit
    
    # 6. ANUALES E ISR ANUAL
    aguinaldo = sd * d_ag
    prima = sd * d_vac * t_prima
    isn_anuales = (aguinaldo + prima) * tasa_isn
    
    # Cálculo ISR Anual (Estimado con promedio)
    grav_ag = max(0, aguinaldo - (30*uma))
    grav_pv = max(0, prima - (15*uma))
    # Base anual promedio para calcular la tasa efectiva anual
    base_anual_promedio = bruto_men + (grav_ag/12) + (grav_pv/12)
    _, _, isr_mensual_promedio_anual = calcular_isr_desglosado(base_anual_promedio, uma)
    isr_total_anual_unit = isr_mensual_promedio_anual * 12
    
    carga_social_anual_unit = (carga_social_mensual_unit * 12) + isn_anuales
    costo_anual_unit = (costo_men_empresa_unit * 12) + aguinaldo + prima + isn_anuales
    
    # --- MULTIPLICACIÓN POR GRUPO (TOTALES) ---
    
    # ISR del Grupo (Lo que pidió)
    isr_mensual_grupo = isr_a_pagar * cant
    isr_anual_grupo = isr_total_anual_unit * cant
    
    # Costos del Grupo
    carga_social_mensual_grupo = carga_social_mensual_unit * cant
    costo_men_empresa_grupo = costo_men_empresa_unit * cant
    carga_social_anual_grupo = carga_social_anual_unit * cant
    costo_anual_grupo = costo_anual_unit * cant
    
    return {
        "Puesto": puesto, 
        "Cantidad": cant,
        # Trabajador Unitario
        "Bruto": bruto_men,
        "Subsidio": subsidio_valor,
        "ISR Final": isr_a_pagar,
        "IMSS Obrero": imss_obrero_mensual,
        "Neto Mensual": neto_mensual_real,
        "PAGO SEMANAL (Unitario)": neto_semanal_real,
        
        # TOTALES GRUPO (EMPRESA + SAT)
        "ISR Retenido Men. (Grupo)": isr_mensual_grupo,    # <--- NUEVO
        "Carga Social Men. (Grupo)": carga_social_mensual_grupo, 
        "Costo Men. Total (Grupo)": costo_men_empresa_grupo,
        
        "ISR Retenido Anual (Grupo)": isr_anual_grupo,      # <--- NUEVO
        "Carga Social Anual (Grupo)": carga_social_anual_grupo,
        "Costo Anual Total (Grupo)": costo_anual_grupo,
        
        # Totales Métricas
        "Total_Nomina_Semanal": neto_semanal_real * cant,
        "Total_Grupo_Mensual": costo_men_empresa_grupo,
        "Total_Grupo_Anual": costo_anual_grupo
    }

# --- 3. INTERFAZ GRÁFICA ---
st.title("🏭 Tablero de Costos - Op. Trajes Españoles")

with st.sidebar:
    try:
        st.image("logo.jpg", use_container_width=True)
    except:
        st.warning("⚠️ Sin logo")
        
    st.header("Configuración 2026")
    st.markdown("### 🎚️ Control")
    usar_imss = st.checkbox("Descontar IMSS al Trabajador", value=True)
    st.markdown("---")
    uma = st.number_input("UMA ($)", value=113.14)
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

if st.button("CALCULAR TOTALES DE GRUPO 🚀", type="primary", use_container_width=True):
    data = []
    if n1_c > 0: data.append(calcular_todo("1. Ayudante", n1_c, smg, n1_b, uma, fi, t_isn, d_ag, d_vac, t_prima, usar_imss))
    if n2_c > 0: data.append(calcular_todo("2. Costurero", n2_c, sm_cost, n2_b, uma, fi, t_isn, d_ag, d_vac, t_prima, usar_imss))
    if n3_c > 0: data.append(calcular_todo("3. Planchador", n3_c, sm_plan, n3_b, uma, fi, t_isn, d_ag, d_vac, t_prima, usar_imss))
    
    if data:
        df = pd.DataFrame(data)
        
        def formato_pesos(val):
            return f"${val:,.2f}"

        # TABLA 1: AL TRABAJADOR (Unitario)
        st.subheader("1. Pago al Trabajador (Datos Individuales)")
        cols_fiscal = ["Puesto", "Bruto", "Subsidio", "ISR Final", "IMSS Obrero", "Neto Mensual", "PAGO SEMANAL (Unitario)"]
        df_fiscal = df[cols_fiscal].copy()
        for col in cols_fiscal[1:]: df_fiscal[col] = df_fiscal[col].apply(formato_pesos)   
        st.dataframe(df_fiscal, use_container_width=True, hide_index=True)
        
        # TABLA 2: COSTO EMPRESA & RETENCIONES (Total Grupo)
        st.subheader("2. Costo Real Empresa y Retenciones (TOTAL POR GRUPO)")
        st.info("💡 Incluye nuevas columnas de ISR Total a Enterar al SAT")
        
        # AGREGAMOS LAS COLUMNAS DE ISR GRUPO A LA VISTA
        cols_fin = [
            "Puesto", "Cantidad", 
            "ISR Retenido Men. (Grupo)", "Carga Social Men. (Grupo)", "Costo Men. Total (Grupo)", 
            "ISR Retenido Anual (Grupo)", "Costo Anual Total (Grupo)"
        ]
        
        df_fin = df[cols_fin].copy()
        for col in cols_fin[2:]: df_fin[col] = df_fin[col].apply(formato_pesos)
        st.dataframe(df_fin, use_container_width=True, hide_index=True)
        
        # --- TOTALES ---
        nomina_semanal_total = df["Total_Nomina_Semanal"].sum()
        gasto_mensual_total = df["Total_Grupo_Mensual"].sum()
        gasto_anual_total = df["Total_Grupo_Anual"].sum()
        
        st.markdown("---")
        st.markdown("### 📊 Tablero de Control Financiero")
        
        k1, k2, k3 = st.columns(3)
        k1.metric("1. NÓMINA SEMANAL (TOTAL)", f"${nomina_semanal_total:,.2f}", "A Dispersar Viernes")
        k2.metric("2. GASTO MENSUAL (TOTAL)", f"${gasto_mensual_total:,.2f}", "Costo Operativo Mes")
        k3.metric("3. GASTO ANUAL (TOTAL)", f"${gasto_anual_total:,.2f}", "Presupuesto 2026")
        
    else:
        st.error("Selecciona al menos 1 empleado.")