# =====================================================================
# modulo_analisis_financiero.py
# Módulo Financiero — Red Actual vs Red Propuesta
# Munchy - Gemelo Digital Logístico
# =====================================================================
import io
import math
import re as _re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import date
from utils_munchy import (
    clasificar_region,
    obtener_coords_ciudad,
    CIUDADES_VENEZUELA,
    _distancia,
)

def fmt_num(valor, decimales=0):
    """Formatea números al estilo latinoamericano: miles con punto, decimales con coma."""
    if decimales == 0:
        return f"{valor:,.0f}".replace(",", ".")
    else:
        s = f"{valor:,.{decimales}f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    
def fmt_pct(valor, decimales=1):
    return str(round(valor, decimales)).replace('.', ',')
# =====================================================================
# CONSTANTES
# =====================================================================
AÑO_ACTUAL     = date.today().year
MESES_DESEADOS = 6
KM_POR_GRADO   = 111.0
VEHICULOS_CALETAS = {
    'CAMIONETA': 20.0,
    '350':       28.0,
    'NPR 1':     35.0,
    'NPR 2':     35.0,
    '750':       42.0,
    'TORONTO':   42.0,
    'GANDOLA':   50.0,
}
VEHICULOS = list(VEHICULOS_CALETAS.keys())
REGIONES_DIRECTAS = ['Centro', 'Oriente']
REGIONES_VIA_CCS  = ['Capital']
REGIONES_VIA_BQTO = ['Centro-Occidente', 'Occidente-Andes']
NOMBRE_MES = {
    1:'Enero', 2:'Febrero', 3:'Marzo',     4:'Abril',
    5:'Mayo',  6:'Junio',   7:'Julio',     8:'Agosto',
    9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'
}
# =====================================================================
# P1. PARSER — NUMERO DE VIAJES [Validación de Decimales]
# =====================================================================
@st.cache_data(show_spinner="Leyendo viajes...")
def cargar_numero_viajes(archivo):
    MESES_MAP = {
        'enero':1, 'febrero':2, 'marzo':3, 'abril':4,
        'mayo':5, 'junio':6, 'julio':7, 'agosto':8,
        'septiembre':9, 'octubre':10, 'noviembre':11, 'diciembre':12,
    }
    
    # ✅ Mapeo de subregiones originales
    SUBREGION_NORM = {
        'REGION CAPITAL':           'Capital',
        'REGION CENTRO':            'Centro',
        'REGION ORIENTE SUR':       'Oriente Sur',
        'REGION ORIENTE NORTE':     'Oriente Norte',
        'REGION CENTRO OCCIDENTE':  'Centro-Occidente',
        'REGION OCCIDENTE':         'Occidente',
        'REGION LOS ANDES':         'Los Andes',
    }
    
    # ✅ Mapeo a regiones grandes (para cálculos)
    SUBREGION_A_REGION = {
        'Capital':          'Capital',
        'Centro':           'Centro',
        'Oriente Sur':      'Oriente',
        'Oriente Norte':    'Oriente',
        'Centro-Occidente': 'Centro-Occidente',
        'Occidente':        'Occidente-Andes',
        'Los Andes':        'Occidente-Andes',
    }
    
    xl             = pd.ExcelFile(archivo)
    sheets_con_mes = []
    
    for sheet in xl.sheet_names:
        mes_num = next(
            (num for nombre, num in MESES_MAP.items()
             if nombre in sheet.lower().strip()),
            None
        )
        if mes_num is not None:
            sheets_con_mes.append((mes_num, sheet))
    
    sheets_con_mes.sort(key=lambda x: x[0])
    sheets_a_leer  = sheets_con_mes[-MESES_DESEADOS:]
    frames         = []
    meses_leidos   = []
    meses_fallidos = []
    
    for mes_num, sheet in sheets_a_leer:
        try:
            df_s = pd.read_excel(archivo, sheet_name=sheet, header=3)
            df_s.columns = [str(c).strip() for c in df_s.columns]
            
            col_region = next(
                (c for c in df_s.columns
                 if 'regi' in c.lower()
                 or 'regi' in c.lower().replace('ó','o')),
                None
            )
            
            if not col_region:
                meses_fallidos.append(f"{sheet}: sin columna Región")
                continue
            
            cols_vehiculos = {}
            for v in VEHICULOS:
                col = next(
                    (c for c in df_s.columns
                     if v.upper() in c.upper().strip()),
                    None
                )
                if col:
                    cols_vehiculos[v] = col
            
            if not cols_vehiculos:
                meses_fallidos.append(f"{sheet}: sin columnas de vehículos")
                continue
            
            df_s[col_region] = df_s[col_region].astype(str).str.strip().str.upper()
            df_reg = df_s[df_s[col_region].str.startswith('REGION')].copy()
            
            if df_reg.empty:
                meses_fallidos.append(f"{sheet}: sin filas de región")
                continue
            
            # ✅ PASO 1: Crear subregión original
            df_reg['Subregion'] = df_reg[col_region].map(SUBREGION_NORM).fillna('Otros')
            df_reg['Mes']       = mes_num
            
            # ✅ PASO 2: Leer valores y validar decimales
            tiene_decimales = False
            vehiculos_con_decimales = []
            
            for v, col in cols_vehiculos.items():
                valores = pd.to_numeric(df_reg[col], errors='coerce').fillna(0.0)
                
                # Validar si hay decimales
                if (valores % 1 != 0).any():
                    tiene_decimales = True
                    vehiculos_con_decimales.append(v)
                
                # Redondeo matemático estándar (≥0.5 arriba, <0.5 abajo)
                df_reg[v] = valores.round(0).astype(int)
            
            # ⚠️ Advertir si hay decimales
            if tiene_decimales:
                meses_fallidos.append(
                    f"⚠️ {sheet}: Columna(s) {', '.join(vehiculos_con_decimales)} "
                    f"con valores decimales. Redondea manualmente en Excel para mayor precisión."
                )
            
            # ✅ PASO 3: Agrupar por Mes + Subregion
            cols_agg = {v: 'sum' for v in cols_vehiculos.keys()}
            df_agg = (
                df_reg
                .groupby(['Mes', 'Subregion'])
                .agg(cols_agg)
                .reset_index()
            )
            
            # ✅ PASO 4: Agregar columna Region
            df_agg['Region'] = df_agg['Subregion'].map(SUBREGION_A_REGION)
            
            frames.append(df_agg)
            meses_leidos.append(f"{sheet} (mes {mes_num})")
            
        except Exception as e:
            meses_fallidos.append(f"{sheet}: {e}")
            continue
    
    if not frames:
        return pd.DataFrame(), meses_leidos, meses_fallidos
    
    df_final = pd.concat(frames, ignore_index=True)
    
    for v in VEHICULOS:
        if v not in df_final.columns:
            df_final[v] = 0
    
    n_meses    = df_final['Mes'].nunique()
    n_subreg   = df_final['Subregion'].nunique()
    meses_leidos.insert(
        0, f"📅 {n_meses} meses | 📍 {n_subreg} subregiones | "
           f"{sorted(df_final['Subregion'].unique())}"
    )
    
    return df_final, meses_leidos, meses_fallidos
# =====================================================================
# HELPER — Limpiar tabulador
# =====================================================================
def _limpiar_tab(df):
    EXCLUIR = ['NAN', 'NONE', 'TABULADOR', 'CALETA', 'REGION', 'DESTINO', '$']
    mask = (
        (df['Destino'].str.len() > 2) &
        (df['Destino'].str.upper().apply(
            lambda x: not any(e == x.strip() for e in EXCLUIR)
        )) &
        (~df['Destino'].str.upper().str.startswith('$')) &
        (df.drop(columns='Destino')
           .apply(pd.to_numeric, errors='coerce')
           .fillna(0)
           .sum(axis=1) > 0)
    )
    return df[mask].reset_index(drop=True)
# =====================================================================
# P2. PARSER — TABULADOR DE TARIFAS
# =====================================================================
@st.cache_data(show_spinner="Leyendo tabulador...")
def cargar_tabulador(archivo):
    xl      = pd.ExcelFile(archivo)
    tabs    = {}
    errores = []
    for sheet in xl.sheet_names:
        sheet_norm = sheet.upper().strip()
        try:
            if 'BARQUISIMETO' in sheet_norm or sheet_norm in ('BTO', 'BQTO', 'BARQ'):
                df_t = pd.read_excel(archivo, sheet_name=sheet, header=8)
                df_t.columns = [str(c).strip() for c in df_t.columns]
                df_limpio            = pd.DataFrame()
                df_limpio['Destino'] = df_t.iloc[:, 1].apply(
                    lambda x: str(x).strip().upper() if pd.notna(x) else ''
                )
                df_limpio['CAMIONETA'] = pd.to_numeric(df_t.iloc[:, 2], errors='coerce').fillna(0.0)
                df_limpio['350']       = pd.to_numeric(df_t.iloc[:, 3], errors='coerce').fillna(0.0)
                npr = pd.to_numeric(df_t.iloc[:, 4], errors='coerce').fillna(0.0)
                df_limpio['NPR 1']   = npr
                df_limpio['NPR 2']   = npr
                toronto_750 = pd.to_numeric(df_t.iloc[:, 5], errors='coerce').fillna(0.0)
                df_limpio['750']     = toronto_750
                df_limpio['TORONTO'] = toronto_750
                df_limpio['GANDOLA'] = pd.to_numeric(df_t.iloc[:, 6], errors='coerce').fillna(0.0)
                tabs['BARQUISIMETO'] = _limpiar_tab(df_limpio)
            elif 'CAPITAL' in sheet_norm or sheet_norm in ('CAP', 'CCS', 'CARACAS'):
                df_t = pd.read_excel(archivo, sheet_name=sheet, header=7)
                df_t.columns = [str(c).strip() for c in df_t.columns]
                df_limpio            = pd.DataFrame()
                df_limpio['Destino'] = df_t.iloc[:, 1].apply(
                    lambda x: str(x).strip().upper() if pd.notna(x) else ''
                )
                def _buscar_col(df, claves):
                    return next(
                        (c for c in df.columns if any(k in c.lower() for k in claves)), None
                    )
                for vehiculo, claves in [
                    ('CAMIONETA', ['camioneta']),
                    ('350',       ['350']),
                    ('NPR 1',     ['npr1', 'npr 1', 'tipo 1', 'npr tipo 1']),
                    ('NPR 2',     ['npr2', 'npr 2', 'tipo 2', 'npr tipo 2']),
                    ('750',       ['750']),
                    ('TORONTO',   ['toronto']),
                    ('GANDOLA',   ['gandola']),
                ]:
                    col = _buscar_col(df_t, claves)
                    df_limpio[vehiculo] = pd.to_numeric(
                        df_t[col], errors='coerce'
                    ).fillna(0.0) if col else 0.0
                tabs['CAPITAL'] = _limpiar_tab(df_limpio)
            elif (
                ('centro' in sheet_norm.lower() and 'oriente' in sheet_norm.lower())
                or sheet_norm.replace('-', '').replace(' ', '') == 'CENTROORIENTE'
            ):
                df_t = pd.read_excel(archivo, sheet_name=sheet, header=8)
                df_t.columns = [str(c).strip() for c in df_t.columns]
                df_limpio            = pd.DataFrame()
                df_limpio['Destino'] = df_t.iloc[:, 1].apply(
                    lambda x: str(x).strip().upper() if pd.notna(x) else ''
                )
                def _buscar_tab(df, claves):
                    return next(
                        (c for c in df.columns if any(k in c.lower() for k in claves)), None
                    )
                for vehiculo, claves in [
                    ('CAMIONETA', ['camioneta']),
                    ('350',       ['350', 'tabulador 350']),
                    ('NPR 1',     ['npr tipo 1', 'npr1', 'npr 1']),
                    ('NPR 2',     ['npr tipo 2', 'npr2', 'npr 2']),
                    ('750',       ['750']),
                    ('TORONTO',   ['toronto']),
                    ('GANDOLA',   ['gandola']),
                ]:
                    col = _buscar_tab(df_t, claves)
                    df_limpio[vehiculo] = pd.to_numeric(
                        df_t[col], errors='coerce'
                    ).fillna(0.0) if col else 0.0
                tabs['CENTRO-ORIENTE'] = _limpiar_tab(df_limpio)
        except Exception as e:
            errores.append(f"{sheet}: {e}")
    return tabs, errores
