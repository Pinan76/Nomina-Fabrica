import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Suite Maquila 2026",
    page_icon="👔",
    layout="wide"
)

# --- 2. MOTOR DE CÁLCULO FISCAL (POR PUESTO) ---
def calcular_costo_empresa_unitario(sd, bono_vales, bono_efectivo, uma, fi, tasa_isn, factor_deducibilidad):
    dias_calculo = 30.4 # Mes promedio
    
    # Ingresos Base
    nomina_base = (sd * dias_calculo)
    bono_total_efectivo = (bono_efectivo / 7) * dias_calculo
    bono_total_vales = (bono_vales / 7) * dias_calculo
    
    # Carga Social (IMSS) - Excedente Vales
    tope_diario_vales = uma * 0.40
    vales_diario = bono_vales / 7
    excedente_diario = max(0, vales_diario - tope_diario)
    
    sbc = (sd * fi) + (bono_efectivo/7) + excedente_diario
    if sbc > (25*uma): sbc = 25*uma
    
    # Cuotas Patronales Estimadas
    cuota_patronal_base = (uma * 0.204 * dias_calculo)
    if sbc > (3*uma): cuota_patronal_base += (sbc - (3*uma)) * 0.011 * dias_calculo
    factor_ramas_imss = 0.185 
    imss_patronal = cuota_patronal_base + (sbc * factor_ramas_imss * dias_calculo)
    
    # ISN
    base_isn = nomina_base + bono_total_efectivo
    isn = base_isn * tasa_isn
    
    # Costo Fiscal (No Deducibilidad)
    no_deducible = bono_total_vales * (1 - factor_deducibilidad)
    isr_corp_extra = no_deducible * 0.30
    
    # Prestaciones Anuales (Provisión mensual)
    dias_ag = 18
    dias_vac = 19
    tasa_prima = 0.25
    costo_anual_prestaciones = (sd * dias_ag) + (sd * dias_vac * tasa_prima)
    provision_mensual_prestaciones = costo_anual_prestaciones / 12
    
    # Costo Total Mensual por Cabeza
    costo_total_mensual = (nomina_base + bono_total_efectivo + bono_total_vales + 
                           imss_patronal + isn + isr_corp_extra + provision_mensual_prestaciones)
    
    return costo_total_mensual

# --- 3. CARGA DE DATOS INTELIGENTE ---
@st.cache_data
def cargar_datos_detallados():
    gastos_anuales = 0.0
    nomina_admin_anual = 0.0
    
    # Contadores Globales
    count_ayudante = 0
    count_costurero = 0
    count_planchador = 0
    count_otros = 0
    
    def clasificar_puesto(df):
        a, c, p, o = 0, 0, 0, 0
        if 'Puesto' in df.columns:
            puestos = df['Puesto'].astype(str).str.upper()
            a = puestos.str.contains('AYUDANTE').sum()
            p = puestos.str.contains('PLANCHADOR').sum()
            c = puestos.str.contains('COSTURERO').sum() + puestos.str.contains('COSTURERA').sum()
            
            total_validos = len(df[pd.to_numeric(df.iloc[:,0], errors='coerce').notnull()])
            detectados = a + c + p
            if detectados < total_validos:
                o = total_validos - detectados
        return a, c, p, o

    # LEER EXCEL GASTOS
    try:
        xls_gastos = pd.ExcelFile("Gastos_2025.xlsx")
        
        # Gastos Fijos
        if "Control_Gastos" in xls_gastos.sheet_names:
            df_g = pd.read_excel(xls_gastos, sheet_name="Control_Gastos")
            gastos_anuales = pd.to_numeric(df_g['Gasto Anual'], errors='coerce').sum()
            
        # Nómina Admin
        if "Sueldos Admin" in xls_gastos.sheet_names:
            df_a = pd.read_excel(xls_gastos, sheet_name="Sueldos Admin", skiprows=2)
            # Buscamos la última columna numérica
            nomina_admin_mensual = pd.to_numeric(df_a.iloc[:, -1], errors='coerce').sum()
            nomina_admin_anual = nomina_admin_mensual * 12
            
        # Pantalón
        sheet_pant = next((s for s in xls_gastos.sheet_names if "Pantalon" in s or "Pantalón" in s), None)
        if sheet_pant:
            df_p = pd.read_excel(xls_gastos, sheet_name=sheet_pant)
            a, c, pl, o = clasificar_puesto(df_p)
            count_ayudante += a
            count_costurero += c
            count_planchador += pl
            count_otros += o
            
        # Corte
        if "Corte" in xls_gastos.sheet_names:
            df_c = pd.read_excel(xls_gastos, sheet_name="Corte")
            a, c, pl, o = clasificar_puesto(df_c)
            count_ayudante += a
            count_costurero += c
            count_planchador += pl
            count_otros += o

    except Exception as e: pass

    # LEER EXCEL SACOS
    try:
        xls_sacos = pd.ExcelFile("Análisis_Línea_Sacos.xlsx")
        for hoja in xls_sacos.sheet_names:
            df_s = pd.read_excel(xls_sacos, sheet_name=hoja)
            a, c, pl, o = clasificar_puesto(df_s)
            count_ayudante += a
            count_costurero += c
            count_planchador += pl
            count_otros += o
    except Exception as e: pass

    count_costurero += count_otros # Asignación por defecto
    
    return gastos_anuales, nomina_admin_anual, count_ayudante, count_costurero, count_planchador

