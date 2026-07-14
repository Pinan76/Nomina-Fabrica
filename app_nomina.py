import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(
    page_title="Nómina Estratégica V27",
    page_icon="💰",
    layout="wide"
)

# ==========================================
# MOTOR DE CÁLCULO V27 (SIN VALES)
# ==========================================

def calcular_isr_normalizado(ingreso_periodo, dias_periodo, uma_valor):
    """Calcula ISR exacto ajustado al periodo (28 o 35 días)."""
    factor_mes = 30.4
    if dias_periodo <= 0: return 0.0, 0.0
    
    # Elevar al mes promedio
    ingreso_mensual = (ingreso_periodo / dias_periodo) * factor_mes
    
    # Tabla ISR 2026
    tabla = [(0.01, 0.0, 0.0192), (746.05, 14.32, 0.0640), (6332.06, 371.83, 0.1088),
             (11128.02, 893.63, 0.1600), (12935.83, 1182.88, 0.1792), (26988.51, 3701.24, 0.2136)]
    
    isr_bruto = 0.0
    for lim, cuota, porc in tabla:
        if ingreso_mensual >= lim: isr_bruto = cuota + ((ingreso_mensual - lim) * porc)
        else: break
            
    # Subsidio
    subsidio = 0.0
    if ingreso_mensual <= 11492.66:
        subsidio = (uma_valor * 30.4) * 0.1502 
        
    # Regresar al periodo exacto
    isr_per = (isr_bruto / factor_mes) * dias_periodo
    sub_per = (subsidio / factor_mes) * dias_periodo
    
    return max(0, isr_per - sub_per), sub_per

def calcular_escenario_periodo(sd, bono_efec_sem, uma, fi, tasa_isn, dias_calc, desc_imss):
    """Calcula la nómina 100% efectivo de un periodo específico (28 o 35 días)."""
    
    # Convertir bono semanal a monto del periodo
    semanas_en_periodo = dias_calc / 7
    bono_efec_total = bono_efec_sem * semanas_en_periodo
    
    # 1. Ingresos Brutos Totales (Sueldo + Bonos)
    bruto = (sd * dias_calc) + bono_efec_total
    
    # 2. ISR
    isr, sub = calcular_isr_normalizado(bruto, dias_calc, uma)
    
    # 3. IMSS (Totalmente integrado)
    sbc = (sd * fi) + (bono_efec_sem / 7)
    if sbc > 25 * uma: sbc = 25 * uma
    
    imss_obr = 0.0
    if desc_imss: imss_obr = sbc * 0.02375 * dias_calc
    
    # Carga Patronal (Costo Empresa)
    cuota_pat = (uma * 0.204 * dias_calc)
    if sbc > 3 * uma: cuota_pat += (sbc - 3 * uma) * 0.011 * dias_calc
    
    # Suma de Ramas Patronales ~18.5%
    factor_ramas = 0.185 
    carga_patronal = cuota_pat + (sbc * factor_ramas * dias_calc) 
    
    # 4. ISN
    isn = bruto * tasa_isn
    
    # 5. Resultados
    neto_bolsillo = bruto - isr - imss_obr
    costo_empresa = bruto + carga_patronal + isn
    
    return isr, sub, neto_bolsillo, imss_obr, carga_patronal+isn, costo_empresa