# =====================================================================
# P2b. PARSER — CENTRO-ORIENTE DESDE MAESTRO
# =====================================================================
@st.cache_data(show_spinner="Leyendo CENTRO-ORIENTE...")
def cargar_centro_oriente(archivo_maestro):
    try:
        xl = pd.ExcelFile(archivo_maestro)
        sheet_target = next(
            (s for s in xl.sheet_names
             if 'centro' in s.upper() and 'oriente' in s.upper()),
            None
        )
        if sheet_target is None:
            return pd.DataFrame(), "❌ No se encontró sheet CENTRO-ORIENTE en Maestro"
        df_t = pd.read_excel(archivo_maestro, sheet_name=sheet_target, header=8)
        df_t.columns = [str(c).strip() for c in df_t.columns]
        df_limpio = pd.DataFrame()
        df_limpio['Destino'] = df_t.iloc[:, 1].apply(
            lambda x: str(x).strip().upper() if pd.notna(x) else ''
        )
        def _buscar_tab(df, claves):
            return next(
                (c for c in df.columns if any(k in c.lower() for k in claves)), None
            )
        for vehiculo, claves in [
            ('CAMIONETA', ['tabulador  camioneta']),
            ('350',       ['tabulador  350']),
            ('NPR 1',     ['tabulador  npr tipo 1']),
            ('NPR 2',     ['tabulador  npr tipo 2']),
            ('750',       ['tabulador  750']),
            ('TORONTO',   ['tabulador  toronto']),
            ('GANDOLA',   ['tabulador  gandola']),
        ]:
            col = _buscar_tab(df_t, claves)
            df_limpio[vehiculo] = pd.to_numeric(
                df_t[col], errors='coerce'
            ).fillna(0.0) if col else 0.0
        df_resultado = _limpiar_tab(df_limpio)
        if df_resultado.empty:
            return pd.DataFrame(), (
                f"❌ _limpiar_tab filtró todo. "
                f"Primeros Destinos: {df_limpio['Destino'].head(5).tolist()}"
            )
        return df_resultado, f"OK — {len(df_resultado)} destinos"
    except Exception as e:
        import traceback
        return pd.DataFrame(), f"❌ Excepción: {traceback.format_exc()}"
# =====================================================================
# P3. PARSER — CONSOLIDADO CENDIS
# =====================================================================
@st.cache_data(show_spinner="Procesando Consolidado...")
def cargar_consolidado(archivo):
    try:
        xl = pd.ExcelFile(archivo)
        sheet_target = next(
            (s for s in xl.sheet_names
             if 'costo' in s.lower() and 'cendis' in s.lower()),
            xl.sheet_names[-1]
        )
        df_raw = pd.read_excel(archivo, sheet_name=sheet_target, header=0)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        col_concepto = df_raw.columns[0]
        col_sep = next(
            (c for c in df_raw.columns
             if str(c).upper().strip() == 'ACUMULADOS'),
            None
        )
        if col_sep is None:
            col_sep = next(
                (c for c in df_raw.columns if df_raw[c].isna().all()), None
            )
        if col_sep:
            idx_sep   = df_raw.columns.get_loc(col_sep)
            cols_data = df_raw.columns[1:idx_sep].tolist()
        else:
            cols_data = df_raw.columns[1:].tolist()
        cols_meses = cols_data[-6:]
        MESES_ABR = {
            'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
            'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
        }
        def _mes_num(col_str):
            s = str(col_str).lower()
            for abr, num in MESES_ABR.items():
                if abr in s:
                    return num
            return None
        bloques = {}
        for i, val in enumerate(df_raw[col_concepto]):
            val_str = str(val).strip()
            if 'cendis' in val_str.lower():
                nombre = val_str.upper().replace('CENDIS', '').strip()
                if not nombre:
                    nombre = f'BLOQUE_{i}'
                bloques[nombre] = i
        if not bloques:
            return None, "❌ No se encontraron bloques CenDis."
        CONCEPTOS = {
            'flete':           'Flete',
            'costos log':      'Costos_Log',
            'costo log':       'Costos_Log',
            '3/c sobre acar':  'Acarreos_Reali',
            'acarreos real':   'Acarreos_Reali',
            'acarreo':         'Acarreos',
            'total gtos':      'Total_Gastos',
            'ventas neta':     'Ventas_Netas',
            'ventas netas':    'Ventas_Netas',
            'kg de venta':     'Kg_Ventas',
            'kg ventas':       'Kg_Ventas',
            'bul/cja':         'Bultos_Mov',
            'bul/cja mov':     'Bultos_Mov',
        }
        resultado    = {}
        bloque_items = sorted(bloques.items(), key=lambda x: x[1])
        for idx_b, (nombre_cendis, fila_ini) in enumerate(bloque_items):
            fila_fin = bloque_items[idx_b + 1][1] \
                       if idx_b + 1 < len(bloque_items) else len(df_raw)
            while fila_fin > fila_ini + 1 and \
                  str(df_raw.iloc[fila_fin - 1][col_concepto]).strip() in ('', 'nan', 'NaN'):
                fila_fin -= 1
            df_bloque    = df_raw.iloc[fila_ini + 1 : fila_fin].copy()
            datos_cendis = {}
            for _, fila in df_bloque.iterrows():
                concepto_raw = str(fila[col_concepto]).lower().strip()
                if concepto_raw in ('', 'nan'):
                    continue
                concepto_norm = None
                for clave, nombre in CONCEPTOS.items():
                    if clave in concepto_raw:
                        concepto_norm = nombre
                        break
                if concepto_norm is None:
                    continue
                valores = []
                for col_mes in cols_meses:
                    val = fila.get(col_mes, None)
                    try:
                        val_num = float(
                            str(val).replace(',', '').replace('-', '0').strip()
                        ) if pd.notna(val) else 0.0
                    except (ValueError, TypeError):
                        val_num = 0.0
                    valores.append(val_num)
                valores_nz = [v for v in valores if v > 0]
                promedio   = round(
                    sum(valores_nz) / len(valores_nz), 2
                ) if valores_nz else 0.0
                datos_cendis[concepto_norm] = promedio
            ventas = datos_cendis.get('Ventas_Netas',  0)
            kg     = datos_cendis.get('Kg_Ventas',      0)
            gtos   = datos_cendis.get('Total_Gastos',   0)
            acar_r = datos_cendis.get('Acarreos_Reali', 0)
            datos_cendis['Pct_Gtos_Ventas']   = round(gtos / ventas * 100, 2) \
                                                 if ventas > 0 else 0.0
            datos_cendis['Costo_Kg']          = round(gtos / kg, 4) \
                                                 if kg > 0 else 0.0
            datos_cendis['Ratio_Acarreos_Kg'] = round(acar_r / kg, 6) \
                                                 if kg > 0 else 0.0
            resultado[nombre_cendis] = datos_cendis
        cendis_leidos = sorted(resultado.keys())
        return resultado, f"✅ OK — CenDis: {cendis_leidos} | Meses: {[_mes_num(c) for c in cols_meses if _mes_num(c)]}"
    except Exception as e:
        return None, f"Error: {e}"
# =====================================================================
# P4. CALCULAR COSTO/KM POR VEHÍCULO
# =====================================================================
def calcular_costo_km(tabs_co):
    LAT_MARACAY = 10.2469
    LON_MARACAY = -67.5958
    MIN_KM      = 40
    if tabs_co.empty:
        return {}
    costo_km = {}
    for vehiculo in VEHICULOS:
        if vehiculo not in tabs_co.columns:
            continue
        ratios = []
        for _, row in tabs_co.iterrows():
            destino = str(row['Destino']).strip().upper()
            tarifa  = float(row.get(vehiculo, 0) or 0)
            if tarifa <= 0:
                continue
            coords = CIUDADES_VENEZUELA.get(destino)
            if not coords:
                coords = next(
                    (v for k, v in CIUDADES_VENEZUELA.items()
                     if destino in k or k in destino),
                    None
                )
            if not coords:
                continue
            lat_d, lon_d = coords
            dist_km      = _distancia(
                LAT_MARACAY, LON_MARACAY, lat_d, lon_d
            ) * KM_POR_GRADO
            if dist_km >= MIN_KM:
                caleta = VEHICULOS_CALETAS.get(vehiculo, 0)
                ratios.append((tarifa - caleta) / dist_km)
        if ratios:
            costo_km[vehiculo] = round(sum(ratios) / len(ratios), 4)
    return costo_km
# =====================================================================
# HELPER — Obtener tarifa de una ciudad
# =====================================================================
def obtener_tarifa_ciudad(tabs_co, tab_extra, ciudad, vehiculo, ruta):
    ciudad_norm = str(ciudad).upper().strip()
    if ruta == 'CENTRO-ORIENTE':
        df_tab = tabs_co
    else:
        df_tab = tab_extra.get(ruta, pd.DataFrame())
    if df_tab is None or df_tab.empty:
        return 0.0
    fila = df_tab[df_tab['Destino'] == ciudad_norm]
    if fila.empty:
        fila = df_tab[
            df_tab['Destino'].str.contains(ciudad_norm, na=False) |
            df_tab['Destino'].apply(
                lambda x: ciudad_norm in str(x).upper()
            )
        ]
    if fila.empty:
        return 0.0
    vehiculo_norm = str(vehiculo).upper().strip()
    col = next(
        (c for c in df_tab.columns if vehiculo_norm in c.upper()), None
    )
    if not col:
        return 0.0
    return float(fila.iloc[0][col])
