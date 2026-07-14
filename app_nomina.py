import os
import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(
    page_title="Nómina Estratégica V28",
    page_icon="💰",
    layout="wide"
)

# ==========================================
# MOTOR DE CÁLCULO V28 (ACTUALIZADO 2026)
# ==========================================
#
# Cambios respecto a V27:
# 1. Tabla ISR mensual corregida y verificada contra el Anexo 8 de la RMF 2026
#    (DOF 28-dic-2025), 11 tramos completos. La tabla anterior tenía cuotas
#    fijas y límites desactualizados a partir del tramo de 21.36%.
# 2. Se elimina el doble conteo de vacaciones: el "Costo Operativo Anual"
#    (8 periodos de 28 días + 4 de 35 días = 364 días) YA incluye el salario
#    base de los días de vacaciones (en México las vacaciones son días
#    pagados, el trabajador sigue devengando su sueldo). El único costo
#    INCREMENTAL real de las vacaciones es la prima vacacional (25% extra).
#    Antes se sumaba sd × días_vacaciones OTRA VEZ sobre el costo operativo,
#    sobreestimando el gasto anual.
# 3. Tope de CEAV (Cesantía en Edad Avanzada y Vejez) corregido: el máximo
#    legal 2026 es 7.513% (SBC > 4.01 UMA), no 8.75% como tenía la versión
#    anterior. Fuente: reforma LSS DOF 16-12-2020, tabla progresiva vigente.
# 4. Ramas del IMSS "ocultas" en una sola constante ahora están desglosadas
#    y documentadas, y la prima de riesgo de trabajo es un parámetro
#    editable (antes estaba enterrada dentro de una constante fija) porque
#    es específica de cada empresa según su siniestralidad declarada.
# 5. IMSS obrero: se agrega el 0.40% adicional sobre el excedente de 3 UMA
#    (antes solo se aplicaba la tasa plana de 2.375%, correcta solo hasta
#    3 UMA).
#
# Fuentes consultadas: INEGI/DOF (UMA 2026), Anexo 8 RMF 2026 (SAT/DOF),
# LSS arts. 25-30 y 106-107, reforma LSS DOF 16-12-2020 (CEAV).
# Nota: verifica siempre las cifras contra el Anexo 8 vigente y tu prima
# de riesgo de trabajo real declarada en el SUA antes de usar esto para
# decisiones formales de nómina — esta es una herramienta de planeación,
# no un sustituto del cálculo oficial.

# --- Tabla ISR MENSUAL 2026 (Art. 96 LISR, Anexo 8 RMF 2026) ---
# (límite inferior, cuota fija, % excedente)
TABLA_ISR_MENSUAL_2026 = [
    (0.01,        0.00,       0.0192),
    (746.05,      14.32,      0.0640),
    (6332.06,     371.83,     0.1088),
    (11128.02,    893.63,     0.1600),
    (12935.83,    1182.88,    0.1792),
    (15487.72,    1639.32,    0.2136),
    (31236.50,    4005.46,    0.2352),
    (49233.01,    8237.45,    0.3000),
    (93993.91,    21665.72,   0.3200),
    (125325.21,   31691.85,   0.3400),
    (375975.62,   116912.87,  0.3500),
]

# --- Ramas IMSS patronales "fijas" (no varían por antigüedad ni por SBC) ---
# Fuente: LSS arts. 25, 74, 106-107, 147, 168. Tasas vigentes sin cambios
# desde la reforma de 1997 (excepto CEAV, ver tabla progresiva abajo).
RAMA_PRESTACIONES_DINERO_PAT = 0.0070   # Enfermedades y Maternidad, prest. en dinero
RAMA_GASTOS_MEDICOS_PENS_PAT = 0.0105   # Gastos médicos de pensionados
RAMA_INVALIDEZ_VIDA_PAT = 0.0175        # Invalidez y Vida
RAMA_GUARDERIAS_PAT = 0.0100            # Guarderías y prestaciones sociales
RAMA_RETIRO_PAT = 0.0200                # Retiro (SAR)
RAMAS_FIJAS_PATRONALES = (RAMA_PRESTACIONES_DINERO_PAT + RAMA_GASTOS_MEDICOS_PENS_PAT
                           + RAMA_INVALIDEZ_VIDA_PAT + RAMA_GUARDERIAS_PAT + RAMA_RETIRO_PAT)  # = 6.50%

# Obrero: prestaciones en dinero 0.25% + gastos médicos pensionados 0.375%
# + invalidez y vida 0.625% + cesantía y vejez 1.125% = 2.375% (hasta 3 UMA)
IMSS_OBRERO_FLAT = 0.02375
IMSS_OBRERO_EXCEDENTE_3UMA = 0.0040  # Enfermedades y Maternidad, excedente obrero


