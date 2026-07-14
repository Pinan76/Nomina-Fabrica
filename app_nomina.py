import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(
    page_title="Nómina Estratégica V27",
    page_icon="💰",
    layout="wide"
)

# ==========================================
# MOTOR DE CÁLCULO V27 (ACTUALIZADO 2026)
# ==========================================

def calcular_isr_normalizado(ingreso_periodo, dias_periodo, uma_valor):
    factor_mes = 30.4
    if dias_periodo <= 0: return 0.0, 0.0
    
    ingreso_mensual = (ingreso_periodo / dias_periodo) * factor_mes
    
    tabla = [(0.01, 0.0, 0.0192), (746.05, 14.32, 0.0640), (6332.06, 371.83, 0.1088),
             (11128.02, 893.63, 0.1600), (12935.83, 1182.88, 0.1792), (26988.51, 3701.24, 0.2136)]
    
    isr_bruto = 0.0
    for lim, cuota, porc in tabla:
        if ingreso_mensual >= lim: isr_bruto = cuota + ((ingreso_mensual - lim) * porc)
        else: break
            
    subsidio = 0.0
    if ingreso_mensual <= 11492.66:
        subsidio = (uma_valor * 30.4) * 0.1502 
        
    isr_per = (isr_bruto / factor_mes) * dias_periodo
    sub_per = (subsidio / factor_mes) * dias_periodo
    
    return max(0, isr_per - sub_per), sub_per

def calcular_escenario_periodo(sd, bono_efec_sem, uma, fi, tasa_isn, dias_calc, desc_imss):
    semanas_en_periodo = dias_calc / 7
    bono_efec_total = bono_efec_sem * semanas_en_periodo
    bruto = (sd * dias_calc) + bono_efec_total
    
    isr, sub = calcular_isr_normalizado(bruto, dias_calc, uma)
    
    sbc = (sd * fi) + (bono_efec_sem / 7)
    if sbc > 25 * uma: sbc = 25 * uma
    
    imss_obr = 0.0
    if desc_imss: imss_obr = sbc * 0.02375 * dias_calc
    
    cuota_pat = (uma * 0.204 * dias_calc)
    if sbc > 3 * uma: cuota_pat += (sbc - 3 * uma) * 0.011 * dias_calc
    
    # --- MOTOR DINÁMICO IMSS (REFORMA CEAV 2026) ---
    ramas_base = 0.14098 
    ratio_uma = sbc / uma
    if ratio_uma <= 1.0: ceav = 0.03150
    elif ratio_uma <= 1.5: ceav = 0.04241
    elif ratio_uma <= 2.0: ceav = 0.05060
    elif ratio_uma <= 2.5: ceav = 0.05688
    elif ratio_uma <= 3.0: ceav = 0.06177
    elif ratio_uma <= 3.5: ceav = 0.06551
    elif ratio_uma <= 4.0: ceav = 0.06845
    else: ceav = 0.0875
    
    factor_ramas_2026 = ramas_base + ceav 
    
    carga_patronal = cuota_pat + (sbc * factor_ramas_2026 * dias_calc) 
    isn = bruto * tasa_isn
    
    neto_bolsillo = bruto - isr - imss_obr
    costo_empresa = bruto + carga_patronal + isn
    
    return isr, sub, neto_bolsillo, imss_obr, carga_patronal+isn, costo_empresa

def calcular_proyeccion_completa_v27(puesto, cant, sd, b_efec, uma, fi, tasa_isn, d_ag, d_vac, t_prima, desc_imss, semanas_view):
    dias_view = 28 if semanas_view == "4 Semanas" else 35
    
    isr_r, sub_r, neto_r, imss_obr_r, carga_r, costo_r = calcular_escenario_periodo(
        sd, b_efec, uma, fi, tasa_isn, dias_view, desc_imss
    )
    
    _, _, _, _, _, costo_mes_corto = calcular_escenario_periodo(sd, b_efec, uma, fi, tasa_isn, 28, desc_imss)
    _, _, _, _, _, costo_mes_largo = calcular_escenario_periodo(sd, b_efec, uma, fi, tasa_isn, 35, desc_imss)
    
    # 1. Costo Operativo Anual Base (52 Semanas de Trabajo y Sueldo Ordinario)
    costo_operativo_anual = (costo_mes_corto * 8) + (costo_mes_largo * 4)
    
    # 2. Costo Vacaciones (Promedio 18.5 Días)
    vacaciones_anual = sd * d_vac
    
    # 3. Prima Vacacional (25% sobre los 18.5 días de vacaciones)
    prima_vacacional = vacaciones_anual * t_prima
    
    # 4. Aguinaldo
    aguinaldo = sd * d_ag
    
    # ISN sobre todas las prestaciones anuales extras (3%)
    isn_prestaciones = (aguinaldo + vacaciones_anual + prima_vacacional) * tasa_isn
    
    # GRAN TOTAL ANUAL UNITARIO
    costo_anual_total_unit = costo_operativo_anual + aguinaldo + vacaciones_anual + prima_vacacional + isn_prestaciones
    
    return {
        "Puesto": puesto, "Cantidad": cant,
        "Bruto": (sd*dias_view) + ((b_efec/7) * dias_view),
        "Subsidio": sub_r, "ISR Ret": isr_r, "IMSS Obr": imss_obr_r, "Neto": neto_r,
        "Costo Mensual Grupo": costo_r * cant,
        "Costo Anual Grupo": costo_anual_total_unit * cant
    }