# =====================================================================
# OBJETIVO 1 — COSTO ACTUAL DE LA RED POR REGIÓN
# =====================================================================
def calcular_costo_actual_region(
    region,
    df_viajes,
    tabs_co,
    tab_extra,
    consolidado,
    cendis_ref='BQTO',
    pasa_por_cendis=False,
    cual_cendis=None,
):
    REGION_A_ARCHIVO = {
        'Capital':          'Capital',
        'Centro':           'Centro',
        'Oriente':          'Oriente',
        'Centro-Occidente': 'Centro-Occidente',
        'Occidente-Andes':  'Occidente-Andes',
    }
    region_archivo = REGION_A_ARCHIVO.get(region, region)
    df_reg = df_viajes[df_viajes['Region'] == region_archivo].copy()
    if df_reg.empty:
        return None, f"❌ No hay viajes para la región {region}"
    meses_disponibles = sorted(df_reg['Mes'].unique().tolist())
    if pasa_por_cendis and cual_cendis:
        tipo_ruta = f'VIA_{cual_cendis.upper()}'
    elif region in REGIONES_VIA_CCS:
        tipo_ruta = 'VIA_CCS'
    elif region in REGIONES_VIA_BQTO:
        tipo_ruta = 'VIA_BQTO'
    else:
        tipo_ruta = 'DIRECTO'
    ciudades_region = [
        ciudad for ciudad in CIUDADES_VENEZUELA.keys()
        if clasificar_region(ciudad, '')[0] == region
    ]
    costo_por_mes   = {}
    viajes_por_mes  = {}
    detalle_por_mes = {}
    for mes in meses_disponibles:
        df_mes      = df_reg[df_reg['Mes'] == mes]
        costo_mes   = 0.0
        viajes_mes  = {}
        detalle_mes = {}
        for vehiculo, caleta in VEHICULOS_CALETAS.items():
            viajes_v = int(df_mes[vehiculo].sum()) \
                       if vehiculo in df_mes.columns else 0
            if viajes_v == 0:
                continue
            viajes_mes[vehiculo] = viajes_v
            if tipo_ruta == 'DIRECTO':
                tarifas   = [
                    obtener_tarifa_ciudad(
                        tabs_co, tab_extra, c, vehiculo, 'CENTRO-ORIENTE'
                    )
                    for c in ciudades_region
                ]
                tarifas_v = [t for t in tarifas if t > 0]
                tarifa    = round(sum(tarifas_v) / len(tarifas_v), 2) \
                            if tarifas_v else 0.0
                costo_v   = round(viajes_v * (tarifa + caleta), 2)
                detalle_mes[vehiculo] = {
                    'Tipo':   'DIRECTO',
                    'Viajes': viajes_v,
                    'Tarifa': tarifa,
                    'Caleta': caleta,
                    'Costo':  costo_v,
                }
            elif tipo_ruta == 'VIA_CCS':
                acarreos_ccs = consolidado.get('CCS', {}).get('Acarreos_Reali', 0)
                viajes_t1    = math.ceil(acarreos_ccs)
                tarifa_t1    = obtener_tarifa_ciudad(
                    tabs_co, tab_extra, 'CARACAS', vehiculo, 'CENTRO-ORIENTE'
                )
                costo_t1     = round(viajes_t1 * (tarifa_t1 + caleta), 2)
                tarifas_t2   = [
                    obtener_tarifa_ciudad(
                        tabs_co, tab_extra, c, vehiculo, 'CAPITAL'
                    )
                    for c in ciudades_region
                ]
                tarifas_t2_v = [t for t in tarifas_t2 if t > 0]
                tarifa_t2    = round(sum(tarifas_t2_v) / len(tarifas_t2_v), 2) \
                               if tarifas_t2_v else 0.0
                costo_t2     = round(viajes_v * (tarifa_t2 + caleta), 2)
                costo_v      = round(costo_t1 + costo_t2, 2)
                detalle_mes[vehiculo] = {
                    'Tipo':      'VIA_CCS',
                    'Viajes_T1': viajes_t1,
                    'Tarifa_T1': tarifa_t1,
                    'Costo_T1':  costo_t1,
                    'Viajes_T2': viajes_v,
                    'Tarifa_T2': tarifa_t2,
                    'Costo_T2':  costo_t2,
                    'Caleta':    caleta,
                    'Costo':     costo_v,
                }
            elif tipo_ruta == 'VIA_BQTO':
                acarreos_bqto = consolidado.get('BQTO', {}).get('Acarreos_Reali', 0)
                viajes_t1     = math.ceil(acarreos_bqto)
                tarifa_t1     = obtener_tarifa_ciudad(
                    tabs_co, tab_extra, 'BARQUISIMETO', vehiculo, 'CENTRO-ORIENTE'
                )
                costo_t1      = round(viajes_t1 * (tarifa_t1 + caleta), 2)
                tarifas_t2   = [
                    obtener_tarifa_ciudad(
                        tabs_co, tab_extra, c, vehiculo, 'BARQUISIMETO'
                    )
                    for c in ciudades_region
                ]
                tarifas_t2_v = [t for t in tarifas_t2 if t > 0]
                tarifa_t2    = round(sum(tarifas_t2_v) / len(tarifas_t2_v), 2) \
                               if tarifas_t2_v else 0.0
                costo_t2     = round(viajes_v * (tarifa_t2 + caleta), 2)
                costo_v      = round(costo_t1 + costo_t2, 2)
                detalle_mes[vehiculo] = {
                    'Tipo':      'VIA_BQTO',
                    'Viajes_T1': viajes_t1,
                    'Tarifa_T1': tarifa_t1,
                    'Costo_T1':  costo_t1,
                    'Viajes_T2': viajes_v,
                    'Tarifa_T2': tarifa_t2,
                    'Costo_T2':  costo_t2,
                    'Caleta':    caleta,
                    'Costo':     costo_v,
                }
            else:
                costo_v = 0.0
            costo_mes += costo_v
        costo_por_mes[mes]   = round(costo_mes, 2)
        viajes_por_mes[mes]  = viajes_mes
        detalle_por_mes[mes] = detalle_mes
    costo_promedio_mes = round(
        sum(costo_por_mes.values()) / len(costo_por_mes), 2
    ) if costo_por_mes else 0.0
    viajes_promedio = {}
    for vehiculo in VEHICULOS:
        vals = [
            viajes_por_mes[mes].get(vehiculo, 0)
            for mes in meses_disponibles
        ]
        viajes_promedio[vehiculo] = math.ceil(
            sum(vals) / len(vals)
        ) if vals else 0
    return {
        'region':             region,
        'tipo_ruta':          tipo_ruta,
        'meses_usados':       meses_disponibles,
        'costo_por_mes':      costo_por_mes,
        'costo_promedio_mes': costo_promedio_mes,
        'viajes_por_mes':     viajes_por_mes,
        'viajes_promedio':    viajes_promedio,
        'detalle_por_mes':    detalle_por_mes,
    }, "OK"
# =====================================================================
# OBJETIVO 2 — COSTO MENSUAL DEL NUEVO CENDIS
# =====================================================================
def calcular_proporcion_vehiculos(df_viajes, region):
    REGION_MAP = {
        'Oriente':          ['Oriente'],
        'Capital':          ['Capital'],
        'Centro':           ['Centro'],
        'Centro-Occidente': ['Centro-Occidente'],
        'Occidente-Andes':  ['Occidente-Andes'],
    }
    regiones_archivo = REGION_MAP.get(region, [region])
    df_reg = df_viajes[df_viajes['Region'].isin(regiones_archivo)].copy()
    if df_reg.empty:
        n = len(VEHICULOS)
        return {v: 1/n for v in VEHICULOS}
    total_por_vehiculo = {}
    total_general      = 0
    for vehiculo in VEHICULOS:
        if vehiculo in df_reg.columns:
            total_v = df_reg[vehiculo].sum()
            total_por_vehiculo[vehiculo] = total_v
            total_general               += total_v
        else:
            total_por_vehiculo[vehiculo] = 0
    if total_general == 0:
        n = len(VEHICULOS)
        return {v: 1/n for v in VEHICULOS}
    return {
        v: round(total_por_vehiculo[v] / total_general, 4)
        for v in VEHICULOS
    }

def calcular_flete_por_distancia(distancia_km, proporciones, costo_km_por_vehiculo):
    flete_total = 0.0
    detalle     = {}
    for vehiculo, proporcion in proporciones.items():
        if proporcion == 0:
            continue
        factor_km   = costo_km_por_vehiculo.get(vehiculo, 0.0)
        caleta      = VEHICULOS_CALETAS.get(vehiculo, 0.0)
        flete_v     = factor_km * distancia_km + caleta
        flete_pond  = proporcion * flete_v
        flete_total += flete_pond
        detalle[vehiculo] = {
            'Proporcion_%': round(proporcion * 100, 1),
            'Factor_KM':    factor_km,
            'Distancia_KM': round(distancia_km, 1),
            'Caleta':       caleta,
            'Flete':        round(flete_v, 2),
            'Ponderado':    round(flete_pond, 2),
        }
    return round(flete_total, 2), detalle

def calcular_costo_modo_estado(
    estado,
    ciudad_cendis,
    df_maestro,
    df_viajes,
    costo_km_por_vehiculo,
):
    lat_c, lon_c = obtener_coords_ciudad(ciudad_cendis)
    if lat_c is None:
        return None, f"❌ No se encontraron coordenadas para {ciudad_cendis}"
    estado_norm = str(estado).upper().strip()
    df_estado   = df_maestro[
        df_maestro['Estado'].astype(str).str.upper().str.strip() == estado_norm
    ].copy()
    if df_estado.empty:
        return None, f"❌ No hay clientes para el estado {estado}"
    df_estado['Region_Cliente'] = df_estado.apply(
        lambda r: clasificar_region(
            r.get('Ciudad', ''), r.get('Estado', '')
        )[0], axis=1
    )
    regiones_en_estado = df_estado['Region_Cliente'].unique().tolist()
    aviso_multiples    = None
    if len(regiones_en_estado) > 1:
        aviso_multiples = (
            f"⚠️ El estado {estado} tiene clientes en múltiples "
            f"regiones: {', '.join(regiones_en_estado)}. "
            f"El costo es un promedio ponderado."
        )
    region_dominante = df_estado['Region_Cliente'].mode()[0]
    proporciones     = calcular_proporcion_vehiculos(df_viajes, region_dominante)
    resultados = []
    for _, cliente in df_estado.iterrows():
        lat_cl = cliente.get('Latitud',  None)
        lon_cl = cliente.get('Longitud', None)
        if pd.isna(lat_cl) or pd.isna(lon_cl):
            continue
        if lat_cl == 0 or lon_cl == 0:
            continue
        dist_km = round(
            _distancia(lat_c, lon_c, lat_cl, lon_cl) * KM_POR_GRADO, 1
        )
        flete_cliente, _ = calcular_flete_por_distancia(
            dist_km, proporciones, costo_km_por_vehiculo
        )
        resultados.append({
            'Id. Cliente':       cliente.get('Id. Cliente', ''),
            'Nombre de Cliente': cliente.get('Nombre de Cliente', ''),
            'Ciudad':            cliente.get('Ciudad', ''),
            'Estado':            estado,
            'Region':            cliente.get('Region_Cliente', ''),
            'Distancia_KM':      dist_km,
            'Valor_USD':         cliente.get('Valor_USD', 0.0),
            'Peso_KG':           cliente.get('Peso_KG', 0.0),
            'Flete_Estimado':    flete_cliente,
        })
    if not resultados:
        return None, "❌ No hay clientes con coordenadas válidas."
    df_resultado = pd.DataFrame(resultados)
    return {
        'estado':            estado,
        'ciudad_cendis':     ciudad_cendis,
        'region_dominante':  region_dominante,
        'regiones_estado':   regiones_en_estado,
        'proporciones':      proporciones,
        'costo_total_flete': round(df_resultado['Flete_Estimado'].sum(), 2),
        'venta_total_usd':   round(df_resultado['Valor_USD'].sum(), 2),
        'kg_total':          round(df_resultado['Peso_KG'].sum(), 1),
        'n_clientes':        len(df_resultado),
        'df_clientes':       df_resultado,
        'aviso_multiples':   aviso_multiples,
    }, "OK"

