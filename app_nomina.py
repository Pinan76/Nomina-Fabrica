import streamlit as st
import pandas as pd
from PIL import Image

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Op. Trajes Españoles",
    page_icon="🧵",
    layout="wide"
)

# --- 2. LÓGICA FISCAL Y FINANCIERA ---
def calcular_isr_mensual(base):
    # Tabla ISR 2026 (Estimada)
    tabla = [
        (0.01, 0.0, 0.0192), (746.05, 14.32, 0.0640), (6332.06, 371.83, 0.1088),
        (11128.02, 893.63, 0.1600), (12935.83, 1182.88, 0.1792), (26988.51, 3701.24, 0.2136)
    ]
    isr = 0.0
    for lim, cuota, porc in tabla:
        if base >= lim:
            isr = cuota + ((base - lim) * porc)
        else:
            break
    return isr

def calcular_fi(dias_ag, dias_vac, prima_vac):
    return (365 + dias_ag + (dias_vac * prima_vac)) / 365

def calcular_todo(puesto, cant, sd, bono, uma, fi, tasa_isn, d_ag, d_vac, t_prima):
    dias_mes = 30.4
    
    # --- MENSUAL ---
    bruto_men = (sd * dias_mes) + ((bono/7) * dias_mes)
    isr_men = calcular_isr_mensual(bruto_men)
    
    sbc = (sd * fi) + (bono/7)
    tope = 25 * uma
    if sbc > tope: sbc = tope
    
    cuota_patronal = (uma * 0.204 * dias_mes)
    if sbc > (3*uma): cuota_patronal += (sbc - (3*uma)) * 0.011 * dias_mes
    
    factor_ramas = 0.007 + 0.0105 + 0.0175 + 0.01 + 0.0113065 + 0.065 + 0.05
    carga_social = cuota_patronal + (sbc * factor_ramas * dias_mes)
    
    isn = bruto_men * tasa_isn
    costo_men = bruto_men + carga_social + isn
    
    # --- ANUAL (DESGLOSE) ---
    monto_aguinaldo = sd * d_ag
    valor_vacaciones = sd * d_vac # Cuánto valen los días de vacaciones en dinero
    monto_prima = valor_vacaciones * t_prima
    
    # ISR Anual
    grav_ag = max(0, monto_aguinaldo - (30*uma))
    grav_pv = max(0, monto_prima - (15*uma))
    isr_anual_base = calcular_isr_mensual(bruto_men + grav_ag + grav_pv)
    isr_extra = max(0, isr_anual_base - isr_men)
    isr_total_anual = (isr_men * 12) + isr_extra
    
    # Costo Total Anual
    # Nota: 'valor_vacaciones' ya está incluido en los 12 meses de 'costo_men' (se pagan aunque descansen).
    # Solo sumamos como EXTRA el Aguinaldo y la Prima.
    isn_anuales = (monto_aguinaldo + monto_prima) * tasa_isn
    costo_anual = (costo_men * 12) + monto_aguinaldo + monto_prima + isn_anuales
    
    return {
        "Puesto": puesto, "Cantidad": cant,
        "SBC Diario": sbc, "Nómina Bruta (Men)": bruto_men,
        "Carga Social IMSS (Men)": carga_social,
        "Costo Mensual (Empresa)": costo_men,
        # Columnas Nuevas Desglosadas:
        "Aguinaldo (18 Días)": monto_aguinaldo,
        "Valor Vacaciones": valor_vacaciones,
        "Prima Vacacional": monto_prima,
        # Finales
        "ISR Total Año (Trab)": isr_total_anual,
        "COSTO ANUAL TOTAL": costo_anual,
        "Total_Grupo": costo_anual * cant, "Total_ISR_Grupo": isr_total_anual * cant
    }

# --- 3. INTERFAZ GRÁFICA ---
st.title("🏭 Tablero de Costos - Operadora de Trajes Españoles")

with st.sidebar:
    try:
        st.image("logo.jpg", use_container_width=True)
    except:
        st.warning("⚠️ Sin logo.jpg")
        
    st.header("Configuración 2026")
    uma = st.number_input("UMA ($)", value=113.14)
    st.markdown("---")
    smg = st.number_input("SM General ($)", value=316.40)
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
n1_b = c1.number_input("Bono Ayudante ($)", 0.0, value=350.0)

c2.success("2. Costurero")
n2_c = c2.number_input("Cant. Costureros", 0, value=1)
n2_b = c2.number_input("Bono Costurero ($)", 0.0, value=500.0)

c3.warning("3. Planchador")
n3_c = c3.number_input("Cant. Planchadores", 0, value=1)
n3_b = c3.number_input("Bono Planchador ($)", 0.0, value=600.0)

st.divider()

if st.button("CALCULAR REPORTE 🚀", type="primary", use_container_width=True):
    data = []
    if n1_c > 0: data.append(calcular_todo("1. Ayudante", n1_c, smg, n1_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    if n2_c > 0: data.append(calcular_todo("2. Costurero", n2_c, sm_cost, n2_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    if n3_c > 0: data.append(calcular_todo("3. Planchador", n3_c, sm_plan, n3_b, uma, fi, t_isn, d_ag, d_vac, t_prima))
    
    if data:
        df = pd.DataFrame(data)
        
        st.subheader("1. Desglose Mensual (Operativo)")
        cols_men = ["Puesto", "Cantidad", "SBC Diario", "Nómina Bruta (Men)", "Carga Social IMSS (Men)", "Costo Mensual (Empresa)"]
        df_men = df[cols_men].copy()
        for c in cols_men[2:]: df_men[c] = df_men[c].map('${:,.2f}'.format)
        st.dataframe(df_men, use_container_width=True)
        
        st.subheader("2. Impuestos y Pasivos Anuales (Desglosados)")
        # AQUI ESTAN LAS NUEVAS COLUMNAS SEPARADAS:
        cols_an = [
            "Puesto", 
            "Aguinaldo (18 Días)", 
            "Valor Vacaciones", 
            "Prima Vacacional", 
            "ISR Total Año (Trab)", 
            "COSTO ANUAL TOTAL"
        ]
        df_an = df[cols_an].copy()
        for c in cols_an[1:]: df_an[c] = df_an[c].map('${:,.2f}'.format)
        st.dataframe(df_an, use_container_width=True)
        
        # Totales
        gasto_total = df["Total_Grupo"].sum()
        isr_total = df["Total_ISR_Grupo"].sum()
        flujo_men = (df["Costo Mensual (Empresa)"] * df["Cantidad"]).sum()
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Flujo Mensual Requerido", f"${flujo_men:,.2f}")
        k2.metric("ISR Retenido Anual", f"${isr_total:,.2f}")
        k3.metric("GASTO ANUAL FÁBRICA", f"${gasto_total:,.2f}")
    else:
        st.error("Selecciona al menos 1 empleado.")