def calcular_fi(d_ag, d_vac, t_prima):
    return (365 + d_ag + (d_vac * t_prima)) / 365

# ==========================================
# INTERFAZ GRÁFICA 
# ==========================================

with st.sidebar:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        st.markdown("### 🏭 Trajes Españoles")
        st.warning("Falta archivo 'logo.png'")
        
    st.markdown("---")
    st.header("Configuración")
    
    uma = st.number_input("UMA 2026", value=117.31)
    
    st.divider()
    st.markdown("### Salarios Base (Diario)")
    sd_ayu = st.number_input("Ayudante ($)", value=316.40)
    sd_cos = st.number_input("Costurero ($)", value=326.38)
    sd_plan = st.number_input("Planchador ($)", value=326.84)
    
    st.divider()
    st.markdown("### Prestaciones Ley")
    d_ag = st.number_input("Días Aguinaldo", 18)
    # PROMEDIO DE 18.5 DÍAS TOTALMENTE INTEGRADO
    d_vac = st.number_input("Días Vacaciones (Promedio)", value=18.5, disabled=True, help="Promedio corporativo fijo de 18.5 días.") 
    fi = calcular_fi(d_ag, d_vac, 0.25)

st.title("Simulador de Nómina Estratégica (V27)")

tab1, tab2, tab3 = st.tabs(["1. NÓMINA (Original)", "2. GASTOS (Pendiente)", "3. MAQUILA (Pendiente)"])

with tab1:
    c_top1, c_top2 = st.columns(2)
    semanas = c_top1.radio("Visualizar Periodo:", ["4 Semanas", "5 Semanas"], horizontal=True)
    usar_imss = c_top2.checkbox("Descontar IMSS al Obrero", value=True)
    
    st.markdown("---")
    
    colA, colB, colC = st.columns(3)
    
    with colA:
        st.info("### 👷 Ayudante")
        n_ayu = st.number_input("Personal", 0, 1000, 111, key="na")
        be_ayu = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=350.0, key="bea")
        
    with colB:
        st.success("### 🪡 Costurero")
        n_cos = st.number_input("Personal", 0, 1000, 177, key="nc")
        be_cos = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=500.0, key="bec")
        
    with colC:
        st.warning("### ♨️ Planchador")
        n_plan = st.number_input("Personal", 0, 1000, 38, key="np")
        be_plan = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=600.0, key="bep")
        
    st.markdown("---")
    
    if st.button("CALCULAR NÓMINA V27", type="primary", use_container_width=True):
        
        t_isn = 0.03
        data = []
        
        if n_ayu > 0:
            data.append(calcular_proyeccion_completa_v27("Ayudante", n_ayu, sd_ayu, be_ayu, uma, fi, t_isn, d_ag, d_vac, 0.25, usar_imss, semanas))
        if n_cos > 0:
            data.append(calcular_proyeccion_completa_v27("Costurero", n_cos, sd_cos, be_cos, uma, fi, t_isn, d_ag, d_vac, 0.25, usar_imss, semanas))
        if n_plan > 0:
            data.append(calcular_proyeccion_completa_v27("Planchador", n_plan, sd_plan, be_plan, uma, fi, t_isn, d_ag, d_vac, 0.25, usar_imss, semanas))
            
        if data:
            df = pd.DataFrame(data)
            def fmt(x): return "${:,.2f}".format(x)
            
            st.subheader(f"1. Detalle del Trabajador (Periodo: {semanas})")
            cols_w = ["Puesto", "Bruto", "Subsidio", "ISR Ret", "IMSS Obr", "Neto"]
            df_show1 = df[cols_w].copy()
            for c in cols_w[1:]: df_show1[c] = df_show1[c].apply(fmt)
            st.table(df_show1)
            
            st.subheader("2. Presupuesto Real Anual (Calculado)")
            st.caption("Proyección de Gasto: (8 Meses Cortos + 4 Meses Largos) + Aguinaldo + Vacaciones (Promedio 18.5 Días) + Prima Vacacional + ISN Prestaciones")
            
            cols_fin = ["Puesto", "Cantidad", "Costo Mensual Grupo", "Costo Anual Grupo"]
            df_show2 = df[cols_fin].copy()
            for c in cols_fin[2:]: df_show2[c] = df_show2[c].apply(fmt)
            st.table(df_show2)
            
            total_anual = df["Costo Anual Grupo"].sum()
            total_personas = df["Cantidad"].sum()
            
            st.success(f"### GRAN TOTAL NÓMINA ANUAL: ${total_anual:,.2f}")
            st.metric("Total Plantilla", f"{total_personas}")
            
        else:
            st.warning("⚠️ Ingresa al menos 1 trabajador.")

with tab2:
    st.write("🚧 Módulo de Gastos (Pendiente de Configurar)")

with tab3:
    st.write("🚧 Cotizador Maquila (Pendiente de Configurar)")
