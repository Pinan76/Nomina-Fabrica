import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN ---
st.set_page_config(
    page_title="Suite Maquila 2026",
    page_icon="🏭",
    layout="wide"
)

# --- 2. MOTOR DE CÁLCULO FISCAL ---
def calcular_costo_empresa_unitario(sd, bono_vales, bono_efectivo, uma, fi, tasa_isn, factor_deducibilidad):
    dias_calculo = 30.4
    nomina_base = (sd * dias_calculo)
    bono_total_efectivo = (bono_efectivo / 7) * dias_calculo
    bono_total_vales = (bono_vales / 7) * dias_calculo
    
    tope_diario_vales = uma * 0.40
    vales_diario = bono_vales / 7
    excedente_diario = max(0, vales_diario - tope_diario_vales)
    
    sbc = (sd * fi) + (bono_efectivo/7) + excedente_diario
    if sbc > (25*uma): sbc = 25*uma
    
    cuota_patronal_base = (uma * 0.204 * dias_calculo)
    if sbc > (3*uma): cuota_patronal_base += (sbc - (3*uma)) * 0.011 * dias_calculo
    factor_ramas_imss = 0.185 
    imss_patronal = cuota_patronal_base + (sbc * factor_ramas_imss * dias_calculo)
    
    base_isn = nomina_base + bono_total_efectivo
    isn = base_isn * tasa_isn
    
    no_deducible = bono_total_vales * (1 - factor_deducibilidad)
    isr_corp_extra = no_deducible * 0.30
    
    dias_ag = 18; dias_vac = 19; tasa_prima = 0.25
    costo_anual_prestaciones = (sd * dias_ag) + (sd * dias_vac * tasa_prima)
    provision_mensual_prestaciones = costo_anual_prestaciones / 12
    
    return (nomina_base + bono_total_efectivo + bono_total_vales + 
            imss_patronal + isn + isr_corp_extra + provision_mensual_prestaciones)

# --- 3. CARGA DE DATOS (CON DIAGNÓSTICO DE ERRORES) ---
@st.cache_data
def cargar_datos_detallados():
    # Inicializamos variables en 0 para evitar Pantalla Blanca
    gastos_anuales = 0.0
    nomina_admin_anual = 0.0
    count_ayudante = 0
    count_costurero = 0
    count_planchador = 0
    count_otros = 0
    
    # Función de clasificación
    def clasificar_puesto(df):
        a, c, p, o = 0, 0, 0, 0
        if 'Puesto' in df.columns:
            puestos = df['Puesto'].astype(str).str.upper()
            a = puestos.str.contains('AYUDANTE').sum()
            p = puestos.str.contains('PLANCHADOR').sum()
            c = puestos.str.contains('COSTURERO').sum() + puestos.str.contains('COSTURERA').sum()
            total_validos = len(df)
            detectados = a + c + p
            if detectados < total_validos: o = total_validos - detectados
        return a, c, p, o

    # INTENTO 1: LEER GASTOS_2025.XLSX
    try:
        xls_gastos = pd.ExcelFile("Gastos_2025.xlsx")
        
        # Gastos Fijos
        if "Control_Gastos" in xls_gastos.sheet_names:
            df_g = pd.read_excel(xls_gastos, sheet_name="Control_Gastos")
            gastos_anuales = pd.to_numeric(df_g['Gasto Anual'], errors='coerce').sum()
        else:
            st.error("❌ No encuentro la pestaña 'Control_Gastos' en Gastos_2025.xlsx")
            
        # Nómina Admin
        if "Sueldos Admin" in xls_gastos.sheet_names:
            df_a = pd.read_excel(xls_gastos, sheet_name="Sueldos Admin", skiprows=2)
            nomina_admin_mensual = pd.to_numeric(df_a.iloc[:, -1], errors='coerce').sum()
            nomina_admin_anual = nomina_admin_mensual * 12
        else:
            st.error("❌ No encuentro la pestaña 'Sueldos Admin' en Gastos_2025.xlsx")
            
        # Pantalón
        sheet_pant = next((s for s in xls_gastos.sheet_names if "Pantalon" in s or "Pantalón" in s), None)
        if sheet_pant:
            df_p = pd.read_excel(xls_gastos, sheet_name=sheet_pant)
            a, c, pl, o = clasificar_puesto(df_p)
            count_ayudante += a; count_costurero += c; count_planchador += pl; count_otros += o
            
        # Corte
        if "Corte" in xls_gastos.sheet_names:
            df_c = pd.read_excel(xls_gastos, sheet_name="Corte")
            a, c, pl, o = clasificar_puesto(df_c)
            count_ayudante += a; count_costurero += c; count_planchador += pl; count_otros += o

    except FileNotFoundError:
        st.error("🚨 CRÍTICO: No encuentro el archivo 'Gastos_2025.xlsx' en GitHub.")
    except Exception as e:
        st.error(f"🚨 Error leyendo Gastos_2025.xlsx: {e}")

    # INTENTO 2: LEER ANÁLISIS_LÍNEA_SACOS.XLSX
    try:
        xls_sacos = pd.ExcelFile("Análisis_Línea_Sacos.xlsx")
        for hoja in xls_sacos.sheet_names:
            df_s = pd.read_excel(xls_sacos, sheet_name=hoja)
            a, c, pl, o = clasificar_puesto(df_s)
            count_ayudante += a; count_costurero += c; count_planchador += pl; count_otros += o
    except FileNotFoundError:
        st.error("🚨 CRÍTICO: No encuentro el archivo 'Análisis_Línea_Sacos.xlsx' en GitHub.")
    except Exception as e:
        # No mostramos error si falla una hoja, solo si falla todo el archivo
        pass

    count_costurero += count_otros 
    
    return gastos_anuales, nomina_admin_anual, count_ayudante, count_costurero, count_planchador

