import os
import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(
    page_title="Nómina Estratégica V29",
    page_icon="💰",
    layout="wide"
)

# ==========================================
# MOTOR DE CÁLCULO V29
# ==========================================
#
# Cambios respecto a V28, todos derivados de cruzar 27 semanas de hojas de
# captura de incentivos + ~35 recibos CFDI reales de nómina:
#
# 1. BUG CORREGIDO: los defaults de salario base en el sidebar de la V28
#    seguían en $280.00 / $288.83 / $289.24 (del censo, desactualizado),
#    a pesar de que se había confirmado con MÚLTIPLES recibos CFDI reales
#    (Sueldo ÷ 6 días) que los salarios vigentes son $316.40 / $326.38 /
#    $326.84. Ese error nunca se aplicó al código, solo se mencionó en
#    conversación. Ya corregido aquí.
#
# 2. NUEVO: "Ayuda de Transporte" ahora es un input explícito, con un
#    toggle GRAVADO (percepción en efectivo, como hoy en tus recibos) vs
#    EXENTO (servicio de transporte de personal pagado directo al
#    transportista + descuento de nómina al trabajador — la figura que
#    discutimos). El toggle cambia si ese monto entra o no a la base de
#    ISR, porque es justo la diferencia que puede darte ~10-15 puntos de
#    margen antes de cruzar el límite del subsidio.
#
# 3. NUEVO — el cambio más importante: el motor ahora calcula el ISR de
#    DOS formas y las muestra juntas:
#       a) "ISR retenido semana a semana" (aislado, lo que ves en cada
#          recibo durante el mes)
#       b) "ISR real del mes" (agregando las 4 o 5 semanas y aplicando la
#          tabla mensual UNA sola vez, con el subsidio como todo-o-nada)
#    La diferencia entre (b) y (a) es el "ajuste de cierre de mes" que
#    confirmaste que CONTPAQi está aplicando. La V28 solo mostraba (a),
#    que subestima el costo real de subir el incentivo — sobre todo cerca
#    del límite de $11,492.66/mes.
#
# 4. NUEVO: la Tabla de Incentivos real (4 Clases × 3 Tiers = 12 montos)
#    ahora es editable en vez de un solo "Bono Efectivo Semanal" plano.
#
# 5. NUEVO: pestaña "Simulador de Acantilado" — muestra, para cada
#    categoría y cada tier de la tabla, si el trabajador se mantiene
#    dentro o fuera del límite del subsidio en meses de 4 y de 5 semanas,
#    y el efecto exacto en neto de cruzar esa línea (el ejemplo real:
#    +$80 de bruto al mes puede significar -$468 de neto si cruza).
#
# Se mantiene todo lo ya corregido en V28 (tabla ISR 2026 de 11 tramos,
# CEAV tope 7.513%, sin doble conteo de vacaciones, IMSS obrero con
# excedente de 3 UMA, ramas patronales desglosadas).
#
# PENDIENTE DE CONFIRMAR CON TU CONTADOR (no modelable con certeza sin su
# confirmación): el mecanismo EXACTO del ajuste de cierre de mes. Aquí se
# modela como "agregado mensual con subsidio todo-o-nada", que es
# consistente con los montos reales que viste en tus recibos (múltiplos
# exactos de $123.47), pero la forma en que CONTPAQi lo distribuye o si
# hay matices adicionales debe confirmarse antes de usar estos números
# para decisiones finales.

# --- Tabla ISR MENSUAL 2026 (Art. 96 LISR, Anexo 8 RMF 2026) ---
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

LIMITE_MENSUAL_SUBSIDIO = 11492.66  # tope de ingreso mensual para conservar el subsidio al empleo
SUBSIDIO_MENSUAL_FORMULA = lambda uma: (uma * 30.4) * 0.1502  # 15.02% de la UMA mensual

RAMA_PRESTACIONES_DINERO_PAT = 0.0070
RAMA_GASTOS_MEDICOS_PENS_PAT = 0.0105
RAMA_INVALIDEZ_VIDA_PAT = 0.0175
RAMA_GUARDERIAS_PAT = 0.0100
RAMA_RETIRO_PAT = 0.0200
RAMAS_FIJAS_PATRONALES = (RAMA_PRESTACIONES_DINERO_PAT + RAMA_GASTOS_MEDICOS_PENS_PAT
                           + RAMA_INVALIDEZ_VIDA_PAT + RAMA_GUARDERIAS_PAT + RAMA_RETIRO_PAT)

