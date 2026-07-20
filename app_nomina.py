import os
import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN VISUAL ---
st.set_page_config(
    page_title="Nómina Estratégica V30",
    page_icon="💰",
    layout="wide"
)

# ==========================================
# MOTOR DE CÁLCULO V30
# ==========================================
#
# Cambios respecto a V29 (dos correcciones importantes, ambas pedidas
# explícitamente tras revisar el reporte real "Partes Gravadas para ISR
# por empleado" de CONTPAQi):
#
# 1. NUEVO: Aportación Patronal de INFONAVIT (5% del SBC) — no estaba
#    incluida en ninguna versión anterior. Es una contribución obligatoria
#    y separada de las cuotas IMSS (se recauda junto vía SUA, pero va a un
#    fondo distinto). Ya está sumada a la carga patronal.
#
# 2. CORREGIDO — el cambio más importante: la fórmula del "Sueldo
#    Mensualizado" (la que decide si se conserva o se pierde el subsidio al
#    cierre de mes) estaba mal. La versión anterior comparaba la SUMA REAL
#    de las semanas del mes contra el límite de $11,492.66. La fórmula real
#    de CONTPAQi, validada letra por letra contra el reporte de junio 2026,
#    es distinta:
#
#        Sueldo Mensualizado = (Total Percepciones Gravables del periodo
#                                ÷ Días Trabajados) × 30.4
#
#    Esto tiene dos consecuencias importantes:
#      a) El margen semanal seguro es MÁS CHICO de lo que se había calculado
#         antes ($376.54 Ayudante / $306.68 Costurero / $303.46 Planchador,
#         con transporte gravado de referencia $55/semana — antes se
#         reportaban cifras de $530-603).
#      b) El margen YA NO DEPENDE de si el mes tiene 4 o 5 semanas — el
#         factor 30.4 normaliza por día, no por mes calendario. Es el MISMO
#         margen semanal siempre. La idea de que "los meses de 5 semanas
#         son estructuralmente peores" (de versiones anteriores de este
#         análisis) queda descartada: el margen siempre fue así de
#         estrecho, todo el año — lo que pasa en meses de 5 semanas es que
#         se pierde MÁS SUBSIDIO EN PESOS al cruzar (5 semanas × $123.47 en
#         vez de 4), no que sea más fácil cruzar.
#
#    Esta corrección explica, con mucho mejor ajuste, la tasa real de
#    pérdida de subsidio observada en el reporte de junio 2026 (30.4% de
#    373 sindicalizados, hasta 60.8% en Planchador) — con el margen viejo
#    (más generoso) esa tasa de pérdida no debería ser tan alta.
#
# Se mantiene todo lo ya corregido en V28/V29 (tabla ISR 2026 de 11 tramos,
# CEAV tope 7.513%, sin doble conteo de vacaciones, IMSS obrero con
# excedente de 3 UMA, ramas patronales desglosadas, transporte
# gravado/exento, Tabla de Incentivos editable).
#
# IMPORTANTE: esta corrección invalida el margen usado para diseñar la
# "Tabla Intermedia" y los niveles 110%/120% de la tabla de transición
# propuestos en el chat — ambos se diseñaron con el margen viejo (más
# generoso) y deben revisarse contra el margen correcto antes de usarse
# en una decisión final.

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
INFONAVIT_PATRONAL = 0.0500  # Aportación patronal INFONAVIT, 5% del SBC (obligatoria, separada del IMSS)
RAMAS_FIJAS_PATRONALES = (RAMA_PRESTACIONES_DINERO_PAT + RAMA_GASTOS_MEDICOS_PENS_PAT
                           + RAMA_INVALIDEZ_VIDA_PAT + RAMA_GUARDERIAS_PAT + RAMA_RETIRO_PAT
                           + INFONAVIT_PATRONAL)

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


def calcular_isr_mensual_real(total_percepciones_gravables, dias_trabajados, uma_valor):
    """ISR verdadero del mes — CORREGIDO. Fórmula validada letra por letra
    contra el reporte real de CONTPAQi 'Partes Gravadas para ISR por
    empleado': el Sueldo Mensualizado NO es la suma simple de las semanas,
    es esa suma convertida a tasa diaria y reelevada por 30.4:

        Sueldo Mensualizado = (Total Percepciones Gravables / Días
                                Trabajados) × 30.4

    El subsidio sigue siendo todo-o-nada según el límite de $11,492.66."""
    if dias_trabajados <= 0:
        return 0.0, 0.0
    sueldo_mensualizado = (total_percepciones_gravables / dias_trabajados) * 30.4
    isr_bruto = 0.0
    for lim, cuota, porc in TABLA_ISR_MENSUAL_2026:
        if sueldo_mensualizado >= lim:
            isr_bruto = cuota + ((sueldo_mensualizado - lim) * porc)
        else:
            break
    subsidio = SUBSIDIO_MENSUAL_FORMULA(uma_valor) if sueldo_mensualizado <= LIMITE_MENSUAL_SUBSIDIO else 0.0
    # isr_bruto y subsidio están en escala MENSUAL (elevada); se regresan a
    # escala del periodo real para poder restarlos del bruto del periodo.
    factor_regreso = dias_trabajados / 30.4
    return max(0, (isr_bruto - subsidio) * factor_regreso), subsidio * factor_regreso


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