# Cargar datos
gastos_fijos, nomina_admin, num_ayu, num_cos, num_plan = cargar_datos_detallados()

# --- 4. INTERFAZ ---
st.title("🏭 Suite Maquila 2026")
st.caption("Sistema de Costos Precisos con Bonos Diferenciados")

with st.sidebar:
    st.header("1. Configuración Anual")
    dias_anuales = st.number_input("Días Operativos Año", value=251, help="251 días promedio laborables")
    uma = st.number_input("UMA 2026", value=117.31)
    deduc = st.selectbox("Deducibilidad Vales", [0.53, 0.47], format_func=lambda x: f"{int(x*100)}%")
    
    st.markdown("---")
    st.header("2. Tabulador Salarial (Diario)")
    sd_ayudante = st.number_input("SD Ayudante ($)", value=316.40, help="Ajustado sobre mínimo") # <--- AJUSTADO
    sd_costurero = st.number_input("SD Costurero ($)", value=326.38)
    sd_planchador = st.number_input("SD Planchador ($)", value=326.84)
    
    st.markdown("---")
    st.header("3. Incentivos (Semanal)")
    st.caption("Asigna bonos distintos por puesto")
    
    # BONOS DIFERENCIADOS
    c_b1, c_b2 = st.columns(2)
    bono_vales_ayu = c_b1.number_input("Vales Ayudante", value=250.0)
    bono_efec_ayu = c_b2.number_input("Efec. Ayudante", value=0.0)
    
    c_b3, c_b4 = st.columns(2)
    bono_vales_cos = c_b3.number_input("Vales Costurero", value=350.0)
    bono_efec_cos = c_b4.number_input("Efec. Costurero", value=0.0)
    
    c_b5, c_b6 = st.columns(2)
    bono_vales_plan = c_b5.number_input("Vales Planchador", value=400.0)
    bono_efec_plan = c_b6.number_input("Efec. Planchador", value=0.0)

# --- CÁLCULOS UNITARIOS (PERSONALIZADOS) ---
fi_aprox = 1.0493
# Cada uno con su propio sueldo Y su propio bono
costo_u_ayu = calcular_costo_empresa_unitario(sd_ayudante, bono_vales_ayu, bono_efec_ayu, uma, fi_aprox, 0.03, deduc)
costo_u_cos = calcular_costo_empresa_unitario(sd_costurero, bono_vales_cos, bono_efec_cos, uma, fi_aprox, 0.03, deduc)
costo_u_plan = calcular_costo_empresa_unitario(sd_planchador, bono_vales_plan, bono_efec_plan, uma, fi_aprox, 0.03, deduc)

# --- PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["1. Gastos Fijos", "2. Nómina Operativa", "3. Cotizador Maquila"])

with tab1:
    st.subheader("Estructura de Costos Fijos")
    c1, c2 = st.columns(2)
    gf_user = c1.number_input("Gastos Operación Anuales", value=gastos_fijos)
    na_user = c2.number_input("Nómina Admin Anual", value=nomina_admin)
    total_fijos = gf_user + na_user
    
    st.metric("Total Fijos Anuales", f"${total_fijos:,.2f}")
    st.info(f"Costo Fijo Diario (Base {dias_anuales} días): ${total_fijos/dias_anuales:,.2f}")