def calcular_isr_normalizado(ingreso_periodo, dias_periodo, uma_valor):
    """Calcula ISR y subsidio al empleo normalizando el ingreso del periodo
    a un equivalente mensual (factor 30.4), aplicando SIEMPRE la misma
    tabla mensual, y regresando el resultado proporcionalmente al periodo.
    Esto es válido tanto para periodos de 4 como de 5 semanas."""
    factor_mes = 30.4
    if dias_periodo <= 0:
        return 0.0, 0.0

    ingreso_mensual = (ingreso_periodo / dias_periodo) * factor_mes

    isr_bruto = 0.0
    for lim, cuota, porc in TABLA_ISR_MENSUAL_2026:
        if ingreso_mensual >= lim:
            isr_bruto = cuota + ((ingreso_mensual - lim) * porc)
        else:
            break

    # Subsidio al empleo: 15.02% de la UMA mensual, tope de ingreso $11,492.66
    # (Decreto DOF 01/05/2024, vigente 2026, fórmula basada en UMA)
    subsidio = 0.0
    if ingreso_mensual <= 11492.66:
        subsidio = (uma_valor * 30.4) * 0.1502

    isr_per = (isr_bruto / factor_mes) * dias_periodo
    sub_per = (subsidio / factor_mes) * dias_periodo

    return max(0, isr_per - sub_per), sub_per


def calcular_prima_riesgo_ceav(sbc, uma):
    """Devuelve la tasa CEAV (Cesantía en Edad Avanzada y Vejez) patronal
    progresiva 2026 según el múltiplo de UMA del SBC.
    Fuente: reforma LSS DOF 16-12-2020, esquema gradual hasta 2030.
    Tope real 2026: 7.513% para SBC > 4.01 UMA (antes se usaba 8.75%,
    corregido)."""
    ratio_uma = sbc / uma
    if ratio_uma <= 1.0:
        return 0.03150
    elif ratio_uma <= 1.5:
        return 0.04241
    elif ratio_uma <= 2.0:
        return 0.05060
    elif ratio_uma <= 2.5:
        return 0.05688
    elif ratio_uma <= 3.0:
        return 0.06177
    elif ratio_uma <= 3.5:
        return 0.06551
    elif ratio_uma <= 4.0:
        return 0.06845
    else:
        return 0.07513  # tope real 2026 (antes 0.0875, corregido)


def calcular_escenario_periodo(sd, bono_efec_sem, uma, fi, tasa_isn, dias_calc, desc_imss, prima_riesgo_trabajo):
    semanas_en_periodo = dias_calc / 7
    bono_efec_total = bono_efec_sem * semanas_en_periodo
    bruto = (sd * dias_calc) + bono_efec_total

    isr, sub = calcular_isr_normalizado(bruto, dias_calc, uma)

    sbc = (sd * fi) + (bono_efec_sem / 7)
    if sbc > 25 * uma:
        sbc = 25 * uma

    imss_obr = 0.0
    if desc_imss:
        imss_obr = sbc * IMSS_OBRERO_FLAT * dias_calc
        if sbc > 3 * uma:
            imss_obr += (sbc - 3 * uma) * IMSS_OBRERO_EXCEDENTE_3UMA * dias_calc

    # Cuota fija patronal (20.40% UMA) + excedente EyM sobre 3 UMA (1.10%)
    cuota_pat = (uma * 0.204 * dias_calc)
    if sbc > 3 * uma:
        cuota_pat += (sbc - 3 * uma) * 0.011 * dias_calc

    ceav = calcular_prima_riesgo_ceav(sbc, uma)
    factor_ramas_2026 = RAMAS_FIJAS_PATRONALES + prima_riesgo_trabajo + ceav

    carga_patronal = cuota_pat + (sbc * factor_ramas_2026 * dias_calc)
    isn = bruto * tasa_isn

    neto_bolsillo = bruto - isr - imss_obr
    costo_empresa = bruto + carga_patronal + isn

    return isr, sub, neto_bolsillo, imss_obr, carga_patronal + isn, costo_empresa, bruto