def calcular_objetivo2(
    modo,
    region_o_estado,
    ciudad_cendis,
    df_maestro,
    df_ventas_raw,
    df_viajes,
    consolidado,
    tabs_co,
    tab_extra,
    costo_km_por_vehiculo,
    pct_gastos_ventas,
    viajes_repo_usuario,
    cendis_ref='BQTO',
    ruta_repo='CENTRO-ORIENTE',
):
    debug            = {}
    resultado_estado = None
    lat_c, lon_c = obtener_coords_ciudad(ciudad_cendis)
    if lat_c is None:
        return None, f"❌ No se encontraron coordenadas para {ciudad_cendis}"
    # ── VENTA BASE ──────────────────────────────────────────────────────
    if modo == 'REGIÓN':
        # Usar df_ventas_raw para detectar meses correctamente
        df_fechas = df_ventas_raw.copy() if not df_ventas_raw.empty else df_maestro.copy()
        if 'Fecha del Documento' in df_fechas.columns:
            df_fechas['_Mes'] = pd.to_datetime(
                df_fechas['Fecha del Documento'], errors='coerce'
            ).dt.to_period('M')
            n_meses = max(df_fechas['_Mes'].nunique(), 1)
        else:
            n_meses = 1
        # Venta base desde df_maestro filtrado por región
        df_base = df_maestro.copy()
        df_base['Region_C'] = df_base.apply(
            lambda r: clasificar_region(
                r.get('Ciudad', ''), r.get('Estado', '')
            )[0], axis=1
        )
        df_base    = df_base[df_base['Region_C'] == region_o_estado]
        venta_base = round(df_base['Valor_USD'].sum() / n_meses, 2)
        kg_base    = round(df_base['Peso_KG'].sum()   / n_meses, 1)
        debug['Meses_Detectados'] = n_meses
    else:  # ESTADO
        resultado_estado, msg = calcular_costo_modo_estado(
            estado                = region_o_estado,
            ciudad_cendis         = ciudad_cendis,
            df_maestro            = df_maestro,
            df_viajes             = df_viajes,
            costo_km_por_vehiculo = costo_km_por_vehiculo,
        )
        if resultado_estado is None:
            return None, msg
        df_estado_base = df_maestro[
            df_maestro['Estado'].astype(str).str.upper().str.strip()
            == str(region_o_estado).upper().strip()
        ]
        if 'Fecha del Documento' in df_estado_base.columns:
            df_estado_base = df_estado_base.copy()
            df_estado_base['_Mes'] = pd.to_datetime(
                df_estado_base['Fecha del Documento'], errors='coerce'
            ).dt.to_period('M')
            n_meses = max(df_estado_base['_Mes'].nunique(), 1)
        else:
            n_meses = 1
        venta_base = round(resultado_estado['venta_total_usd'] / n_meses, 2)
        kg_base    = round(resultado_estado['kg_total']         / n_meses, 1)
        debug['Meses_Detectados'] = n_meses
        debug['modo_estado'] = {
            'Estado':       region_o_estado,
            'N_Clientes':   resultado_estado['n_clientes'],
            'Regiones':     resultado_estado['regiones_estado'],
            'Proporciones': resultado_estado['proporciones'],
        }
        if resultado_estado['aviso_multiples']:
            debug['aviso'] = resultado_estado['aviso_multiples']
    debug['Venta_Base_USD'] = venta_base
    debug['Kg_Base']        = kg_base
    # ── GASTO OPERACIONAL ───────────────────────────────────────────────
    gasto_operacional = round(venta_base * (pct_gastos_ventas / 100), 2)
    debug['Gasto_Operacional'] = {
        'Venta_Base_USD':    venta_base,
        'Pct_Gastos_Ventas': pct_gastos_ventas,
        'Gasto_Op':          gasto_operacional,
        'Benchmark_CCS':     '8.62%',
        'Benchmark_BQTO':    '9.83%',
    }
   # ── COSTO REPOSICIÓN (Planta → CenDis) — solo GANDOLA ──────────────
    VEHICULO_REPO = 'GANDOLA'
    caleta_repo   = VEHICULOS_CALETAS.get(VEHICULO_REPO, 50.0)

    tarifa_gandola = obtener_tarifa_ciudad(
        tabs_co, tab_extra, ciudad_cendis, VEHICULO_REPO, ruta_repo
    )
    tarifa_repo_prom = round(tarifa_gandola + caleta_repo, 2) \
        if tarifa_gandola > 0 else 0.0

    costo_reposicion = round(viajes_repo_usuario * tarifa_repo_prom, 2)

    debug['Reposicion'] = {
        'CenDis_Ref':          cendis_ref,
        'Ruta_Repo':           ruta_repo,
        'Vehiculo_Repo':       VEHICULO_REPO,
        'Tarifa_Gandola':      tarifa_gandola,
        'Caleta_Gandola':      caleta_repo,
        'Tarifa_Total_Viaje':  tarifa_repo_prom,
        'Viajes_Repo_Usuario': viajes_repo_usuario,
        'Costo_Reposicion':    costo_reposicion,
    }
    # ── COSTO DISTRIBUCIÓN (CenDis → Clientes) ─────────────────────────
    costo_distribucion = 0.0
    if resultado_estado is not None:
        costo_distribucion = resultado_estado.get('costo_total_flete', 0.0)
        costo_distribucion = round(costo_distribucion / n_meses, 2)
        debug['Distribucion'] = {
            'Costo_CenDis_Clientes': costo_distribucion,
            'N_Clientes':            resultado_estado['n_clientes'],
        }
    # ── COSTO TOTAL ─────────────────────────────────────────────────────
    costo_total_mes = round(
        gasto_operacional + costo_distribucion, 2
    )
    debug['RESUMEN'] = {
        'Modo':               modo,
        'Region_o_Estado':    region_o_estado,
        'Ciudad_CenDis':      ciudad_cendis,
        'Meses':              n_meses,
        'Venta_Base_USD':     venta_base,
        'Kg_Base':            kg_base,
        'Gasto_Operacional':  gasto_operacional,
        'Costo_Reposicion':   costo_reposicion,
        'Costo_Distribucion': costo_distribucion,
        'Costo_Total_Mes':    costo_total_mes,
        'Nota': 'Gasto_Operacional ya incluye Costo_Reposicion',
    }
    return {
        'modo':               modo,
        'region_o_estado':    region_o_estado,
        'ciudad_cendis':      ciudad_cendis,
        'venta_base':         venta_base,
        'kg_base':            kg_base,
        'n_meses':            n_meses,
        'pct_gastos':         pct_gastos_ventas,
        'gasto_operacional':  gasto_operacional,
        'viajes_repo':        viajes_repo_usuario,
        'tarifa_repo':        tarifa_repo_prom,
        'costo_reposicion':   costo_reposicion,
        'costo_distribucion': costo_distribucion,
        'costo_total_mes':    costo_total_mes,
        'resultado_estado':   resultado_estado,
        'debug':              debug,
    }, "OK"
# =====================================================================
# OBJETIVO 3 — COMPARACIÓN RED ACTUAL vs RED PROPUESTA
# =====================================================================
def calcular_objetivo3(resultado_obj1, resultado_obj2):
    debug = {}
    if resultado_obj1 is None or resultado_obj2 is None:
        return None, "❌ Faltan resultados de Obj1 u Obj2"
    costo_actual    = resultado_obj1['costo_promedio_mes']
    costo_propuesto = resultado_obj2['costo_total_mes']
    ahorro_mes      = round(costo_actual - costo_propuesto, 2)
    debug['COMPARACION_BASE'] = {
        'Costo_Red_Actual_Mes ($)':    costo_actual,
        'Costo_Red_Propuesta_Mes ($)': costo_propuesto,
        'Ahorro_Mes ($)':              ahorro_mes,
        'Es_Rentable':                 ahorro_mes > 0,
    }
    acumulado      = []
    acum_actual    = 0.0
    acum_propuesto = 0.0
    for mes in range(1, 25):
        acum_actual    = round(acum_actual    + costo_actual,    2)
        acum_propuesto = round(acum_propuesto + costo_propuesto, 2)
        acumulado.append({
            'Mes':            mes,
            'Acum_Actual':    acum_actual,
            'Acum_Propuesto': acum_propuesto,
            'Diferencia':     round(acum_actual - acum_propuesto, 2),
        })
    mes_cruce = next(
        (a['Mes'] for a in acumulado if a['Diferencia'] > 0), None
    )
    debug['ACUMULADO_MUESTRA'] = {
        'Mes_1':     acumulado[0],
        'Mes_6':     acumulado[5],
        'Mes_12':    acumulado[11],
        'Mes_24':    acumulado[23],
        'Mes_Cruce': mes_cruce,
    }
    return {
        'costo_actual_mes':    costo_actual,
        'costo_propuesto_mes': costo_propuesto,
        'ahorro_mes':          ahorro_mes,
        'es_rentable':         ahorro_mes > 0,
        'mes_cruce':           mes_cruce,
        'acumulado':           acumulado,
        'debug':               debug,
    }, "OK"