with tab2:
    st.subheader("Nómina Operativa Real (Por Puesto)")
    st.caption("Calculado con Salarios y Bonos específicos para cada perfil.")
    
    colA, colB, colC = st.columns(3)
    
    # AYUDANTES
    colA.markdown(f"#### 👷 Ayudantes")
    colA.caption(f"Salario: ${sd_ayudante} | Vales: ${bono_vales_ayu}")
    n_ayu = colA.number_input("Cant. Ayudantes", value=num_ayu)
    total_ayu = n_ayu * costo_u_ayu * 12
    colA.metric("Costo Anual", f"${total_ayu:,.0f}", f"Unit Mensual: ${costo_u_ayu:,.0f}")
    
    # COSTUREROS
    colB.markdown(f"#### 🪡 Costureros")
    colB.caption(f"Salario: ${sd_costurero} | Vales: ${bono_vales_cos}")
    n_cos = colB.number_input("Cant. Costureros", value=num_cos)
    total_cos = n_cos * costo_u_cos * 12
    colB.metric("Costo Anual", f"${total_cos:,.0f}", f"Unit Mensual: ${costo_u_cos:,.0f}")
    
    # PLANCHADORES
    colC.markdown(f"#### ♨️ Planchadores")
    colC.caption(f"Salario: ${sd_planchador} | Vales: ${bono_vales_plan}")
    n_plan = colC.number_input("Cant. Planchadores", value=num_plan)
    total_plan = n_plan * costo_u_plan * 12
    colC.metric("Costo Anual", f"${total_plan:,.0f}", f"Unit Mensual: ${costo_u_plan:,.0f}")
    
    st.divider()
    total_nomina_op = total_ayu + total_cos + total_plan
    total_empleados = n_ayu + n_cos + n_plan
    
    k1, k2 = st.columns(2)
    k1.metric("PLANTILLA TOTAL", f"{total_empleados} Colaboradores")
    k2.metric("NÓMINA OPERATIVA ANUAL", f"${total_nomina_op:,.2f}")

with tab3:
    st.subheader("Cotizador de Precio (Maquila)")
    st.write(f"Cálculo basado en **{dias_anuales} días laborales** al año.")
    
    # SLIDER DE MARGEN
    margen_pct = st.slider("Margen Utilidad Deseado (%)", 0, 50, 20)
    margen = margen_pct / 100
    
    st.markdown(f"**Fórmula de Utilidad:** `Costo Operación / (1 - {margen_pct}%)`")
    
    costo_total_fabrica = total_fijos + total_nomina_op
    
    # Factores de Prorrateo (Complejidad)
    peso_saco = 0.65
    peso_pant = 0.35
    
    escenarios = [855, 900, 1000]
    data_res = []
    
    for cap in escenarios:
        prod_anual = cap * dias_anuales # 251 días
        
        if prod_anual > 0:
            # 1. Costo Unitario de Operación (Break-even)
            costo_unit_op = costo_total_fabrica / prod_anual
            
            # 2. Precio de Venta (Con Margen sobre Venta)
            # Formula: Costo / (1 - %)
            precio_promedio = costo_unit_op / (1 - margen)
            
            # Precio diferenciado
            precio_saco = (precio_promedio * 2) * peso_saco
            precio_pant = (precio_promedio * 2) * peso_pant
            
            # Utilidad Monetaria
            utilidad = (precio_promedio * prod_anual) - costo_total_fabrica
            
            data_res.append({
                "Producción Diaria": f"{cap} Trajes",
                "Prod. Anual": f"{prod_anual:,.0f}",
                "Costo Operación Unit.": f"${costo_unit_op:,.2f}",
                "PRECIO MAQUILA (JUEGO)": f"${precio_promedio:,.2f}", # EL DATO CLAVE
                "Precio Saco": f"${precio_saco:,.2f}",
                "Precio Pantalón": f"${precio_pant:,.2f}",
                "Utilidad Proyectada": f"${utilidad:,.0f}"
            })
        
    st.table(pd.DataFrame(data_res))