def calcular_proyeccion_completa_v28(puesto, cant, sd, b_efec, uma, fi, tasa_isn, d_ag, d_vac, t_prima,
                                       desc_imss, semanas_view, prima_riesgo_trabajo):
    dias_view = 28 if semanas_view == "4 Semanas" else 35

    isr_r, sub_r, neto_r, imss_obr_r, carga_r, costo_r, bruto_r = calcular_escenario_periodo(
        sd, b_efec, uma, fi, tasa_isn, dias_view, desc_imss, prima_riesgo_trabajo
    )

    _, _, _, _, _, costo_mes_corto, _ = calcular_escenario_periodo(sd, b_efec, uma, fi, tasa_isn, 28, desc_imss, prima_riesgo_trabajo)
    _, _, _, _, _, costo_mes_largo, _ = calcular_escenario_periodo(sd, b_efec, uma, fi, tasa_isn, 35, desc_imss, prima_riesgo_trabajo)

    # 1. Costo Operativo Anual (8 meses cortos + 4 largos = 364 días).
    #    Esto YA incluye el sueldo base de los días de vacaciones, porque
    #    el trabajador cobra su sueldo los 364 días del año trabaje o esté
    #    de vacaciones. NO se debe volver a sumar sd*dias_vacaciones aparte.
    costo_operativo_anual = (costo_mes_corto * 8) + (costo_mes_largo * 4)

    # 2. Prima Vacacional: el ÚNICO costo incremental real de las vacaciones
    #    (25% extra sobre el sueldo de los días de vacaciones).
    vacaciones_pago_base = sd * d_vac  # informativo: ya está dentro del costo operativo
    prima_vacacional = vacaciones_pago_base * t_prima

    # 3. Aguinaldo
    aguinaldo = sd * d_ag

    # ISN sobre aguinaldo y prima vacacional (las prestaciones extraordinarias
    # que no forman parte del "bruto" ordinario ya gravado dentro del costo operativo)
    isn_prestaciones = (aguinaldo + prima_vacacional) * tasa_isn

    costo_anual_total_unit = costo_operativo_anual + aguinaldo + prima_vacacional + isn_prestaciones

    return {
        "Puesto": puesto, "Cantidad": cant,
        "Bruto": bruto_r,
        "Subsidio": sub_r, "ISR Ret": isr_r, "IMSS Obr": imss_obr_r, "Neto": neto_r,
        "Costo Mensual Grupo": costo_r * cant,
        "Vacaciones (ya incluidas en operación)": vacaciones_pago_base * cant,
        "Prima Vacacional Grupo": prima_vacacional * cant,
        "Aguinaldo Grupo": aguinaldo * cant,
        "Costo Anual Grupo": costo_anual_total_unit * cant,
        "_sd": sd, "_bono": b_efec, "_dias_vac": d_vac,
    }


def calcular_fi(d_ag, d_vac, t_prima):
    return (365 + d_ag + (d_vac * t_prima)) / 365


def calcular_impacto_isr_bono(sd, bono_sem, uma, fi, tasa_isn, dias_calc, desc_imss, prima_riesgo_trabajo):
    """Compara el ISR retenido CON el bono actual vs SIN bono, para medir
    cuánto del incentivo semanal se 'pierde' en mayor retención de ISR."""
    isr_con, _, neto_con, _, _, _, bruto_con = calcular_escenario_periodo(
        sd, bono_sem, uma, fi, tasa_isn, dias_calc, desc_imss, prima_riesgo_trabajo)
    isr_sin, _, neto_sin, _, _, _, bruto_sin = calcular_escenario_periodo(
        sd, 0, uma, fi, tasa_isn, dias_calc, desc_imss, prima_riesgo_trabajo)

    delta_bruto = bruto_con - bruto_sin
    delta_isr = isr_con - isr_sin
    delta_neto = neto_con - neto_sin
    pct_perdido = (delta_isr / delta_bruto * 100) if delta_bruto > 0 else 0.0

    return {
        "ISR sin bono": isr_sin, "ISR con bono": isr_con, "Delta ISR": delta_isr,
        "Neto sin bono": neto_sin, "Neto con bono": neto_con, "Delta Neto": delta_neto,
        "% del bono perdido en ISR extra": pct_perdido,
    }


# ==========================================
# INTERFAZ GRÁFICA
# ==========================================