def margen_semanal_antes_de_cruzar(sd, transporte_sem, transporte_gravado, uma):
    """CORREGIDO: cuántos pesos de incentivo POR SEMANA puede recibir un
    trabajador de este puesto antes de que el Sueldo Mensualizado (fórmula
    real: total/días×30.4) cruce el límite del subsidio al empleo. Con la
    fórmula correcta este margen YA NO depende de si el mes tiene 4 o 5
    semanas — es el mismo siempre, porque el factor 30.4 normaliza por día,
    no por mes calendario. Negativo = ya lo cruza solo con el sueldo base."""
    techo_semanal = LIMITE_MENSUAL_SUBSIDIO * 7 / 30.4
    base_semana = sd * 7
    transp_grav = transporte_sem if transporte_gravado else 0
    return techo_semanal - (base_semana + transp_grav)


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

st.title("Simulador de Nómina Estratégica (V30)")

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

    if st.button("CALCULAR NÓMINA V30", type="primary", use_container_width=True):
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
        "última semana del mes se le recupera de golpe lo que se le había dado. "
        "**Corregido:** el margen ya no depende de si el mes tiene 4 o 5 semanas — el factor de "
        "elevación (30.4) normaliza por día, no por mes calendario, así que es el mismo margen semanal "
        "todo el año. Lo que sí cambia entre meses de 4 y 5 semanas es cuántos pesos de subsidio están "
        "en juego si se cruza (una semana más de subsidio que recuperar)."
    )

    tabla_uso = st.session_state.get("tabla_incentivos", TABLA_INCENTIVOS_DEFAULT)

    st.markdown("### Margen semanal seguro por categoría (antes de sumar el incentivo)")
    filas_margen = []
    for puesto, sd in SD_MAP.items():
        margen = margen_semanal_antes_de_cruzar(sd, transporte_prom, transp_gravado, uma)
        filas_margen.append({"Puesto": puesto, "Margen semanal antes de incentivo": margen})
    df_margen = pd.DataFrame(filas_margen).set_index("Puesto")
    st.dataframe(df_margen.style.format("${:,.2f}"), use_container_width=True)
    st.caption("Negativo = ya se cruza el límite solo con sueldo + transporte, antes de un solo peso de incentivo. "
               "Este margen aplica igual sin importar si el mes tiene 4 o 5 semanas.")

    st.markdown("---")
    st.markdown("### Semáforo: cada combinación Clase/Tier de tu tabla, por categoría")

    filas_semaforo = []
    for puesto, sd in SD_MAP.items():
        margen = margen_semanal_antes_de_cruzar(sd, transporte_prom, transp_gravado, uma)
        for clase, tiers in tabla_uso.items():
            for tier, monto in tiers.items():
                cruza = monto > margen
                filas_semaforo.append({
                    "Puesto": puesto, "Clase": clase, "Tier": f"{int(tier*100)}%",
                    "Incentivo/sem": monto, "Estado": "🔴 Cruza — pierde subsidio" if cruza else "🟢 Mantiene subsidio"
                })
    df_sem = pd.DataFrame(filas_semaforo)
    puesto_filtro = st.selectbox("Filtrar por categoría", list(SD_MAP.keys()), key="filtro_semaforo")
    st.dataframe(df_sem[df_sem["Puesto"] == puesto_filtro].drop(columns="Puesto"), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### El acantilado en números: comparación directa antes/después de cruzar")
    st.caption("Elige una categoría y compara el neto del periodo justo antes vs. justo después del límite. "
               "La longitud del mes (4 o 5 semanas) no cambia si se cruza o no, pero sí cuánto subsidio total está en juego.")

    puesto_cliff = st.selectbox("Categoría", list(SD_MAP.keys()), key="puesto_cliff")
    sd_cliff = SD_MAP[puesto_cliff]
    n_cliff = st.radio("Longitud del mes", [4, 5], horizontal=True, key="n_cliff")
    incentivo_cliff = st.slider("Incentivo semanal a simular ($)", 0, 900, 400, step=10, key="incentivo_cliff")

    dias_cliff = n_cliff * 7
    base_semana = sd_cliff * 7
    transp_grav_cliff = transporte_prom if transp_gravado else 0
    total_percepciones_gravables = (base_semana + transp_grav_cliff + incentivo_cliff) * n_cliff
    isr_periodo, sub_periodo = calcular_isr_mensual_real(total_percepciones_gravables, dias_cliff, uma)
    bruto_total_percibido = (base_semana + transporte_prom + incentivo_cliff) * n_cliff
    neto_periodo = bruto_total_percibido - isr_periodo

    sueldo_mensualizado = (total_percepciones_gravables / dias_cliff) * 30.4
    cruzo = sueldo_mensualizado > LIMITE_MENSUAL_SUBSIDIO
    col1, col2, col3 = st.columns(3)
    col1.metric("Sueldo Mensualizado (elevado)", f"${sueldo_mensualizado:,.2f}")
    col2.metric("Subsidio del periodo", f"${sub_periodo:,.2f}", delta="Perdido" if cruzo else "Conservado", delta_color="inverse" if cruzo else "normal")
    col3.metric("Neto del periodo (estimado)", f"${neto_periodo:,.2f}")

    if cruzo:
        st.error(f"⚠️ Este escenario CRUZA el límite por ${sueldo_mensualizado - LIMITE_MENSUAL_SUBSIDIO:,.2f} "
                 f"en el Sueldo Mensualizado. El trabajador pierde el subsidio completo del periodo "
                 f"(~${SUBSIDIO_MENSUAL_FORMULA(uma)/30.4*dias_cliff:,.2f}).")
    else:
        st.success(f"✅ Este escenario se mantiene ${LIMITE_MENSUAL_SUBSIDIO - sueldo_mensualizado:,.2f} por debajo del límite. Subsidio conservado.")

with tab4:
    st.write("🚧 Cotizador Maquila (Pendiente de Configurar)")