IMSS_OBRERO_FLAT = 0.02375
IMSS_OBRERO_EXCEDENTE_3UMA = 0.0040

# Tabla de Incentivos real de OTESA (Clase x Tier de eficiencia), valores
# tomados de Tabla_de_Incentivos.xlsx y verificados contra recibos reales.
TABLA_INCENTIVOS_DEFAULT = {
    'C':  {0.8: 113, 0.9: 169, 1.0: 198},
    'B':  {0.8: 226, 0.9: 311, 1.0: 339},
    'A':  {0.8: 340, 0.9: 397, 1.0: 424},
    'AA': {0.8: 453, 0.9: 481, 1.0: 509},
}


def calcular_isr_normalizado(ingreso_periodo, dias_periodo, uma_valor):
    """ISR retenido tratando el periodo de forma AISLADA (elevación
    proporcional a mes vía factor 30.4). Esto es lo que se ve en cada
    recibo semanal individual, ANTES del ajuste de cierre de mes."""
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
    subsidio = SUBSIDIO_MENSUAL_FORMULA(uma_valor) if ingreso_mensual <= LIMITE_MENSUAL_SUBSIDIO else 0.0
    isr_per = (isr_bruto / factor_mes) * dias_periodo
    sub_per = (subsidio / factor_mes) * dias_periodo
    return max(0, isr_per - sub_per), sub_per


def calcular_isr_mensual_real(ingreso_mensual_real, uma_valor):
    """ISR verdadero del mes: aplica la tabla mensual UNA sola vez sobre
    el ingreso mensual real acumulado (suma de las 4 o 5 semanas), con el
    subsidio como todo-o-nada según el límite de $11,492.66. Esto es lo
    que el ajuste de cierre de mes termina forzando, confirmado contra
    tus recibos reales."""
    isr_bruto = 0.0
    for lim, cuota, porc in TABLA_ISR_MENSUAL_2026:
        if ingreso_mensual_real >= lim:
            isr_bruto = cuota + ((ingreso_mensual_real - lim) * porc)
        else:
            break
    subsidio = SUBSIDIO_MENSUAL_FORMULA(uma_valor) if ingreso_mensual_real <= LIMITE_MENSUAL_SUBSIDIO else 0.0
    return max(0, isr_bruto - subsidio), subsidio


def calcular_prima_riesgo_ceav(sbc, uma):
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
        return 0.07513


def calcular_escenario_periodo(sd, bono_efec_sem, transporte_sem, transporte_gravado, uma, fi, tasa_isn,
                                dias_calc, desc_imss, prima_riesgo_trabajo):
    semanas_en_periodo = dias_calc / 7
    bono_total = bono_efec_sem * semanas_en_periodo
    transporte_total = transporte_sem * semanas_en_periodo

    # El ingreso GRAVABLE para ISR incluye el transporte solo si está marcado
    # como "gravado" (percepción en efectivo). Si es "exento" (servicio de
    # transporte de personal pagado directo al proveedor), no entra aquí.
    bruto_gravable = (sd * dias_calc) + bono_total + (transporte_total if transporte_gravado else 0)
    # El "bruto total percibido" para efectos de reporte SÍ incluye el
    # transporte siempre (es valor que recibe el trabajador, gravado o no).
    bruto_total_percibido = (sd * dias_calc) + bono_total + transporte_total

    isr, sub = calcular_isr_normalizado(bruto_gravable, dias_calc, uma)

    sbc = (sd * fi) + (bono_efec_sem / 7)
    if transporte_gravado:
        sbc += (transporte_sem / 7)
    if sbc > 25 * uma:
        sbc = 25 * uma

    imss_obr = 0.0
    if desc_imss:
        imss_obr = sbc * IMSS_OBRERO_FLAT * dias_calc
        if sbc > 3 * uma:
            imss_obr += (sbc - 3 * uma) * IMSS_OBRERO_EXCEDENTE_3UMA * dias_calc

    cuota_pat = (uma * 0.204 * dias_calc)
    if sbc > 3 * uma:
        cuota_pat += (sbc - 3 * uma) * 0.011 * dias_calc

    ceav = calcular_prima_riesgo_ceav(sbc, uma)
    factor_ramas_2026 = RAMAS_FIJAS_PATRONALES + prima_riesgo_trabajo + ceav

    carga_patronal = cuota_pat + (sbc * factor_ramas_2026 * dias_calc)
    isn = bruto_gravable * tasa_isn

    neto_bolsillo = bruto_total_percibido - isr - imss_obr
    costo_empresa = bruto_total_percibido + carga_patronal + isn

    return isr, sub, neto_bolsillo, imss_obr, carga_patronal + isn, costo_empresa, bruto_gravable, bruto_total_percibido