# =====================================================================
# D1. PARSER — ARCHIVO DE CRECIMIENTO
# =====================================================================
@st.cache_data(show_spinner="Leyendo datos de crecimiento...")
def cargar_crecimiento(archivo_crecimiento, clave_forzada=None):
    MESES_COLS = [
        'ene', 'feb', 'mar', 'abr', 'may', 'jun',
        'jul', 'ago', 'sep', 'oct', 'nov', 'dic'
    ]
    xl      = pd.ExcelFile(archivo_crecimiento)
    datos   = {}
    errores = []
    for sheet in xl.sheet_names:
        sheet_norm = sheet.upper().strip()
        if clave_forzada:
            clave = clave_forzada
        else:
            if 'CENDIS' in sheet_norm:
                clave = 'CENDIS'
            elif 'REGION' in sheet_norm:
                clave = 'REGION'
            else:
                clave = 'CENDIS' if not datos else 'REGION'
        try:
            df_raw = pd.read_excel(
                archivo_crecimiento,
                sheet_name=sheet,
                header=None
            )
            df_raw = df_raw.fillna('')
            header_row = None
            for i, row in df_raw.iterrows():
                row_str = ' '.join([str(v).lower().strip() for v in row.values])
                if 'ene' in row_str and ('feb' in row_str or 'mar' in row_str):
                    header_row = i
                    break
            if header_row is None:
                errores.append(f"{sheet}: no se encontró fila de encabezados de meses")
                continue
            df = pd.read_excel(
                archivo_crecimiento,
                sheet_name=sheet,
                header=header_row
            )
            df.columns = [str(c).strip().lower() for c in df.columns]
            col_año = df.columns[0]
            cols_meses_encontradas = []
            for mes in MESES_COLS:
                col = next(
                    (c for c in df.columns if c.strip().lower().startswith(mes[:3])), None
                )
                if col:
                    cols_meses_encontradas.append((mes, col))
            if not cols_meses_encontradas:
                errores.append(f"{sheet}: sin columnas de meses")
                continue
            df[col_año] = df[col_año].astype(str).str.strip()
            df_años = df[df[col_año].str.match(r'^\d{4}$')].copy()
            if df_años.empty:
                errores.append(f"{sheet}: sin filas de años")
                continue
            df_limpio        = pd.DataFrame()
            df_limpio['Año'] = df_años[col_año].astype(int).values
            for mes, col in cols_meses_encontradas:
                df_limpio[mes] = pd.to_numeric(
                    df_años[col], errors='coerce'
                ).values
            df_limpio    = df_limpio.set_index('Año')
            datos[clave] = df_limpio
        except Exception as e:
            errores.append(f"{sheet}: {e}")
    return datos, errores
# =====================================================================
# D2. CALCULAR FACTORES DE CRECIMIENTO [Solución Híbrida]
# =====================================================================
def calcular_factores_crecimiento(datos_crecimiento):
    resultado = {}

    for clave in ['CENDIS', 'REGION']:
        df = datos_crecimiento.get(clave)
        if df is None or df.empty:
            resultado[clave] = {
                'factor_pct':   0.0,
                'año_base':     None,
                'año_actual':   None,
                'meses_usados': [],
                'detalle':      {},
                'error':        f"No se encontró datos para {clave}",
            }
            continue

        años_disponibles = sorted(df.index.tolist())
        if len(años_disponibles) < 2:
            resultado[clave] = {
                'factor_pct': 0.0,
                'error':      f"Se necesitan al menos 2 años en {clave}",
            }
            continue

        MESES_ORDEN = [
            'ene','feb','mar','abr','may','jun',
            'jul','ago','sep','oct','nov','dic'
        ]

        # ═══════════════════════════════════════════════════════════
        # CENDIS — MÉTODO HÍBRIDO (Total + Promedio desde Oct 2025)
        # ═══════════════════════════════════════════════════════════
        if clave == 'CENDIS':

            MES_APERTURA = 'oct'
            AÑO_APERTURA = 2025
            IDX_APERTURA = MESES_ORDEN.index(MES_APERTURA)

            valores_secuenciales = []
            meses_secuenciales   = []

            for año in años_disponibles:
                año_int = int(año)
                for idx_mes, mes in enumerate(MESES_ORDEN):
                    if mes not in df.columns:
                        continue
                    if año_int < AÑO_APERTURA:
                        continue
                    if año_int == AÑO_APERTURA and idx_mes < IDX_APERTURA:
                        continue

                    try:
                        val = float(df.loc[año, mes])
                    except Exception:
                        continue

                    if val != val or val <= 0:
                        continue

                    valores_secuenciales.append(val)
                    meses_secuenciales.append(f"{mes.capitalize()} {año_int}")

            crecimientos = []
            for i in range(1, len(valores_secuenciales)):
                ant = valores_secuenciales[i - 1]
                act = valores_secuenciales[i]
                if ant > 0:
                    crecimientos.append(round((act - ant) / ant * 100, 2))

            factor_promedio   = round(sum(crecimientos) / len(crecimientos), 2) if crecimientos else 0.0
            crecimiento_total = 0.0
            if len(valores_secuenciales) >= 2:
                crecimiento_total = round(
                    (valores_secuenciales[-1] - valores_secuenciales[0])
                    / valores_secuenciales[0] * 100, 2
                )

            resultado[clave] = {
                'factor_pct':           factor_promedio,
                'crecimiento_total':    crecimiento_total,
                'año_base':             años_disponibles[0],
                'año_actual':           años_disponibles[-1],
                'método':               'HÍBRIDO',
                'n_meses_secuenciales': len(valores_secuenciales),
                'n_crecimientos':       len(crecimientos),
                'primer_mes':           meses_secuenciales[0]  if meses_secuenciales else 'N/A',
                'ultimo_mes':           meses_secuenciales[-1] if meses_secuenciales else 'N/A',
                'valor_primer_mes':     round(valores_secuenciales[0],  2) if valores_secuenciales else 0,
                'valor_ultimo_mes':     round(valores_secuenciales[-1], 2) if valores_secuenciales else 0,
                'meses_secuenciales':   meses_secuenciales,
                'crecimientos_lista':   crecimientos,
                'detalle': {
                    'Promedio_Mensual':  f"+{factor_promedio}%",
                    'Crecimiento_Total': f"+{crecimiento_total}%",
                    'Desde':             meses_secuenciales[0]  if meses_secuenciales else 'N/A',
                    'Hasta':             meses_secuenciales[-1] if meses_secuenciales else 'N/A',
                },
                'error': None if valores_secuenciales else 'No hay datos desde Oct 2025',
            }

        # ═══════════════════════════════════════════════════════════
        # REGION — MÉTODO AÑO VS AÑO
        # ═══════════════════════════════════════════════════════════
        else:
            crecimientos_anuales = []
            años_comparados      = []

            for i in range(1, len(años_disponibles)):
                año_anterior  = años_disponibles[i - 1]
                año_siguiente = años_disponibles[i]

                fila_anterior  = df.loc[año_anterior]
                fila_siguiente = df.loc[año_siguiente]

                crecimientos_meses = []

                for mes in MESES_ORDEN:
                    if mes not in df.columns:
                        continue

                    val_sig = fila_siguiente.get(mes, None)
                    val_ant = fila_anterior.get(mes, None)

                    try:
                        val_sig = float(val_sig) if val_sig is not None else None
                        val_ant = float(val_ant) if val_ant is not None else None
                    except (TypeError, ValueError):
                        continue

                    if val_sig is None or val_ant is None:
                        continue
                    if pd.isna(val_sig) or pd.isna(val_ant):
                        continue
                    if val_sig <= 0 or val_ant <= 0:
                        continue

                    pct = round((val_sig - val_ant) / val_ant * 100, 2)
                    crecimientos_meses.append(pct)

                if crecimientos_meses:
                    crecimiento_anual = round(
                        sum(crecimientos_meses) / len(crecimientos_meses), 2
                    )
                    crecimientos_anuales.append(crecimiento_anual)
                    años_comparados.append(f"{año_anterior}→{año_siguiente}")

            factor_pct = round(
                sum(crecimientos_anuales) / len(crecimientos_anuales), 2
            ) if crecimientos_anuales else 0.0

            resultado[clave] = {
                'factor_pct':           factor_pct,
                'año_base':             años_disponibles[0],
                'año_actual':           años_disponibles[-1],
                'método':               'AÑO_VS_AÑO',
                'años_usados':          años_disponibles,
                'años_comparados':      años_comparados,
                'crecimientos_anuales': dict(zip(años_comparados, crecimientos_anuales)),
                'n_años_comparados':    len(crecimientos_anuales),
                'detalle':              dict(zip(años_comparados, crecimientos_anuales)),
                'error':                None,
            }

    return resultado
# =====================================================================
# D3. CALCULAR DIMENSIONAMIENTO DEL CENDIS
# =====================================================================
SUBREGIONES_POR_REGION = {
    'Oriente':          'Oriente Norte (Anzoátegui, Nueva Esparta, Sucre) + Oriente Sur (Bolívar, Delta Amacuro, Amazonas, Monagas)',
    'Capital':          'Distrito Capital, La Guaira, Miranda',
    'Centro':           'Aragua, Carabobo, Cojedes',
    'Centro-Occidente': 'Lara, Portuguesa, Yaracuy, Barinas, Falcón',
    'Occidente-Andes':  'Zulia + Mérida, Trujillo, Táchira',
}

MESES_LISTA = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
]

def calcular_dimensionamiento(factores, region_o_estado, modo, bultos_por_mes_usuario):
    BULTOS_POR_PALLET = 50
    M2_POR_PALLET     = 1.44

    # Filtrar meses con data > 0
    meses_con_data = {
        mes: bultos
        for mes, bultos in bultos_por_mes_usuario.items()
         if bultos is not None and bultos > 0
    }
    if not meses_con_data:
        return None, "❌ Ingresa al menos un mes con bultos > 0"

    # Top 3 meses con mayor volumen
    top3 = sorted(meses_con_data.items(), key=lambda x: x[1], reverse=True)[:3]
    bultos_base = round(sum(v for _, v in top3) / len(top3), 0)
    meses_pico  = [m for m, _ in top3]

    # Proyección
    factor_region = factores.get('REGION', {}).get('factor_pct', 0.0)
    factor_cendis = factores.get('CENDIS', {}).get('factor_pct', 0.0)
    bultos_proy   = round(
        bultos_base
        * (1 + factor_region / 100)
        * (1 + factor_cendis / 100),
        0
    )
    pallets         = math.ceil(bultos_proy / BULTOS_POR_PALLET)
    m2_almacenaje        = round(pallets * M2_POR_PALLET, 1)
    m2_transito          = round(m2_almacenaje * 0.20, 1)
    m2_recomendados      = round(m2_almacenaje + m2_transito, 1)


    return {
    'region_o_estado':    region_o_estado,
    'modo':               modo,
    'bultos_base':        bultos_base,
    'meses_pico':         meses_pico,
    'meses_con_data':     len(meses_con_data),
    'factor_region_pct':  factor_region,
    'factor_cendis_pct':  factor_cendis,
    'multiplicador':      round((1 + factor_region/100) * (1 + factor_cendis/100), 4),
    'bultos_proyectados': bultos_proy,
    'pallets':            pallets,
    'm2_almacenaje':      m2_almacenaje,
    'm2_transito':        m2_transito,
    'm2_recomendados':    m2_recomendados,
    'detalle_meses':      dict(top3),
    }, "OK"