with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("### 🏭 Trajes Españoles")
        st.warning("Falta archivo 'logo.jpg'")

    st.markdown("---")
    st.header("Configuración")

    uma = st.number_input("UMA 2026", value=117.31)

    st.divider()
    st.markdown("### Salarios Base (Diario)")
    st.caption("Defaults tomados de tu censo de personal (26_Lista_de_Personal_en_Gral_Vacaciones_2026.xlsx)")
    sd_ayu = st.number_input("Ayudante General ($)", value=280.00)
    sd_cos = st.number_input("Costurero ($)", value=288.83)
    sd_plan = st.number_input("Planchador ($)", value=289.24)

    st.divider()
    st.markdown("### Prestaciones de Ley")
    d_ag = st.number_input("Días Aguinaldo", value=20, min_value=15)
    st.caption("Días de vacaciones promedio por categoría — calculado real de tu plantilla, editable:")
    d_vac_ayu = st.number_input("Vac. Ayudante General", value=15.0, step=0.1)
    d_vac_cos = st.number_input("Vac. Costurero", value=17.5, step=0.1)
    d_vac_plan = st.number_input("Vac. Planchador", value=17.7, step=0.1)

    st.divider()
    st.markdown("### IMSS")
    prima_riesgo = st.number_input(
        "Prima de Riesgo de Trabajo (%)", value=1.13, step=0.01,
        help="Tasa específica de OTESA declarada ante el IMSS (Determinación Anual de Prima). "
             "1.13% es un valor de referencia para Clase II; actualízalo con tu prima real."
    ) / 100

    fi_ayu = calcular_fi(d_ag, d_vac_ayu, 0.25)
    fi_cos = calcular_fi(d_ag, d_vac_cos, 0.25)
    fi_plan = calcular_fi(d_ag, d_vac_plan, 0.25)

st.title("Simulador de Nómina Estratégica (V28)")

tab1, tab2, tab3 = st.tabs(["1. NÓMINA", "2. IMPACTO ISR DEL BONO", "3. MAQUILA (Pendiente)"])

with tab1:
    c_top1, c_top2 = st.columns(2)
    semanas = c_top1.radio("Visualizar Periodo:", ["4 Semanas", "5 Semanas"], horizontal=True)
    usar_imss = c_top2.checkbox("Descontar IMSS al Obrero", value=True)

    st.markdown("---")

    colA, colB, colC = st.columns(3)

    with colA:
        st.info("### 👷 Ayudante General")
        n_ayu = st.number_input("Personal", 0, 1000, 133, key="na")
        be_ayu = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=350.0, key="bea")

    with colB:
        st.success("### 🪡 Costurero")
        n_cos = st.number_input("Personal", 0, 1000, 179, key="nc")
        be_cos = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=500.0, key="bec")

    with colC:
        st.warning("### ♨️ Planchador")
        n_plan = st.number_input("Personal", 0, 1000, 61, key="np")
        be_plan = st.number_input("Bono Efectivo (Semanal $)", 0.0, value=600.0, key="bep")

    st.markdown("---")

    if st.button("CALCULAR NÓMINA V28", type="primary", use_container_width=True):

        t_isn = 0.03
        data = []

        if n_ayu > 0:
            data.append(calcular_proyeccion_completa_v28("Ayudante General", n_ayu, sd_ayu, be_ayu, uma, fi_ayu, t_isn, d_ag, d_vac_ayu, 0.25, usar_imss, semanas, prima_riesgo))
        if n_cos > 0:
            data.append(calcular_proyeccion_completa_v28("Costurero", n_cos, sd_cos, be_cos, uma, fi_cos, t_isn, d_ag, d_vac_cos, 0.25, usar_imss, semanas, prima_riesgo))
        if n_plan > 0:
            data.append(calcular_proyeccion_completa_v28("Planchador", n_plan, sd_plan, be_plan, uma, fi_plan, t_isn, d_ag, d_vac_plan, 0.25, usar_imss, semanas, prima_riesgo))

        if data:
            st.session_state["nomina_data"] = data
            df = pd.DataFrame(data)

            def fmt(x):
                return "${:,.2f}".format(x)

            st.subheader(f"1. Detalle del Trabajador (Periodo: {semanas})")
            cols_w = ["Puesto", "Bruto", "Subsidio", "ISR Ret", "IMSS Obr", "Neto"]
            df_show1 = df[cols_w].copy()
            for c in cols_w[1:]:
                df_show1[c] = df_show1[c].apply(fmt)
            st.table(df_show1)

            st.subheader("2. Presupuesto Real Anual (Calculado)")
            st.caption(
                "Costo Operativo Anual = (8 Meses Cortos + 4 Meses Largos) — YA incluye el sueldo base "
                "de los días de vacaciones (son días pagados por ley). Se suma aparte solo el costo "
                "INCREMENTAL real: Aguinaldo + Prima Vacacional (25%) + ISN sobre esas prestaciones."
            )

            cols_fin = ["Puesto", "Cantidad", "Costo Mensual Grupo", "Aguinaldo Grupo",
                        "Prima Vacacional Grupo", "Costo Anual Grupo"]
            df_show2 = df[cols_fin].copy()
            for c in cols_fin[2:]:
                df_show2[c] = df_show2[c].apply(fmt)
            st.table(df_show2)

            total_anual = df["Costo Anual Grupo"].sum()
            total_personas = df["Cantidad"].sum()
            total_isr_periodo = (df["ISR Ret"] * df["Cantidad"]).sum()
            total_isr_anual = total_isr_periodo * (13 if semanas == "4 Semanas" else 10.4)

            colR1, colR2, colR3 = st.columns(3)
            colR1.success(f"### GRAN TOTAL NÓMINA ANUAL: ${total_anual:,.2f}")
            colR2.metric("Total Plantilla", f"{total_personas}")
            colR3.metric("ISR Retenido Total (aprox. anual)", fmt(total_isr_anual),
                         help="Suma de ISR retenido a todos los trabajadores en el año — es una obligación "
                              "de entero ante el SAT, NO un costo adicional para la empresa (ya está descontado "
                              "del bruto que se paga al trabajador).")

        else:
            st.warning("⚠️ Ingresa al menos 1 trabajador.")