def calcular_proyeccion_completa_v29(puesto, cant, sd, b_efec, transporte_sem, transporte_gravado,
                                       uma, fi, tasa_isn, d_ag, d_vac, t_prima,
                                       desc_imss, semanas_view, prima_riesgo_trabajo):
    dias_view = 28 if semanas_view == "4 Semanas" else 35

    (isr_r, sub_r, neto_r, imss_obr_r, carga_r, costo_r,
     bruto_grav_r, bruto_tot_r) = calcular_escenario_periodo(
        sd, b_efec, transporte_sem, transporte_gravado, uma, fi, tasa_isn, dias_view, desc_imss, prima_riesgo_trabajo
    )

    _, _, _, _, _, costo_mes_corto, _, _ = calcular_escenario_periodo(
        sd, b_efec, transporte_sem, transporte_gravado, uma, fi, tasa_isn, 28, desc_imss, prima_riesgo_trabajo)
    _, _, _, _, _, costo_mes_largo, _, _ = calcular_escenario_periodo(
        sd, b_efec, transporte_sem, transporte_gravado, uma, fi, tasa_isn, 35, desc_imss, prima_riesgo_trabajo)

    costo_operativo_anual = (costo_mes_corto * 8) + (costo_mes_largo * 4)
    vacaciones_pago_base = sd * d_vac
    prima_vacacional = vacaciones_pago_base * t_prima
    aguinaldo = sd * d_ag
    isn_prestaciones = (aguinaldo + prima_vacacional) * tasa_isn
    costo_anual_total_unit = costo_operativo_anual + aguinaldo + prima_vacacional + isn_prestaciones

    return {
        "Puesto": puesto, "Cantidad": cant,
        "Bruto Gravable": bruto_grav_r, "Bruto Total": bruto_tot_r,
        "Subsidio": sub_r, "ISR Ret": isr_r, "IMSS Obr": imss_obr_r, "Neto": neto_r,
        "Costo Mensual Grupo": costo_r * cant,
        "Prima Vacacional Grupo": prima_vacacional * cant,
        "Aguinaldo Grupo": aguinaldo * cant,
        "Costo Anual Grupo": costo_anual_total_unit * cant,
        "_sd": sd, "_bono": b_efec, "_transporte": transporte_sem, "_transp_gravado": transporte_gravado,
    }


def calcular_fi(d_ag, d_vac, t_prima):
    return (365 + d_ag + (d_vac * t_prima)) / 365


def margen_semanal_antes_de_cruzar(sd, transporte_sem, transporte_gravado, n_semanas, uma):
    """Cuántos pesos de incentivo POR SEMANA puede recibir un trabajador
    de este puesto antes de que el ingreso mensual acumulado cruce el
    límite del subsidio al empleo. Negativo = ya lo cruzó sin incentivo."""
    base_semana = sd * 7
    transp_grav = transporte_sem if transporte_gravado else 0
    base_mensual_gravable = (base_semana + transp_grav) * n_semanas
    margen_total = LIMITE_MENSUAL_SUBSIDIO - base_mensual_gravable
    return margen_total / n_semanas


# ==========================================
# INTERFAZ GRÁFICA
# ==========================================