# Cargar datos
gastos_fijos, nomina_admin, num_ayu, num_cos, num_plan = cargar_datos_detallados()

# --- 4. INTERFAZ ---
st.title("🏭 Suite Maquila 2026")

with st.sidebar:
    st.header("1. Configuración")
    dias_anuales = st.number_input("Días Operativos", value=251)
    uma = st.number_input("UMA 2026", value=117.31)
    deduc = st.selectbox("Deducibilidad Vales", [0.53, 0.47], format_func=lambda x: f"{int(x*100)}%")
    
    st.markdown("---")
    st.header("2. Tabulador Salarial")
    sd_ayudante = st.number_input("SD Ayudante ($)", value=316.40)
    sd_costurero = st.number_input("SD Costurero ($)", value=326.38)
    sd_planchador = st.number_input("SD Planchador ($)", value=326.84)
    
    st.markdown("---")
    st.header("3. Incentivos")
    c_b1, c_b2 = st.columns(2)
    bono_vales_ayu = c_b1.number_input("Vales Ayu", value=250.0)
    bono_efec_ayu = c_b2.number_input("Efec. Ayu", value=0.0)
    c_b3, c_b4 = st.columns(2)
    bono_vales_cos = c_b3.number_input("Vales Cos", value=350.0)
    bono_efec_cos = c_b4.number_input("Efec. Cos", value=0.0)
    c_b5, c_b6 = st.columns(2)
    bono_vales_plan = c_b5.number_input("Vales Plan", value=400.0)
    bono_efec_plan = c_b6.number_input("Efec. Plan", value=0.0)

# Cálculos
fi = 1.0493
costo_u_ayu = calcular_costo_empresa_unitario(sd_ayudante, bono_vales_ayu, bono_efec_ayu, uma, fi, 0.03, deduc)
costo_u_cos = calcular_costo_empresa_unitario(sd_costurero, bono_vales_cos, bono_efec_cos, uma, fi, 0.03, deduc)
costo_u_plan = calcular_costo_empresa_unitario(sd_planchador, bono_vales_plan, bono_efec_plan, uma, fi, 0.03, deduc)

tab1, tab2, tab3 = st.tabs(["1. Gastos Fijos", "2. Nómina Operativa", "3. Cotizador Maquila"])

with tab1:
    st.subheader("Costos Fijos")
    if gastos_fijos == 0: st.warning("⚠️ No se leyeron Gastos Fijos (Verifica el Excel)")
    
    col1, col2 = st.columns(2)
    gf = col1.number_input("Gastos Operación", value=gastos_fijos)
    na = col2.number_input("Nómina Admin", value=nomina_admin)
    st.metric("Total Fijos", f"${gf+na:,.2f}")

with tab2:
    st.subheader("Nómina Operativa")
    c1, c2, c3 = st.columns(3)
    
    n_ayu = c1.number_input("Ayudantes", value=num_ayu)
    c1.metric("Costo Anual", f"${n_ayu * costo_u_ayu * 12:,.0f}")
    
    n_cos = c2.number_input("Costureros", value=num_cos)
    c2.metric("Costo Anual", f"${n_cos * costo_u_cos * 12:,.0f}")
    
    n_plan = c3.number_input("Planchadores", value=num_plan)
    c3.metric("Costo Anual", f"${n_plan * costo_u_plan * 12:,.0f}")
    
    total_op = (n_ayu * costo_u_ayu * 12) + (n_cos * costo_u_cos * 12) + (n_plan * costo_u_plan * 12)
    st.metric("TOTAL NÓMINA OP", f"${total_op:,.2f}")

with tab3:
    st.subheader("Cotizador")
    margen = st.slider("Margen %", 0, 50, 20) / 100
    costo_total = (gf + na) + total_op
    
    escenarios = [855, 900, 1000]
    res = []
    for cap in escenarios:
        prod_anual = cap * dias_anuales
        if prod_anual > 0:
            costo_u = costo_total / prod_anual
            precio = costo_u / (1 - margen)
            res.append({
                "Prod. Diaria": cap,
                "Costo Unit": f"${costo_u:,.2f}",
                "PRECIO": f"${precio:,.2f}",
                "Utilidad": f"${(precio*prod_anual)-costo_total:,.0f}"
            })
    st.table(pd.DataFrame(res))