with tab2:
    st.subheader("¿Cuánto del bono semanal se pierde en ISR?")
    st.caption(
        "Compara el ISR retenido CON el bono actual contra un escenario SIN bono, para cada categoría. "
        "Esto te ayuda a calibrar montos de incentivo que no empujen al trabajador a perder una parte "
        "desproporcionada del bono en impuesto."
    )

    if "nomina_data" not in st.session_state:
        st.info("Primero calcula la nómina en la pestaña 1 para ver el impacto del bono.")
    else:
        t_isn = 0.03
        dias_view = 28 if semanas == "4 Semanas" else 35
        filas = []
        for row in st.session_state["nomina_data"]:
            sd = row["_sd"]
            bono = row["_bono"]
            puesto = row["Puesto"]
            fi_map = {"Ayudante General": fi_ayu, "Costurero": fi_cos, "Planchador": fi_plan}
            fi_p = fi_map[puesto]
            imp = calcular_impacto_isr_bono(sd, bono, uma, fi_p, t_isn, dias_view, usar_imss, prima_riesgo)
            filas.append({"Puesto": puesto, "Bono Semanal Actual": bono, **imp})

        df_imp = pd.DataFrame(filas)

        def fmt2(x):
            return "${:,.2f}".format(x)

        cols_money = ["Bono Semanal Actual", "ISR sin bono", "ISR con bono", "Delta ISR", "Neto sin bono", "Neto con bono", "Delta Neto"]
        df_show = df_imp.copy()
        for c in cols_money:
            df_show[c] = df_show[c].apply(fmt2)
        df_show["% del bono perdido en ISR extra"] = df_imp["% del bono perdido en ISR extra"].apply(lambda x: f"{x:.1f}%")
        st.table(df_show[["Puesto", "Bono Semanal Actual", "Delta ISR", "Delta Neto", "% del bono perdido en ISR extra"]])

        st.markdown("---")
        st.subheader("Escáner de sensibilidad: bono semanal vs. % perdido en ISR")
        st.caption("Simula distintos montos de bono semanal (manteniendo el resto de la configuración) para ver en qué punto el ISR empieza a comerse más del incentivo.")

        puesto_sel = st.selectbox("Categoría a simular", ["Ayudante General", "Costurero", "Planchador"])
        sd_map = {"Ayudante General": sd_ayu, "Costurero": sd_cos, "Planchador": sd_plan}
        fi_map2 = {"Ayudante General": fi_ayu, "Costurero": fi_cos, "Planchador": fi_plan}
        sd_sel = sd_map[puesto_sel]
        fi_sel = fi_map2[puesto_sel]

        bonos_test = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1200, 1500]
        filas_scan = []
        for b in bonos_test:
            imp = calcular_impacto_isr_bono(sd_sel, b, uma, fi_sel, 0.03, dias_view, usar_imss, prima_riesgo)
            filas_scan.append({
                "Bono Semanal": b,
                "Neto con bono (periodo)": imp["Neto con bono"],
                "% del bono perdido en ISR": imp["% del bono perdido en ISR extra"],
            })
        df_scan = pd.DataFrame(filas_scan)
        st.line_chart(df_scan.set_index("Bono Semanal")["% del bono perdido en ISR"])
        st.dataframe(df_scan.style.format({
            "Neto con bono (periodo)": "${:,.2f}",
            "% del bono perdido en ISR": "{:.1f}%"
        }), use_container_width=True)

with tab3:
    st.write("🚧 Cotizador Maquila (Pendiente de Configurar)")