with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("### 🏭 Trajes Españoles")
        st.warning("Falta archivo 'logo.png'")

    st.markdown("---")
    st.header("Configuración")

    uma = st.number_input("UMA 2026", value=117.31)

    st.divider()
    st.markdown("### Salarios Base (Diario)")
    st.caption("✅ Confirmados contra múltiples recibos CFDI reales (Sueldo ÷ 6 días). "
               "El censo (280 / 288.83 / 289.24) estaba desactualizado — NO lo uses.")
    sd_ayu = st.number_input("Ayudante General ($)", value=316.40)
    sd_cos = st.number_input("Costurero ($)", value=326.38)
    sd_plan = st.number_input("Planchador ($)", value=326.84)

    st.divider()
    st.markdown("### Ayuda de Transporte")
    transp_gravado = st.radio(
        "Tratamiento fiscal del transporte",
        ["Gravado (efectivo, como hoy)", "Exento (servicio de personal — pendiente de formalizar)"],
        help="Exento requiere: el transportista factura a OTESA (no al trabajador), el servicio se "
             "ofrece de forma general (no como opción de efectivo), y el descuento al trabajador se "
             "documenta como deducción de nómina con su autorización por escrito. Confírmalo con tu contador."
    ) == "Gravado (efectivo, como hoy)"
    transporte_prom = st.number_input(
        "Transporte semanal promedio ($)", value=55.0, step=1.0,
        help="En tus recibos reales vimos un rango de $24 a $180 por persona — este es solo un promedio "
             "de referencia. Alguien con transporte alto tiene menos margen del que muestra este promedio."
    )

    st.divider()
    st.markdown("### Prestaciones de Ley")
    d_ag = st.number_input("Días Aguinaldo", value=20, min_value=15)
    st.caption("Días de vacaciones promedio por categoría (real de tu plantilla, editable):")
    d_vac_ayu = st.number_input("Vac. Ayudante General", value=15.0, step=0.1)
    d_vac_cos = st.number_input("Vac. Costurero", value=17.5, step=0.1)
    d_vac_plan = st.number_input("Vac. Planchador", value=17.7, step=0.1)

    st.divider()
    st.markdown("### IMSS")
    prima_riesgo = st.number_input(
        "Prima de Riesgo de Trabajo (%)", value=1.13, step=0.01,
        help="1.13% es referencia Clase II. Actualízalo con tu prima real declarada en el SUA."
    ) / 100

    fi_ayu = calcular_fi(d_ag, d_vac_ayu, 0.25)
    fi_cos = calcular_fi(d_ag, d_vac_cos, 0.25)
    fi_plan = calcular_fi(d_ag, d_vac_plan, 0.25)

st.title("Simulador de Nómina Estratégica (V29)")

tab1, tab2, tab3, tab4 = st.tabs([
    "1. NÓMINA", "2. TABLA DE INCENTIVOS", "3. SIMULADOR DE ACANTILADO", "4. MAQUILA (Pendiente)"
])

SD_MAP = {"Ayudante General": sd_ayu, "Costurero": sd_cos, "Planchador": sd_plan}
FI_MAP = {"Ayudante General": fi_ayu, "Costurero": fi_cos, "Planchador": fi_plan}