# =====================================================================
def renderizar_dimensionamiento(df_maestro):
    st.markdown("---")
    st.markdown("## Herramienta de Dimensionamiento del CenDis")
    st.caption(
        "Calcula los m² recomendados basándose en el crecimiento "
        "histórico de la región y del CenDis de referencia."
    )

    # ── ARCHIVOS DE CRECIMIENTO ───────────────────────────────────────
    st.markdown("### Archivos de Crecimiento")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        arch_crec_cendis = st.file_uploader(
            "📈 Crecimiento_CenDis.xlsx",
            type=['xlsx'], key="dim_crec_cendis",
            help="Tabla pivote: Año × Meses con Kg del CenDis BQTO"
        )
    with col_c2:
        arch_crec_region = st.file_uploader(
            "📈 Crecimiento_Region.xlsx",
            type=['xlsx'], key="dim_crec_region",
            help="Tabla pivote: Año × Meses con Kg de la región"
        )
    if arch_crec_cendis is not None:
        st.session_state['_dim_cendis_bytes'] = arch_crec_cendis.read()
        arch_crec_cendis.seek(0)
    if arch_crec_region is not None:
        st.session_state['_dim_region_bytes'] = arch_crec_region.read()
        arch_crec_region.seek(0)
    cendis_bytes = st.session_state.get('_dim_cendis_bytes')
    region_bytes = st.session_state.get('_dim_region_bytes')
    if not cendis_bytes or not region_bytes:
        faltantes = []
        if not cendis_bytes: faltantes.append("Crecimiento_CenDis")
        if not region_bytes: faltantes.append("Crecimiento_Region")
        st.warning(f"⚠️ Faltan archivos: {', '.join(faltantes)}")
        return
    cache_key = (len(cendis_bytes), len(region_bytes))
    if st.session_state.get('_dim_cache_key') != cache_key:
        with st.spinner("Calculando factores de crecimiento..."):
            datos_cendis, _ = cargar_crecimiento(
                io.BytesIO(cendis_bytes), clave_forzada='CENDIS'
            )
            datos_region, _ = cargar_crecimiento(
                io.BytesIO(region_bytes), clave_forzada='REGION'
            )
            datos_combinados = {
                'CENDIS': datos_cendis.get(
                    'CENDIS',
                    list(datos_cendis.values())[0] if datos_cendis else None
                ),
                'REGION': datos_region.get(
                    'REGION',
                    list(datos_region.values())[0] if datos_region else None
                ),
            }
    
            st.session_state['_dim_factores']  = calcular_factores_crecimiento(datos_combinados)
            st.session_state['_dim_cache_key'] = cache_key
    factores = st.session_state['_dim_factores']

    st.markdown("### Factores de Crecimiento Calculados")
    factor_region_pct = factores.get('REGION', {}).get('factor_pct', 0.0)
    factor_cendis_pct = factores.get('CENDIS', {}).get('factor_pct', 0.0)
    crec_total_cendis = factores.get('CENDIS', {}).get('crecimiento_total', 0.0)
    multiplicador     = round(
        (1 + factor_region_pct/100) * (1 + factor_cendis_pct/100), 4
    )

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        año_r = factores.get('REGION', {})
        st.metric("📍 Crec. Región",    f"+{fmt_pct(factor_region_pct)}%",
            delta=f"{año_r.get('año_base','')} → {año_r.get('año_actual','')}")

    with col_f2:
        año_c = factores.get('CENDIS', {})
        factor_promedio_pct = año_c.get('factor_pct', 0.0)

        st.metric(
            "🏭 Crec. CenDis BQTO (Promedio)",
            f"+{fmt_pct(factor_promedio_pct)}%",
            # ✅ Usar primer_mes y ultimo_mes (no año_base → año_actual)
            delta=f"{año_c.get('primer_mes', '')} → {año_c.get('ultimo_mes', '')}"
        )
        st.caption(f"📈 **Crecimiento total**: +{fmt_pct(crec_total_cendis)}% desde apertura")
    
    with col_f3:
        st.metric("✖️ Multiplicador Total", f"×{fmt_pct(multiplicador, 4)}",
            delta=f"+{round((multiplicador-1)*100,1)}% sobre volumen base")
        st.caption(f"💡 Usa promedio mensual (+{fmt_pct(factor_cendis_pct)}%) para dimensionamiento")

    st.markdown("---")

    # ── PARÁMETROS ────────────────────────────────────────────────────
    st.markdown("### Parámetros del Dimensionamiento")
    col_d1, _ = st.columns(2)
    with col_d1:
        modo_dim = st.radio(
            "Modo:", options=["REGIÓN", "ESTADO"],
            horizontal=True, key="dim_modo"
        )
        if modo_dim == "REGIÓN":
            region_dim = st.selectbox(
                "📍 Región a dimensionar:",
                options=REGIONES_DIRECTAS + REGIONES_VIA_CCS + REGIONES_VIA_BQTO,
                key="dim_region"
            )
        else:
            estados_disponibles = sorted(
                df_maestro['Estado'].dropna().unique().tolist()
            ) if 'Estado' in df_maestro.columns else []
            region_dim = st.selectbox(
                "🗺️ Estado a dimensionar:",
                options=estados_disponibles,
                key="dim_estado"
            )

    # ── RECORDATORIO DE SUBREGIONES ───────────────────────────────────
    subregion_txt = SUBREGIONES_POR_REGION.get(region_dim, '')
    if subregion_txt:
        st.info(f"📍 **{region_dim}** comprende: {subregion_txt}")

    # ── INPUT DE BULTOS POR MES ───────────────────────────────────────
    st.markdown("### Bultos/Cajas por Mes")
    st.caption(
        "Ingresa el total de bultos/cajas de la región para cada mes. "
        "Deja en 0 los meses sin data — el sistema usará solo los meses con valores."
    )

    # Tabla de input — 2 columnas de 6 meses
    bultos_por_mes = {}
    col_m1, col_m2 = st.columns(2)
    for i, mes in enumerate(MESES_LISTA):
        key = f"dim_bultos_{mes}"
        col = col_m1 if i < 6 else col_m2
        with col:
            bultos_por_mes[mes] = st.number_input(
                mes,
                min_value=0,
                value=None,
                step=100,
                key=key,
                format="%d",
                placeholder="Cantidad..."
            )

    meses_ingresados = sum(1 for v in bultos_por_mes.values() if v is not None and v > 0)
    if meses_ingresados > 0:
        total_bultos = sum(v for v in bultos_por_mes.values() if v is not None)
        st.caption(
            f"✅ {meses_ingresados} meses con data | "
            f"Total período: {fmt_num(total_bultos)} bultos | "
            f"Promedio mensual: {fmt_num(round(total_bultos/meses_ingresados))} bultos"
        )
    else:
        st.caption("💡 Ingresa los valores de al menos 1 mes para calcular.")

    # ── BOTÓN Y CÁLCULO ───────────────────────────────────────────────
    btn_dim = st.button(
        "📐 Calcular Dimensionamiento",
        use_container_width=True,
        key="dim_btn"
    )
    if not btn_dim:
        st.info("💡 Completa los bultos por mes y presiona **Calcular Dimensionamiento**.")
        return
    if meses_ingresados == 0:
        st.warning("⚠️ Ingresa al menos un mes con bultos > 0.")
        return

    with st.spinner("Calculando dimensionamiento..."):
        resultado_dim, msg_dim = calcular_dimensionamiento(
            factores            = factores,
            region_o_estado     = region_dim,
            modo                = modo_dim,
            bultos_por_mes_usuario = bultos_por_mes,
        )
    if resultado_dim is None:
        st.error(msg_dim)
        return

    # ── RESULTADOS ────────────────────────────────────────────────────
    st.markdown(
        f"### 📐 Dimensionamiento Recomendado — "
        f"{'Región' if modo_dim == 'REGIÓN' else 'Estado'} **{region_dim}**"
    )
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    with col_r1:
        st.metric("📦 Bultos Base",
              f"{fmt_num(resultado_dim['bultos_base'])}",
              delta=f"Promedio top {len(resultado_dim['meses_pico'])} meses")
    with col_r2:
        st.metric("📦 Bultos Proyectados",
                  f"{fmt_num(resultado_dim['bultos_proyectados'])}",
                  delta=f"×{resultado_dim['multiplicador']}")
    with col_r3:
        st.metric("🏗️ Pallets Necesarios", f"{fmt_num(resultado_dim['pallets'])}")
    with col_r4:
        st.metric("📐 M² Recomendados",
                  f"{fmt_num(resultado_dim['m2_recomendados'], 1)} m²",
                  delta="Piso, sin racks")
    with st.expander("🔍 Ver desglose del cálculo", expanded=False):
        st.markdown("##### 📊 Top 3 meses pico")
        st.dataframe(
            pd.DataFrame([
                {'Mes': mes, 'Bultos/Cajas': fmt_num(bultos)}
                for mes, bultos in resultado_dim['detalle_meses'].items()
            ]),
            use_container_width=True, hide_index=True
        )
        meses_pico_str = ', '.join(resultado_dim['meses_pico'])
        st.code(f"""
DIMENSIONAMIENTO — {region_dim}
{'='*45}
Meses Pico (top 3):           {meses_pico_str}
Bultos Base (promedio top 3):  {fmt_num(resultado_dim['bultos_base'])} bultos
Factor Crecimiento Región:    +{resultado_dim['factor_region_pct']:.2f}%
Factor Crecimiento CenDis:    +{resultado_dim['factor_cendis_pct']:.2f}%
Multiplicador Total:          ×{resultado_dim['multiplicador']:.4f}
Bultos Proyectados:            {fmt_num(resultado_dim['bultos_proyectados'])} bultos
Pallets Necesarios:            {fmt_num(resultado_dim['pallets'])}
  = ceil({fmt_num(resultado_dim['bultos_proyectados'])} ÷ 50)
M² Almacenaje (piso):          {fmt_num(resultado_dim['m2_almacenaje'], 1)} m²
  = {fmt_num(resultado_dim['pallets'])} pallets × 1,44 m²/pallet
M² Tránsito (+20%):            {fmt_num(resultado_dim['m2_transito'], 1)} m²
─────────────────────────────────────────────
M² TOTALES Recomendados:       {fmt_num(resultado_dim['m2_recomendados'], 1)} m²
""", language='text')
# =====================================================================
# UI — MÓDULO PRINCIPAL
# =====================================================================
def renderizar_objetivo1(resultado):
    if resultado is None:
        return
    region     = resultado['region']
    tipo_ruta  = resultado['tipo_ruta']
    meses      = resultado['meses_usados']
    costo_mes  = resultado['costo_por_mes']
    costo_prom = resultado['costo_promedio_mes']
    viajes_mes = resultado['viajes_por_mes']
    viajes_avg = resultado['viajes_promedio']
    detalle    = resultado['detalle_por_mes']

    st.markdown(f"### Costo Red Actual — Región {region}")
    st.caption(
        f"Ruta: **{tipo_ruta}** | "
        f"Meses analizados: **{', '.join([NOMBRE_MES[m] for m in meses])}**"
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💸 Costo Promedio Mensual", f"${fmt_num(costo_prom)}")
    with col2:
        st.metric("🚛 Viajes Promedio/Mes",    f"{sum(viajes_avg.values())}")
    with col3:
        st.metric("📅 Meses con Datos",        f"{len(meses)}")

    st.markdown("#### Viajes y Costos por Mes")
    filas = []
    for mes in meses:
        fila = {'Mes': NOMBRE_MES[mes]}
        total_viajes = 0
        for vehiculo in VEHICULOS:
            v = viajes_mes.get(mes, {}).get(vehiculo, 0)
            fila[vehiculo] = v
            total_viajes  += v
        fila['Total Viajes'] = total_viajes
        fila['Costo ($)']    = f"${fmt_num(costo_mes.get(mes, 0))}"
        filas.append(fila)
    fila_prom = {'Mes': '📊 Promedio'}
    for vehiculo in VEHICULOS:
        fila_prom[vehiculo] = viajes_avg.get(vehiculo, 0)
    fila_prom['Total Viajes'] = sum(viajes_avg.values())
    fila_prom['Costo ($)']    = f"${fmt_num(costo_prom)}"
    filas.append(fila_prom)
    st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    with st.expander("🔍 Desglose por vehículo y mes", expanded=False):
        for mes in meses:
            st.markdown(f"##### {NOMBRE_MES[mes]}")
            det_mes = detalle.get(mes, {})
            if not det_mes:
                continue
            filas_det = []
            for vehiculo, datos in det_mes.items():
                if datos.get('Tipo') == 'DIRECTO':
                    filas_det.append({
                        'Vehículo':        vehiculo,
                        'Viajes':          datos.get('Viajes', 0),
                        'Tarifa ($)':      f"${fmt_num(datos.get('Tarifa', 0), 2)}",
                        'Caleta ($)':      f"${fmt_num(datos.get('Caleta', 0))}",
                        'Costo Total ($)': f"${fmt_num(datos.get('Costo', 0))}",
                    })
                else:
                    filas_det.append({
                        'Vehículo':        vehiculo,
                        'Viajes T1':       datos.get('Viajes_T1', 0),
                        'Costo T1 ($)':    f"${fmt_num(datos.get('Costo_T1', 0))}",
                        'Viajes T2':       datos.get('Viajes_T2', 0),
                        'Costo T2 ($)':    f"${fmt_num(datos.get('Costo_T2', 0))}",
                        'Costo Total ($)': f"${fmt_num(datos.get('Costo', 0))}",
                    })
            st.dataframe(
                pd.DataFrame(filas_det),
                use_container_width=True, hide_index=True
            )
def modulo_analisis_financiero(
    df_ventas_raw,
    df_maestro,
    puntos_vol,
    puntos_val,
    nombre_p,
    lat_p,
    lon_p,
    lista_cendis_existentes,
    archivo_maestro=None,
):
    st.markdown("## Análisis Financiero — Red Actual vs Red Propuesta")
    st.caption(
        "Comparación de costos logísticos basada en "
        "tabuladores reales y viajes históricos."
    )

    # PASO 1 — CARGA DE ARCHIVOS
    st.markdown("### Paso 1 — Carga de Archivos")
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        arch_viajes = st.file_uploader(
            "🚛 Numero_Viajes.xlsx",
            type=['xlsx'], key="fin_viajes"
        )
    with col_u2:
        arch_tab = st.file_uploader(
            "📋 tabulador.xlsx",
            type=['xlsx'], key="fin_tab"
        )
    with col_u3:
        arch_consol = st.file_uploader(
            "📊 Consolidado_Cendis.xlsx",
            type=['xlsx'], key="fin_consol"
        )

    archivos_ok = all([arch_viajes, arch_tab, arch_consol])
    if not archivos_ok:
        faltantes = []
        if not arch_viajes: faltantes.append("Numero_Viajes")
        if not arch_tab:    faltantes.append("tabulador")
        if not arch_consol: faltantes.append("Consolidado_Cendis")
        st.warning(f"⚠️ Faltan archivos: {', '.join(faltantes)}")
        return

    df_viajes   = pd.DataFrame()
    tabs        = {}
    tab_err     = []
    consolidado = None
    consol_msg  = ""
    tabs_co     = pd.DataFrame()
    co_msg      = "Sin archivo Maestro"
    costo_km    = {}
    meses_ok    = []
    meses_err   = []

    with st.spinner("Cargando archivos..."):
        df_viajes, meses_ok, meses_err = cargar_numero_viajes(arch_viajes)
        tabs, tab_err                   = cargar_tabulador(arch_tab)
        consolidado, consol_msg         = cargar_consolidado(arch_consol)

    # ── CENTRO-ORIENTE: Maestro primero, tabulador como fallback ──
    if archivo_maestro is not None:
        tabs_co, co_msg = cargar_centro_oriente(archivo_maestro)
        if tabs_co.empty and 'CENTRO-ORIENTE' in tabs:
            tabs_co = tabs['CENTRO-ORIENTE']
            co_msg  = "✅ CENTRO-ORIENTE cargado desde tabulador.xlsx"
    elif 'CENTRO-ORIENTE' in tabs:
        tabs_co = tabs['CENTRO-ORIENTE']
        co_msg  = "✅ CENTRO-ORIENTE cargado desde tabulador.xlsx"
    else:
        tabs_co = pd.DataFrame()
        co_msg  = "Sin CENTRO-ORIENTE"

    costo_km = calcular_costo_km(tabs_co)

    # ✅ ADVERTENCIAS DE DECIMALES VISIBLE (fuera del expander)
    advertencias_decimales = [e for e in meses_err if '⚠️' in e and 'decimales' in e.lower()]
    if advertencias_decimales:
        st.warning(
            "### ⚠️ Valores Decimales Detectados en Numero_Viajes.xlsx\n\n"
            "Algunos meses contienen valores decimales en las columnas de viajes. "
            "Para mayor precisión en los cálculos, se recomienda **redondear manualmente** "
            "estos valores en el archivo Excel antes de subirlo.\n\n"
            f"**Meses afectados**: {len(advertencias_decimales)}"
        )
        with st.expander("📋 Ver detalle de advertencias", expanded=False):
            for adv in advertencias_decimales:
                st.caption(adv)

    # Validar archivos cargados
    if consolidado is None or df_viajes.empty:
        st.error("❌ Hay archivos con problemas. Revisa los Debug.")
        return

    # Aviso separado si no hay CENTRO-ORIENTE (no bloquea)
    if tabs_co.empty:
        st.warning(
            "⚠️ No se encontró CENTRO-ORIENTE en el Maestro. "
            "Los cálculos de tarifa por distancia no estarán disponibles."
        )

    st.markdown("---")
    mostrar_debug = st.toggle("🔍 Mostrar información de diagnóstico", value=False, key="fin_mostrar_debug")
    # DEBUG 1 — VIAJES
    if mostrar_debug:
        with st.expander("🔍 Debug 1 — Numero_Viajes", expanded=False):
            st.markdown("##### ✅ Meses leídos")
            for m in meses_ok:
                st.caption(m)

        errores_otros = [e for e in meses_err if e not in advertencias_decimales]
        if errores_otros:
            st.markdown("##### ⚠️ Otros Errores")
            for e in errores_otros:
                st.warning(e)

        if not df_viajes.empty:
            st.markdown("##### 📊 Viajes por Subregión Original")
            for subregion in sorted(df_viajes['Subregion'].unique()):
                region_grande = df_viajes[
                    df_viajes['Subregion'] == subregion
                ]['Region'].iloc[0]
                st.markdown(f"**{subregion}** → Región: {region_grande}")
                df_sub = df_viajes[df_viajes['Subregion'] == subregion].copy()
                df_sub['Mes_Nombre'] = df_sub['Mes'].map(NOMBRE_MES)
                cols_show = ['Mes_Nombre'] + [v for v in VEHICULOS if v in df_sub.columns]
                st.dataframe(
                    df_sub[cols_show].rename(columns={'Mes_Nombre': 'Mes'}),
                    use_container_width=True, hide_index=True
                )

    # DEBUG 2 — TABULADORES
    if mostrar_debug:
        with st.expander("🔍 Debug 2 — Tabuladores", expanded=False):
            if tab_err:
                for e in tab_err:
                    st.warning(f"⚠️ {e}")
            for nombre_tab, df_tab in tabs.items():
                st.markdown(f"##### 📋 {nombre_tab}")
                if df_tab.empty:
                    st.warning(f"❌ {nombre_tab} vacío")
                else:
                    st.caption(f"{len(df_tab)} destinos cargados")
                    st.dataframe(df_tab.head(10), use_container_width=True)
        st.markdown("##### 📋 CENTRO-ORIENTE (desde Maestro)")
        if tabs_co.empty:
            st.warning(f"⚠️ {co_msg}")
        else:
            st.caption(f"{len(tabs_co)} destinos cargados")
            st.dataframe(tabs_co.head(10), use_container_width=True)
        st.markdown("##### 💲 Costo/KM por Vehículo")
        if costo_km:
            st.dataframe(
                pd.DataFrame([
                    {
                        'Vehículo':     v,
                        'Costo/KM ($)': f"${costo_km.get(v, 0):.4f}",
                        'Caleta ($)':   f"${VEHICULOS_CALETAS.get(v, 0):.0f}",
                    }
                    for v in VEHICULOS
                ]),
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("❌ No se pudo calcular Costo/KM")

    # DEBUG 3 — CONSOLIDADO
    if mostrar_debug:
        with st.expander("🔍 Debug 3 — Consolidado CenDis", expanded=False):
            if consolidado is None:
                st.error(f"❌ {consol_msg}")
            else:
                st.success(consol_msg)
                for cendis_nombre, datos in consolidado.items():
                    st.markdown(f"##### 🏭 CenDis {cendis_nombre}")
                    st.dataframe(
                        pd.DataFrame([{'Concepto': k, 'Valor': v} for k, v in datos.items()]),
                        use_container_width=True, hide_index=True
                    )

    st.markdown("---")

    # ── SINCRONIZACIÓN DE REGIÓN (definir ANTES de usarlas) ──────────
    regiones_disponibles = sorted(df_maestro['Region'].dropna().unique().tolist())

    if 'region_sincronizada' not in st.session_state:
        st.session_state['region_sincronizada'] = regiones_disponibles[1]

    def sync_desde_paso2():
        st.session_state['region_sincronizada'] = st.session_state['region_paso2']

    def sync_desde_paso3():
        st.session_state['region_sincronizada'] = st.session_state['region_paso3']

    # PASO 2 — OBJETIVO 
    st.markdown("### Paso 2 — Costo Actual de la Red")
    col_r1 = st.columns(1)[0]
    
    with col_r1:
        region_paso2 = st.selectbox(
            "📍 Región a analizar:",
            options=regiones_disponibles,
            index=regiones_disponibles.index(st.session_state['region_sincronizada']),
            key="region_paso2",
            on_change=sync_desde_paso2
        )
    
    st.session_state['region_sugerida'] = region_paso2
    region = region_paso2
    
    resultado_obj1, msg_obj1 = calcular_costo_actual_region(
        region          = region_paso2,
        df_viajes       = df_viajes,
        tabs_co         = tabs_co,
        tab_extra       = tabs,
        consolidado     = consolidado,
        pasa_por_cendis = False,
        cual_cendis     = None,
    )
    if resultado_obj1 is None:
        st.error(msg_obj1)
        return

    if mostrar_debug:
        with st.expander("🔍 Debug 4 — Objetivo 1 Detalle", expanded=False):
            st.json({
                'Region':       resultado_obj1['region'],
                'Tipo_Ruta':    resultado_obj1['tipo_ruta'],
                'Meses_Usados': resultado_obj1['meses_usados'],
            })
            st.markdown("##### Costo por Mes")
            st.json(resultado_obj1['costo_por_mes'])
            st.markdown("##### Viajes Promedio por Vehículo")
            st.json(resultado_obj1['viajes_promedio'])
            if resultado_obj1['detalle_por_mes']:
                ultimo_mes = max(resultado_obj1['detalle_por_mes'].keys())
                st.markdown(f"##### Detalle último mes ({NOMBRE_MES[ultimo_mes]})")
                st.json(resultado_obj1['detalle_por_mes'][ultimo_mes])

    renderizar_objetivo1(resultado_obj1)
    st.markdown("---")

    # PASO 3 — PARÁMETROS USUARIO
    st.markdown("### Paso 3 — Configurar Nuevo CenDis")
    st.caption("Introduzca los parametros para configurar el nuevo cendis")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        modo = st.radio(
            "Modo de análisis:",
            options=["REGIÓN", "ESTADO"],
            horizontal=True,
            key="fin_modo"
        )
        ciudades_disponibles = sorted(CIUDADES_VENEZUELA.keys())
        ciudad_cendis_sel = st.selectbox(
            "🏙️ Ciudad del nuevo CenDis:",
            options=[""] + ciudades_disponibles,
            format_func=lambda x: "Selecciona una ciudad..." if x == "" else x.title(),
            key="fin_ciudad_cendis"
        )
        ciudad_cendis = ciudad_cendis_sel if ciudad_cendis_sel else ""

        if modo == "REGIÓN":
            region_paso3 = st.selectbox(
                "📍 Región que atenderá: (debe coincidir con la región seleccionda del Paso 2)",
                options=regiones_disponibles,
                index=regiones_disponibles.index(st.session_state['region_sincronizada']),
                key="region_paso3",
                on_change=sync_desde_paso3
            )
            region_o_estado = region_paso3  # ← fuente única de verdad

        else:
            estados_disponibles = sorted(
                df_maestro['Estado'].dropna().unique().tolist()
            ) if 'Estado' in df_maestro.columns else []
            region_o_estado = st.selectbox(
                "🗺️ Estado que atenderá:",
                options=estados_disponibles,
                key="fin_estado_sel"
            )

        cendis_ref = st.selectbox(
            "🏭 CenDis de referencia:",
            options=['BQTO', 'CCS'],
            key="fin_cendis_ref"
        )

    with col_p2:
        pct_default = 9.83 if cendis_ref == 'BQTO' else 8.62
        pct_gastos = st.number_input(
            "⚙️ % Gastos/Ventas: (usar punto (' . ' para marcar decimal · ej: 9.83)",
            min_value=0.0, max_value=30.0,
            value=pct_default,
            step=0.1,
            help="Benchmark CCS: 8.62% | BQTO: 9.83% — Streamlit requiere punto (.) como separador decimal",
            key=f"fin_pct_gastos_{cendis_ref}"
        )

    ratio_sug   = consolidado.get(cendis_ref, {}).get('Ratio_Acarreos_Kg', 0.0)
    kg_base_est = 0.0
    if modo == 'REGIÓN':
        df_tmp = df_maestro.copy()
        df_tmp['Region_C'] = df_tmp.apply(
            lambda r: clasificar_region(r.get('Ciudad', ''), r.get('Estado', ''))[0], axis=1
        )
        kg_base_est = df_tmp[df_tmp['Region_C'] == region_o_estado]['Peso_KG'].sum()
    elif 'Estado' in df_maestro.columns:
        kg_base_est = df_maestro[
            df_maestro['Estado'].astype(str).str.upper().str.strip()
            == str(region_o_estado).upper().strip()
        ]['Peso_KG'].sum()

    viajes_sug = math.ceil(kg_base_est * ratio_sug) if kg_base_est > 0 and ratio_sug > 0 else 0

    if ratio_sug > 0 and viajes_sug > 0:
        st.caption(
            f"💡 Ratio sugerido ({cendis_ref}): "
            f"{ratio_sug:.6f} viajes/kg → "
            f"**{viajes_sug} viajes/mes**"
        )

    viajes_repo = st.number_input(
        "🔄 Viajes de reposición/mes:",
        min_value=0, max_value=200,
        value=int(viajes_sug),
        step=1,
        key="fin_viajes_repo"
    )
    btn_calcular = st.button(
        "🚀 Calcular Comparación",
        use_container_width=True,
        key="fin_btn_calcular"
    )
    if btn_calcular:
        st.session_state['_fin_calcular_ok'] = True
    if not st.session_state.get('_fin_calcular_ok', False):
        st.info("💡 Configura los parámetros y presiona **Calcular Comparación**.")
        return
    if not ciudad_cendis:
        st.warning("⚠️ Ingresa la ciudad del nuevo CenDis.")
        return

    # PASO 4 — OBJETIVO 2
    with st.spinner("Calculando costo del nuevo CenDis..."):
        resultado_obj2, msg_obj2 = calcular_objetivo2(
            modo                  = modo,
            region_o_estado       = region_o_estado,
            ciudad_cendis         = ciudad_cendis,
            df_maestro            = df_maestro,
            df_ventas_raw         = df_ventas_raw,
            df_viajes             = df_viajes,
            consolidado           = consolidado,
            tabs_co               = tabs_co,
            tab_extra             = tabs,
            costo_km_por_vehiculo = costo_km,
            pct_gastos_ventas     = pct_gastos,
            viajes_repo_usuario   = int(viajes_repo),
            cendis_ref            = cendis_ref,
        )
    if resultado_obj2 is None:
        st.error(msg_obj2)
        return
    
    if mostrar_debug:
        with st.expander("🔍 Debug 5 — Objetivo 2 Detalle", expanded=False):
            debug2 = resultado_obj2['debug']
            st.markdown("##### Venta Base y Kg")
            st.json({
                'Modo':           modo,
                'Region_Estado':  region_o_estado,
                'Ciudad_CenDis':  ciudad_cendis,
                'Venta_Base_USD': debug2.get('Venta_Base_USD', 0),
                'Kg_Base':        debug2.get('Kg_Base', 0),
            })
            st.markdown("##### Gasto Operacional")
            st.json(debug2.get('Gasto_Operacional', {}))
            st.markdown("##### Reposición")
            st.json(debug2.get('Reposicion', {}))
            if modo == 'ESTADO':
                st.markdown("##### Modo Estado")
                st.json(debug2.get('modo_estado', {}))
                if 'aviso' in debug2:
                    st.warning(debug2['aviso'])
                if resultado_obj2.get('resultado_estado'):
                    df_cl = resultado_obj2['resultado_estado']['df_clientes']
                    if not df_cl.empty:
                        st.markdown("##### Clientes con Flete Estimado")
                        st.dataframe(
                            df_cl[[
                                'Id. Cliente', 'Ciudad', 'Estado',
                                'Distancia_KM', 'Valor_USD',
                                'Peso_KG', 'Flete_Estimado'
                            ]].sort_values('Distancia_KM'),
                            use_container_width=True,
                            hide_index=True
                        )
            st.markdown("##### Resumen")
            st.json(debug2.get('RESUMEN', {}))
    st.markdown("### Paso 4 — Costo Mensual del Nuevo CenDis")
    col_k1, col_k2, col_k3 = st.columns(3)
    with col_k1:
        st.metric("💵 Venta Base",          f"${fmt_num(resultado_obj2['venta_base'])}")
    with col_k2:
        st.metric("⚙️ Gasto Operacional",   f"${fmt_num(resultado_obj2['gasto_operacional'])}",
                  delta=f"{str(round(pct_gastos, 2)).replace('.', ',')}% sobre ventas")
    with col_k3:
        st.metric("🔄 Costo Reposición",    f"${fmt_num(resultado_obj2['costo_reposicion'])}",
                  delta=f"{int(viajes_repo)} viajes/mes")
    st.markdown("---")  # ← fuera de las columnas, correcto
    # PASO 5 — OBJETIVO 3
    with st.spinner("Calculando comparación..."):
        resultado_obj3, msg_obj3 = calcular_objetivo3(
            resultado_obj1, resultado_obj2
        )
    if resultado_obj3 is None:
        st.error(msg_obj3)
        return
    
    if mostrar_debug:
        with st.expander("🔍 Debug 6 — Objetivo 3 Detalle", expanded=False):
            debug3 = resultado_obj3['debug']
            st.markdown("##### Comparación Base")
            st.json(debug3.get('COMPARACION_BASE', {}))
            st.markdown("##### Acumulado Muestra")
            st.json(debug3.get('ACUMULADO_MUESTRA', {}))
        st.markdown("### Paso 5 — Comparación Red Actual vs Propuesta")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.metric("🏭 Red Actual/Mes",    f"${fmt_num(resultado_obj3['costo_actual_mes'])}")
    with col_c2:
        st.metric("🏗️ Red Propuesta/Mes", f"${fmt_num(resultado_obj3['costo_propuesto_mes'])}")
    # Gráfico comparativo mensual — Barras agrupadas
    st.markdown("#### Costo Mensual — Red Actual vs Red Propuesta")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='🏭 Red Actual',
        x=['Costo Mensual'],
        y=[resultado_obj3['costo_actual_mes']],
        marker_color='#E60F29',
        text=[f"${fmt_num(resultado_obj3['costo_actual_mes'])}"],
        textposition='outside',
    ))
    fig.add_trace(go.Bar(
        name='🏗️ Red Propuesta',
        x=['Costo Mensual'],
        y=[resultado_obj3['costo_propuesto_mes']],
        marker_color='#00C853',
        text=[f"${resultado_obj3['costo_propuesto_mes']:,.0f}"],
        textposition='outside',
    ))
    fig.update_layout(
        template='plotly_dark',
        barmode='group',
        yaxis_title='Costo Mensual ($)',
        legend=dict(orientation="h", y=1.1),
        height=400,
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True)
    # HERRAMIENTA DE DIMENSIONAMIENTO (al final)
    renderizar_dimensionamiento(df_maestro)