def calcular_proyeccion_completa_v27(puesto, cant, sd, b_efec, uma, fi, tasa_isn, d_ag, d_vac, t_prima, desc_imss, semanas_view):
    """
    Proyección anual: 8 Periodos Cortos (4 sem) + 4 Periodos Largos (5 sem) + Prestaciones.
    """
    
    # --- A. CÁLCULOS MENSUALES (Para Tabla 1) ---
    dias_view = 28 if semanas_view == "4 Semanas" else 35
    
    isr_r, sub_r, neto_r, imss_obr_r, carga_r, costo_r = calcular_escenario_periodo(
        sd, b_efec, uma, fi, tasa_isn, dias_view, desc_imss
    )
    
    # --- B. CÁLCULO ANUAL EXACTO (Fórmula $178k+) ---
    
    # 1. Costo de un Mes Corto (28 días)
    _, _, _, _, _, costo_mes_corto = calcular_escenario_periodo(sd, b_efec, uma, fi, tasa_isn, 28, desc_imss)
    
    # 2. Costo de un Mes Largo (35 días)
    _, _, _, _, _, costo_mes_largo = calcular_escenario_periodo(sd, b_efec, uma, fi, tasa_isn, 35, desc_imss)
    
    # 3. Suma Operativa Anual (12 periodos = 52 semanas)
    costo_operativo_anual = (costo_mes_corto * 8) + (costo_mes_largo * 4)
    
    # 4. Prestaciones de Fin de Año
    aguinaldo = sd * d_ag
    prima = sd * d_vac * t_prima
    isn_prest = (aguinaldo + prima) * tasa_isn
    
    costo_anual_total_unit = costo_operativo_anual + aguinaldo + prima + isn_prest
    
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
# INTERFAZ GRÁFICA (LAYOUT ORIGINAL V27)
# ==========================================

# --- SIDEBAR (LOGO + CONFIG) ---
with st.sidebar:
    # 1. LOGO
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
    d_vac = st.number_input("Días Vacaciones", 19)
    fi = calcular_fi(d_ag, d_vac, 0.25)

st.title("Simulador de Nómina Estratégica (V27)")

tab1, tab2, tab3 = st.tabs(["1. NÓMINA (Original)", "2. GASTOS (Pendiente)", "3. MAQUILA (Pendiente)"])

with tab1:
    # --- CONTROLES SUPERIORES ---
    c_top1, c_top2 = st.columns(2)
    semanas = c_top1.radio("Visualizar Periodo:", ["4 Semanas", "5 Semanas"], horizontal=True)
    usar_imss = c_top2.checkbox("Descontar IMSS al Obrero", value=True)
    
    st.markdown("---")
    
    # --- INPUTS DE BONOS (CENTRADOS) ---
    colA, colB, colC = st.columns(3)
    
    # 1. AYUDANTE
    with colA:
        st.info("### 👷 Ayudante")
        n_ayu = st.number_input("Personal", 0, 1000, 111, key="na")
        be_ayu = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=350.0, key="bea")
        
    # 2. COSTURERO
    with colB:
        st.success("### 🪡 Costurero")
        n_cos = st.number_input("Personal", 0, 1000, 177, key="nc")
        be_cos = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=500.0, key="bec")
        
    # 3. PLANCHADOR
    with colC:
        st.warning("### ♨️ Planchador")
        n_plan = st.number_input("Personal", 0, 1000, 38, key="np")
        be_plan = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=600.0, key="bep")
        
    st.markdown("---")
    
    # --- BOTÓN DE CÁLCULO ---
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
            
            # FORMATO DE PESOS
            def fmt(x): return "${:,.2f}".format(x)
            
            # --- TABLA 1: DETALLE TRABAJADOR ---
            st.subheader(f"1. Detalle del Trabajador (Periodo: {semanas})")
            cols_w = ["Puesto", "Bruto", "Subsidio", "ISR Ret", "IMSS Obr", "Neto"]
            df_show1 = df[cols_w].copy()
            for c in cols_w[1:]: df_show1[c] = df_show1[c].apply(fmt)
            st.table(df_show1)
            
            # --- TABLA 2: PRESUPUESTO REAL ANUAL ---
            st.subheader("2. Presupuesto Real (Proyección 52 Semanas)")
            st.caption("Fórmula: (8 Meses Cortos + 4 Meses Largos) + Aguinaldo + Prima + ISN Prestaciones")
            
            cols_fin = ["Puesto", "Cantidad", "Costo Mensual Grupo", "Costo Anual Grupo"]
            df_show2 = df[cols_fin].copy()
            for c in cols_fin[2:]: df_show2[c] = df_show2[c].apply(fmt)
            st.table(df_show2)
            
            # --- TOTALES ---
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