with tab1:
    c_top1, c_top2 = st.columns(2)
    semanas = c_top1.radio("Visualizar Periodo:", ["4 Semanas", "5 Semanas"], horizontal=True)
    usar_imss = c_top2.checkbox("Descontar IMSS al Obrero", value=True)

    st.markdown("---")
    colA, colB, colC = st.columns(3)
    with colA:
        st.info("### 👷 Ayudante General")
        n_ayu = st.number_input("Personal", 0, 1000, 133, key="na")
        be_ayu = st.number_input("Bono Efectivo Promedio (Semanal $)", 0.0, value=250.0, key="bea")
    with colB:
        st.success("### 🪡 Costurero")
        n_cos = st.number_input("Personal", 0, 1000, 179, key="nc")
        be_cos = st.number_input("Bono Efectivo Promedio (Semanal $)", 0.0, value=300.0, key="bec")
    with colC:
        st.warning("### ♨️ Planchador")
        n_plan = st.number_input("Personal", 0, 1000, 61, key="np")
        be_plan = st.number_input("Bono Efectivo Promedio (Semanal $)", 0.0, value=350.0, key="bep")

    st.caption("Sugerencia: usa el promedio real de incentivo pagado por categoría, no el tier máximo — "
               "en tus 27 semanas de datos, el promedio real fue ~$165 (Ayudante), ~$229 (Costurero), ~$276 (Planchador).")

    st.markdown("---")

    if st.button("CALCULAR NÓMINA V29", type="primary", use_container_width=True):
        t_isn = 0.03
        data = []
        if n_ayu > 0:
            data.append(calcular_proyeccion_completa_v29("Ayudante General", n_ayu, sd_ayu, be_ayu, transporte_prom, transp_gravado, uma, fi_ayu, t_isn, d_ag, d_vac_ayu, 0.25, usar_imss, semanas, prima_riesgo))
        if n_cos > 0:
            data.append(calcular_proyeccion_completa_v29("Costurero", n_cos, sd_cos, be_cos, transporte_prom, transp_gravado, uma, fi_cos, t_isn, d_ag, d_vac_cos, 0.25, usar_imss, semanas, prima_riesgo))
        if n_plan > 0:
            data.append(calcular_proyeccion_completa_v29("Planchador", n_plan, sd_plan, be_plan, transporte_prom, transp_gravado, uma, fi_plan, t_isn, d_ag, d_vac_plan, 0.25, usar_imss, semanas, prima_riesgo))

        if data:
            st.session_state["nomina_data"] = data
            df = pd.DataFrame(data)

            def fmt(x):
                return "${:,.2f}".format(x)

            st.subheader(f"1. Detalle del Trabajador (Periodo: {semanas})")
            cols_w = ["Puesto", "Bruto Total", "Subsidio", "ISR Ret", "IMSS Obr", "Neto"]
            df_show1 = df[cols_w].copy()
            for c in cols_w[1:]:
                df_show1[c] = df_show1[c].apply(fmt)
            st.table(df_show1)
            st.caption("⚠️ ISR Ret aquí es el retenido SEMANA A SEMANA de forma aislada. Ve a la pestaña "
                       "'Simulador de Acantilado' para ver el ISR real del mes completo, que puede ser mayor.")

            st.subheader("2. Presupuesto Real Anual (Calculado)")
            cols_fin = ["Puesto", "Cantidad", "Costo Mensual Grupo", "Aguinaldo Grupo",
                        "Prima Vacacional Grupo", "Costo Anual Grupo"]
            df_show2 = df[cols_fin].copy()
            for c in cols_fin[2:]:
                df_show2[c] = df_show2[c].apply(fmt)
            st.table(df_show2)

            total_anual = df["Costo Anual Grupo"].sum()
            total_personas = df["Cantidad"].sum()
            colR1, colR2 = st.columns(2)
            colR1.success(f"### GRAN TOTAL NÓMINA ANUAL: ${total_anual:,.2f}")
            colR2.metric("Total Plantilla", f"{total_personas}")
        else:
            st.warning("⚠️ Ingresa al menos 1 trabajador.")

with tab2:
    st.subheader("Tabla de Incentivos (Clase × Nivel de Eficiencia)")
    st.caption("Edita los montos para simular incrementos. Los defaults son tu tabla vigente.")

    tabla_editada = {}
    cols = st.columns(4)
    for i, clase in enumerate(['C', 'B', 'A', 'AA']):
        with cols[i]:
            st.markdown(f"**Clase {clase}**")
            tabla_editada[clase] = {}
            for tier in [0.8, 0.9, 1.0]:
                tabla_editada[clase][tier] = st.number_input(
                    f"{int(tier*100)}% eficiencia", value=float(TABLA_INCENTIVOS_DEFAULT[clase][tier]),
                    key=f"tabla_{clase}_{tier}", step=1.0
                )

    st.session_state["tabla_incentivos"] = tabla_editada

    st.markdown("---")
    st.caption("Esta tabla se usa en la pestaña 'Simulador de Acantilado' para revisar cada combinación "
               "Clase × Tier contra el límite mensual del subsidio, por categoría de puesto.")

with tab3:
    st.subheader("¿Qué tiers de tu Tabla de Incentivos cruzan el límite del subsidio?")
    st.caption(
        f"Límite mensual del subsidio al empleo: ${LIMITE_MENSUAL_SUBSIDIO:,.2f}. Si el ingreso gravable "
        "del mes lo supera, el trabajador pierde TODO el subsidio de ese mes (no es gradual) — y en la "
        "última semana del mes se le recupera de golpe lo que se le había dado."
    )

    tabla_uso = st.session_state.get("tabla_incentivos", TABLA_INCENTIVOS_DEFAULT)

    st.markdown("### Margen disponible por categoría (antes de sumar el incentivo)")
    filas_margen = []
    for puesto, sd in SD_MAP.items():
        for n in [4, 5]:
            margen = margen_semanal_antes_de_cruzar(sd, transporte_prom, transp_gravado, n, uma)
            filas_margen.append({"Puesto": puesto, "Mes de": f"{n} semanas", "Margen semanal antes de incentivo": margen})
    df_margen = pd.DataFrame(filas_margen).pivot(index="Puesto", columns="Mes de", values="Margen semanal antes de incentivo")
    st.dataframe(df_margen.style.format("${:,.2f}"), use_container_width=True)
    st.caption("Negativo = ya se cruza el límite solo con sueldo + transporte, antes de un solo peso de incentivo.")

    st.markdown("---")
    st.markdown("### Semáforo: cada combinación Clase/Tier de tu tabla, por categoría y longitud de mes")

    filas_semaforo = []
    for puesto, sd in SD_MAP.items():
        for n in [4, 5]:
            margen = margen_semanal_antes_de_cruzar(sd, transporte_prom, transp_gravado, n, uma)
            for clase, tiers in tabla_uso.items():
                for tier, monto in tiers.items():
                    cruza = monto > margen
                    filas_semaforo.append({
                        "Puesto": puesto, "Mes": f"{n} sem", "Clase": clase, "Tier": f"{int(tier*100)}%",
                        "Incentivo/sem": monto, "Estado": "🔴 Cruza — pierde subsidio" if cruza else "🟢 Mantiene subsidio"
                    })
    df_sem = pd.DataFrame(filas_semaforo)
    puesto_filtro = st.selectbox("Filtrar por categoría", list(SD_MAP.keys()), key="filtro_semaforo")
    st.dataframe(df_sem[df_sem["Puesto"] == puesto_filtro].drop(columns="Puesto"), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### El acantilado en números: comparación directa antes/después de cruzar")
    st.caption("Elige una categoría y compara el neto mensual justo antes vs. justo después del límite.")

    puesto_cliff = st.selectbox("Categoría", list(SD_MAP.keys()), key="puesto_cliff")
    sd_cliff = SD_MAP[puesto_cliff]
    n_cliff = st.radio("Longitud del mes", [4, 5], horizontal=True, key="n_cliff")
    incentivo_cliff = st.slider("Incentivo semanal a simular ($)", 0, 900, 400, step=10, key="incentivo_cliff")

    base_semana = sd_cliff * 7
    transp_grav_cliff = transporte_prom if transp_gravado else 0
    bruto_mes = (base_semana + transp_grav_cliff) * n_cliff + incentivo_cliff * n_cliff
    isr_mes, sub_mes = calcular_isr_mensual_real(bruto_mes, uma)
    bruto_total_percibido = (base_semana + transporte_prom) * n_cliff + incentivo_cliff * n_cliff
    neto_mes = bruto_total_percibido - isr_mes

    cruzo = bruto_mes > LIMITE_MENSUAL_SUBSIDIO
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingreso gravable del mes", f"${bruto_mes:,.2f}")
    col2.metric("Subsidio del mes", f"${sub_mes:,.2f}", delta="Perdido" if cruzo else "Conservado", delta_color="inverse" if cruzo else "normal")
    col3.metric("Neto del mes (estimado)", f"${neto_mes:,.2f}")

    if cruzo:
        st.error(f"⚠️ Este escenario CRUZA el límite por ${bruto_mes - LIMITE_MENSUAL_SUBSIDIO:,.2f}. "
                 f"El trabajador pierde el subsidio completo del mes (~${SUBSIDIO_MENSUAL_FORMULA(uma):,.2f}).")
    else:
        st.success(f"✅ Este escenario se mantiene ${LIMITE_MENSUAL_SUBSIDIO - bruto_mes:,.2f} por debajo del límite. Subsidio conservado.")

with tab4:
    st.write("🚧 Cotizador Maquila (Pendiente de Configurar)")
