import pandas as pd
import numpy as np
import streamlit as st
import os
import folium
import re
from streamlit_folium import st_folium
from sklearn.cluster import KMeans
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# ── Importaciones compartidas ─────────────────────────────────────────
from utils_munchy import (
    clasificar_region,
    obtener_tarifa_gandola,
    obtener_coords_ciudad,
    TARIFAS_GANDOLA,
    CIUDADES_VENEZUELA,
    CALETA_GANDOLA,
    _distancia,
)
import importlib
import modulo_analisis_financiero
importlib.reload(modulo_analisis_financiero)
from modulo_analisis_financiero import modulo_analisis_financiero  

def fmt_num(valor, decimales=0):
    """Formatea números al estilo latinoamericano: miles con punto, decimales con coma."""
    if decimales == 0:
        return f"{valor:,.0f}".replace(",", ".")
    else:
        # Primero formateamos con coma americana, luego invertimos separadores
        s = f"{valor:,.{decimales}f}"
        # "1,234,567.89" → "1.234.567,89"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s

# =====================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y ESTILOS
# =====================================================================
st.set_page_config(
    page_title="Munchy - Optimización CENDIS",
    page_icon="🏭",
    layout="wide"
)

ruta_logo = "Munchy logo.png"
if os.path.exists(ruta_logo):
    st.sidebar.image(ruta_logo, use_container_width=True)
st.sidebar.markdown("---")

munchy_style = """
<style>
.stApp { background-color: #0F2260 !important; }
h1, h2, h3, h4, h5, h6, p, label, span, .stMarkdown { color: #FFFFFF !important; }
section[data-testid="stSidebar"] { background-color: #0A1846 !important; }

/* ── FILE UPLOADER ─────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border: 1.5px dashed rgba(255, 255, 255, 0.4) !important;
    border-radius: 8px !important;
    padding: 8px !important;
}
[data-testid="stFileUploader"] label {
    color: #FFFFFF !important;
}
[data-testid="stFileUploader"] p,
[data-testid="stFileUploader"] span,
[data-testid="stFileUploader"] small {
    color: #CCCCCC !important;
}
[data-testid="stFileUploadDropzone"] {
    background-color: rgba(255, 255, 255, 0.03) !important;
    border: none !important;
}

/* ── BOTONES ───────────────────────────────────────────── */
div.stButton > button {
    background-color: rgba(230, 15, 41, 0.7) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(230, 15, 41, 0.9) !important;
    border-radius: 6px !important;
    font-weight: bold !important;
}
div.stButton > button:hover {
    background-color: rgba(230, 15, 41, 1.0) !important;
    border-color: #FFFFFF !important;
}
</style>
"""
st.markdown(munchy_style, unsafe_allow_html=True)

# =====================================================================
# 2. PANEL LATERAL CONTROLES
# =====================================================================
def modulo_controles_simulacion():
    st.sidebar.header("Panel de Simulación Logística")
    
    modalidad = st.sidebar.radio(
        "Seleccione el Escenario Logístico:",
        options=[
            "1. Red Actual (Planta La Morita + CenDis Existentes)",
            "2. Red Teórica desde Cero (Solo Planta Origen)"
        ]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Parámetros de Planta Origen")
    nombre_planta = st.sidebar.text_input("Nombre de la Instalación:", value="Planta La Morita")
    lat_planta    = st.sidebar.number_input("Latitud de Planta:",  value=10.2442,  format="%.5f", step=0.0001)
    lon_planta    = st.sidebar.number_input("Longitud de Planta:", value=-67.4764, format="%.5f", step=0.0001)
    
    lista_cendis_existentes = []
    if "1. Red Actual" in modalidad:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Configuración de CenDis Existentes")
        cant_existentes = st.sidebar.number_input(
            "¿Cuántos CenDis operan actualmente?", min_value=1, max_value=5, value=2, step=1
        )
        
        def_nombres = ["CenDis Capital", "CenDis Barquisimeto"]
        def_lats    = [10.4806, 10.0644]
        def_lons    = [-66.9036, -69.3570]
        
        for i in range(int(cant_existentes)):
            with st.sidebar.expander(f"CenDis Existente #{i+1}", expanded=False):
                n_c   = st.text_input(f"Nombre:", value=def_nombres[i] if i < len(def_nombres) else f"CenDis {i+1}", key=f"nc_{i}")
                lat_c = st.number_input(f"Latitud:",  value=def_lats[i] if i < len(def_lats) else 10.0,  format="%.5f", step=0.0001, key=f"latc_{i}")
                lon_c = st.number_input(f"Longitud:", value=def_lons[i] if i < len(def_lons) else -66.0, format="%.5f", step=0.0001, key=f"lonc_{i}")
                lista_cendis_existentes.append({"nombre": n_c, "lat": lat_c, "lon": lon_c})
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Concentración de Clientes")
    radio_kernel = st.sidebar.slider(
        "Radio de influencia entre vecinos:",
        min_value=0.10, max_value=1.50, value=0.45, step=0.05,
    )
    
    km_activos = round(radio_kernel * 111)
    if radio_kernel <= 0.25:
        modo = "🔬 Modo Barrio"
        desc = "Solo clientes muy cercanos se influencian entre sí."
        color_txt = "#FFD700"
    elif radio_kernel <= 0.60:
        modo = "Modo Ciudad"
        desc = "Balance recomendado. Clientes dentro de una misma área metropolitana."
        color_txt = "#4CAF50"
    elif radio_kernel <= 1.00:
        modo = "Modo Estado"
        desc = "Influencia regional amplia."
        color_txt = "#FF9800"
    else:
        modo = "Modo Regional"
        desc = "Influencia muy amplia. Clientes dispersos en regiones enteras."
        color_txt = "#F44336"
    
    st.sidebar.markdown(
        f"""
        <div style="
            background-color: rgba(255,255,255,0.07);
            border-left: 3px solid {color_txt};
            padding: 8px 12px;
            border-radius: 4px;
            margin-top: 4px;
        ">
            <span style="color:{color_txt}; font-weight:bold;">{modo}</span><br>
            <span style="color:#CCCCCC; font-size:0.85em;">
                Radio activo: <b>{radio_kernel}°</b> ≈ <b>{km_activos} km</b><br>
                {desc}
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    return modalidad, nombre_planta, lat_planta, lon_planta, lista_cendis_existentes, radio_kernel  

# =====================================================================
# 3. FUNCIONES DE SANEAMIENTO
# =====================================================================
def normalizar_identificador_cliente(valor):
    if pd.isna(valor):
        return ""
    if isinstance(valor, float):
        if valor.is_integer():
            return str(int(valor)).strip().upper()
        return str(valor).strip().upper()
    s = str(valor).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s.upper()  

def sanear_coordenada_territorial(valor, es_latitud):
    if pd.isna(valor):
        return np.nan
    s_val = str(valor).strip()
    if not s_val:
        return np.nan
    s_filtrado = re.sub(r'[^0-9.,-]', '', s_val).replace(',', '.')
    partes = s_filtrado.split('.')
    if len(partes) > 2:
        s_filtrado = partes[0] + '.' + ''.join(partes[1:])
    if s_filtrado in ['', '-', '.', '-.']:
        return np.nan
    try:
        v = float(s_filtrado)
        if es_latitud:
            v = abs(v)
            while v > 14.0:
                v = v / 10.0
            if 1.0 <= v <= 14.0:
                return round(v, 6)
        else:
            if v > 0:
                v = -v
            while v < -74.0:
                v = v / 10.0
            if -74.0 <= v <= -59.0:
                return round(v, 6)
        return np.nan
    except:
        return np.nan  

def coordenada_en_venezuela(lat, lon):
    try:
        return 1.0 <= float(lat) <= 14.0 and -74.0 <= float(lon) <= -59.0
    except:
        return False  

# =====================================================================
# 4a. GEOCODIFICACIÓN POR CIUDAD
# =====================================================================
@st.cache_data(show_spinner=False)
def geocodificar_ciudad(ciudad, estado):
    geolocator = Nominatim(user_agent="munchy_cendis_optimizer")
    geocode    = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)
    
    intentos = [
        f"{ciudad}, {estado}, Venezuela",
        f"{ciudad}, Venezuela",
        f"{estado}, Venezuela"
    ]
    
    for query in intentos:
        try:
            location = geocode(query)
            if location:
                lat = location.latitude
                lon = location.longitude
                if coordenada_en_venezuela(lat, lon):
                    return round(lat, 6), round(lon, 6)
        except Exception:
            continue
    
    return None, None  

# =====================================================================
# 4. MOTOR DE CARGA MAESTRA
# =====================================================================
@st.cache_data(show_spinner="Procesando matriz transaccional de Munchy...")
def cargar_y_optimizar_data_maestra(archivo_uploaded):
    try:
        lector_excel    = pd.ExcelFile(archivo_uploaded)
        pestañas_reales = lector_excel.sheet_names
        mapa_pestañas   = {
            p.lower().replace('ó','o').replace('é','e').replace('á','a'): p
            for p in pestañas_reales
        }
        
        if 'geolocalizacion' in mapa_pestañas:
            df_cli = pd.read_excel(archivo_uploaded, sheet_name=mapa_pestañas['geolocalizacion'])
        else:
            return None, None, None, False, "❌ No se encontró la pestaña 'Geolocalizacion'.", pd.DataFrame()
        
        if 'ventas' in mapa_pestañas:
            df_ven = pd.read_excel(archivo_uploaded, sheet_name=mapa_pestañas['ventas'])
        else:
            return None, None, None, False, "❌ No se encontró la pestaña 'Ventas'.", pd.DataFrame()
        
        df_fle         = pd.DataFrame()
        tiene_fletes   = False
        claves_excluir = {'geolocalizacion', 'ventas'}
        
        for clave, nombre_real in mapa_pestañas.items():
            if clave in claves_excluir:
                continue
            try:
                df_tmp     = pd.read_excel(archivo_uploaded, sheet_name=nombre_real, header=8)
                cols_lower = [str(c).lower().strip() for c in df_tmp.columns]
                if 'destino' in cols_lower:
                    df_fle       = df_tmp.copy()
                    tiene_fletes = True
                    break
            except Exception:
                continue
        
        lat_series = pd.Series(np.nan, index=df_cli.index)
        lon_series = pd.Series(np.nan, index=df_cli.index)
        
        for col in df_cli.columns:
            col_limpia = re.sub(r'\.\d+$', '', str(col).lower().strip()).strip()
            if col_limpia not in ['latitud', 'longitud']:
                continue
            
            muestra = pd.to_numeric(df_cli[col], errors='coerce').dropna()
            if muestra.empty:
                continue
            
            es_latitud_vzla  = muestra.abs().between(1.0, 14.0).mean() > 0.5
            es_longitud_vzla = muestra.between(-74.0, -59.0).mean() > 0.5
            
            if es_latitud_vzla:
                cleaned    = df_cli[col].apply(lambda x: sanear_coordenada_territorial(x, es_latitud=True))
                lat_series = lat_series.combine_first(cleaned)
            elif es_longitud_vzla:
                cleaned    = df_cli[col].apply(lambda x: sanear_coordenada_territorial(x, es_latitud=False))
                lon_series = lon_series.combine_first(cleaned)
        
        df_cli_nuevo = pd.DataFrame(index=df_cli.index)
        
        for col in df_cli.columns:
            col_limpia = re.sub(r'\.\d+$', '', str(col).lower().strip()).strip()
            if col_limpia in ['id. cliente','codigo del cliente','codigo'] and 'Id. Cliente' not in df_cli_nuevo.columns:
                df_cli_nuevo['Id. Cliente'] = df_cli[col].apply(normalizar_identificador_cliente)
            elif col_limpia in ['nombre de cliente','nombre'] and 'Nombre de Cliente' not in df_cli_nuevo.columns:
                df_cli_nuevo['Nombre de Cliente'] = df_cli[col].astype(str).str.strip().str.title()
            elif col_limpia == 'ciudad' and 'Ciudad' not in df_cli_nuevo.columns:
                df_cli_nuevo['Ciudad'] = df_cli[col].astype(str).str.strip().str.title()
            elif col_limpia == 'estado' and 'Estado' not in df_cli_nuevo.columns:
                df_cli_nuevo['Estado'] = df_cli[col].astype(str).str.strip().str.title()
        
        df_cli_nuevo['Latitud']  = lat_series
        df_cli_nuevo['Longitud'] = lon_series
        
        df_cli_nuevo = (df_cli_nuevo
                        .dropna(subset=['Id. Cliente'])
                        .drop_duplicates(subset=['Id. Cliente'])
                        .reset_index(drop=True))
        
        df_ven_nuevo     = pd.DataFrame(index=df_ven.index)
        col_peso_ok      = False
        col_monetario_ok = False
        
        for col in df_ven.columns:
            col_limpia = re.sub(r'\.\d+$', '', str(col).lower().strip()).strip()
            if col_limpia in ['id. cliente','codigo del cliente','codigo'] and 'Id. Cliente' not in df_ven_nuevo.columns:
                df_ven_nuevo['Id. Cliente'] = df_ven[col].apply(normalizar_identificador_cliente)
            elif any(x in col_limpia for x in ['peso total fact','peso_kg','peso']) and 'Peso_KG' not in df_ven_nuevo.columns:
                s = (df_ven[col].astype(str).str.replace(' ','',regex=False).str.replace(',','.',regex=False)
                     if df_ven[col].dtype == object else df_ven[col])
                df_ven_nuevo['Peso_KG'] = pd.to_numeric(s, errors='coerce').fillna(0.0)
                col_peso_ok = True
            elif any(x in col_limpia for x in ['valos monetario','valor monetario','monto','valor']) and 'Valor_USD' not in df_ven_nuevo.columns:
                s = (df_ven[col].astype(str).str.replace(' ','',regex=False).str.replace(',','.',regex=False)
                     if df_ven[col].dtype == object else df_ven[col])
                df_ven_nuevo['Valor_USD'] = pd.to_numeric(s, errors='coerce').fillna(0.0)
                col_monetario_ok = True
            elif any(x in col_limpia for x in ['fecha']) and 'Fecha del Documento' not in df_ven_nuevo.columns:
                df_ven_nuevo['Fecha del Documento'] = pd.to_datetime(df_ven[col], errors='coerce')
            elif any(x in col_limpia for x in ['cantidad x unidad']) and 'Cantidad_x_Unidad' not in df_ven_nuevo.columns:
                df_ven_nuevo['Cantidad_x_Unidad'] = pd.to_numeric(df_ven[col], errors='coerce').fillna(0.0)
            elif any(x in col_limpia for x in ['conversion', 'bul/caja', 'bulto', 'caja']) and 'Conversion_Bul_Caja' not in df_ven_nuevo.columns:
                df_ven_nuevo['Conversion_Bul_Caja'] = pd.to_numeric(df_ven[col], errors='coerce').fillna(1.0)
        
        if not col_peso_ok or 'Id. Cliente' not in df_ven_nuevo.columns:
            return None, None, None, False, "❌ Error: Comprueba los campos...",pd.DataFrame()
        
        if not col_monetario_ok:
            df_ven_nuevo['Valor_USD'] = 0.0
        
        if 'Cantidad_x_Unidad' not in df_ven_nuevo.columns:
            df_ven_nuevo['Cantidad_x_Unidad'] = 0.0
        if 'Conversion_Bul_Caja' not in df_ven_nuevo.columns:
            df_ven_nuevo['Conversion_Bul_Caja'] = 1.0  
        
        df_ven_nuevo    = df_ven_nuevo[df_ven_nuevo['Peso_KG'] > 0].copy()
        df_ven_agrupado = df_ven_nuevo.groupby('Id. Cliente', as_index=False).agg(
            Peso_KG             = ('Peso_KG',             'sum'),
            Valor_USD           = ('Valor_USD',           'sum'),
            Cantidad_x_Unidad   = ('Cantidad_x_Unidad',   'sum'),
            Conversion_Bul_Caja = ('Conversion_Bul_Caja', 'first')
        )  
        
        df_fle_limpio = pd.DataFrame()
        if tiene_fletes and not df_fle.empty:
            cols_fle       = df_fle.columns.tolist()
            cols_lower_fle = [str(c).lower().strip() for c in cols_fle]
            idx_destino    = next((i for i, c in enumerate(cols_lower_fle) if 'destino' in c), None)
            idx_gandola    = next((i for i, c in enumerate(cols_lower_fle) if 'gandola' in c), None)
            
            if idx_destino is not None and idx_gandola is not None:
                df_fle_limpio = df_fle[[cols_fle[idx_destino], cols_fle[idx_gandola]]].copy()
                df_fle_limpio.columns = ['Ciudad_Flete', 'Tarifa_Gandola']
                df_fle_limpio = df_fle_limpio.dropna(subset=['Ciudad_Flete'])
                df_fle_limpio['Ciudad_Flete'] = df_fle_limpio['Ciudad_Flete'].astype(str).str.strip().str.title()
                df_fle_limpio = df_fle_limpio[
                    ~df_fle_limpio['Ciudad_Flete'].str.upper().isin(['REGION','REGÍON','REGIÓN',''])
                ].reset_index(drop=True)
                df_fle_limpio['Tarifa_Gandola'] = pd.to_numeric(
                    df_fle_limpio['Tarifa_Gandola'].astype(str).str.replace('[^0-9.]','',regex=True),
                    errors='coerce'
                ).fillna(0.0)
                df_fle_limpio['Costo_Flete_Total'] = df_fle_limpio['Tarifa_Gandola'] + 50.0
                df_fle_limpio = df_fle_limpio[
                    df_fle_limpio['Costo_Flete_Total'] > 50.0
                ].reset_index(drop=True)
        
        return df_cli_nuevo, df_ven_agrupado, df_fle_limpio, tiene_fletes, "¡Data procesada con éxito!", df_ven_nuevo
    
    except Exception as e:
        return None, None, None, False, f"Error interno: {e}", pd.DataFrame()

# =====================================================================
# 6. MOTOR DE PUNTOS DORADOS POR REGIÓN
# =====================================================================
def calcular_puntos_dorados_por_region(
    df_clase_a, col_peso, lista_cendis_existentes, lat_p, lon_p,
    umbral_pct=0.05, radio_kernel=0.45
):
    RADIO_COBERTURA_GRADOS = 1.80
    
    df = df_clase_a.dropna(subset=['Latitud','Longitud']).copy()
    df = df[(df['Latitud'] != 0) & (df['Longitud'] != 0)]
    if df.empty:
        return [], pd.DataFrame()
    
    df[['Region','Subregion']] = df.apply(
        lambda r: pd.Series(clasificar_region(
            r.get('Ciudad',''), r.get('Estado','')
        )), axis=1
    )
    
    total_demanda = df[col_peso].sum()
    if total_demanda == 0:
        return [], pd.DataFrame()
    
    nodos_existentes = [{'lat': lat_p, 'lon': lon_p}]
    for c in lista_cendis_existentes:
        nodos_existentes.append({'lat': c['lat'], 'lon': c['lon']})
    
    def distancia_minima_a_nodos(lat, lon):
        return min(
            np.sqrt((lat - n['lat'])**2 + (lon - n['lon'])**2)
            for n in nodos_existentes
        )
    
    df['dist_nodo_existente'] = df.apply(
        lambda r: distancia_minima_a_nodos(r['Latitud'], r['Longitud']), axis=1
    )
    df['sin_cobertura'] = df['dist_nodo_existente'] > RADIO_COBERTURA_GRADOS
    
    df_sin_cobertura = df[df['sin_cobertura']].copy()
    total_demanda_descubierta = df_sin_cobertura[col_peso].sum()
    if total_demanda_descubierta == 0:
        return [], pd.DataFrame()
    
    demanda_region = df_sin_cobertura.groupby('Region')[col_peso].sum()
    regiones_activas = demanda_region[
        demanda_region / total_demanda_descubierta >= umbral_pct
    ].index.tolist()
    
    puntos_dorados = []
    
    debug_kernel = []
    for region in regiones_activas:
        df_reg = df_sin_cobertura[df_sin_cobertura['Region'] == region].copy()
        if len(df_reg) < 1:
            continue
        
        km = KMeans(n_clusters=1, random_state=42, n_init=10)
        
        if col_peso == 'Conteo':
            coords = df_reg[['Latitud','Longitud']].values
            n      = len(coords)
            
            if n == 1:
                pesos = np.ones(1)
            else:
                pesos = np.zeros(n)
                for i in range(n):
                    for j in range(n):
                        if i == j:
                            continue
                        d2 = ((coords[i,0] - coords[j,0])**2 +
                              (coords[i,1] - coords[j,1])**2)
                        pesos[i] += np.exp(-d2 / (2.0 * radio_kernel**2))
                
                if pesos.sum() < 1e-9:
                    pesos = np.ones(n)
                else:
                    pesos = 1.0 + (pesos - pesos.min()) / (pesos.max() - pesos.min() + 1e-9) * 9.0
            
            debug_kernel.append({
                'Region': region,
                'n':      n,
                'min':    round(float(pesos.min()), 2),
                'max':    round(float(pesos.max()), 2),
                'std':    round(float(pesos.std()), 2),
            })
        else:
            pesos = df_reg[col_peso].values.clip(min=0.001)
        
        km.fit(df_reg[['Latitud','Longitud']].values, sample_weight=pesos)
        lat_d = km.cluster_centers_[0][0]
        lon_d = km.cluster_centers_[0][1]
        
        dist_min = distancia_minima_a_nodos(lat_d, lon_d)
        if dist_min < RADIO_COBERTURA_GRADOS:
            continue
        
        df_reg_total = df[df['Region'] == region]
        
        puntos_dorados.append({
            'Region':           region,
            'Latitud':          round(lat_d, 4),
            'Longitud':         round(lon_d, 4),
            'Clientes_A':       len(df_reg),
            'Clientes_A_Total': len(df_reg_total),
            'Peso_KG':          round(df_reg['Peso_KG'].sum(), 1),
            'Valor_USD':        round(df_reg['Valor_USD'].sum(), 2),
            'Pct_Demanda':      round(demanda_region[region] / total_demanda_descubierta * 100, 1),
            '_debug_kernel':    debug_kernel,
        })
    
    return puntos_dorados, df

# =====================================================================
# 7. ASIGNACIÓN DE CLIENTES A NODOS
# =====================================================================
def asignar_clientes_a_nodos(df_maestro, puntos_dorados, nombre_p, lat_p, lon_p, lista_cendis_existentes):
    df = df_maestro.dropna(subset=['Latitud','Longitud']).copy()
    df = df[(df['Latitud'] != 0) & (df['Longitud'] != 0)]
    
    nodos = [{'nombre': nombre_p, 'lat': lat_p, 'lon': lon_p, 'tipo': '🏭 Planta'}]
    
    for c in lista_cendis_existentes:
        nodos.append({'nombre': c['nombre'], 'lat': c['lat'], 'lon': c['lon'], 'tipo': '🏬 CenDis Existente'})
    
    for pd_nodo in puntos_dorados:
        nodos.append({
            'nombre': f"PD {pd_nodo['Region']}",
            'lat':    pd_nodo['Latitud'],
            'lon':    pd_nodo['Longitud'],
            'tipo':   '⭐ Punto Dorado'
        })
    
    if not nodos:
        return df, []
    
    def nodo_mas_cercano(lat, lon):
        distancias = [
            np.sqrt((lat - n['lat'])**2 + (lon - n['lon'])**2)
            for n in nodos
        ]
        idx = int(np.argmin(distancias))
        return nodos[idx]['nombre'], round(distancias[idx], 4)
    
    df[['Nodo_Asignado', 'Distancia_Nodo']] = df.apply(
        lambda r: pd.Series(nodo_mas_cercano(r['Latitud'], r['Longitud'])),
        axis=1
    )
    
    return df, nodos  

# =====================================================================
# 8. TABLA DE COBERTURA POR NODO
# =====================================================================
def mostrar_tabla_cobertura(df_asignado, nodos):
    st.markdown("### Cobertura de Clientes por Nodo Logístico")
    st.caption("Cada cliente fue asignado al nodo más cercano por distancia euclidiana.")

    resumen_nodos = []
    total_clientes = 0
    total_vol      = 0.0

    for nodo in nodos:
        df_n = df_asignado[df_asignado['Nodo_Asignado'] == nodo['nombre']]
        if df_n.empty:
            continue
        vol  = round(df_n['Peso_KG'].sum(), 1)
        val  = round(df_n['Valor_USD'].sum(), 2)
        flt  = round(df_n['Costo_Flete_Total'].sum(), 2) if 'Costo_Flete_Total' in df_n.columns else 0.0
        total_clientes += len(df_n)
        total_vol      += vol
        resumen_nodos.append({
            'Nodo':               nodo['nombre'],
            'Tipo':               nodo['tipo'],
            'Latitud':            nodo['lat'],
            'Longitud':           nodo['lon'],
            'Clientes Asignados': len(df_n),
            'Volumen Total (Kg)': fmt_num(vol, 1),
            'Valor Total (USD)':  fmt_num(val, 2),
            'Flete Acum. (USD)':  fmt_num(flt, 2),
        })

    if not resumen_nodos:
        st.warning("No se pudo generar la tabla de cobertura.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🏭Total Nodos Activos",  f"{len(resumen_nodos)}")
    with col2:
        st.metric("👥Clientes Cubiertos",    f"{total_clientes}")
    with col3:
        st.metric("📨Volumen Cubierto (Kg)", fmt_num(total_vol, 1))

    st.markdown("#### 📋 Detalle por Nodo")
    st.dataframe(
        pd.DataFrame(resumen_nodos)[[
            'Nodo', 'Tipo', 'Latitud', 'Longitud',
            'Clientes Asignados', 'Volumen Total (Kg)',
            'Valor Total (USD)', 'Flete Acum. (USD)'
        ]],
        use_container_width=True, hide_index=True
    )

    st.markdown("#### Clientes por Nodo (detalle)")
    for nodo in nodos:
        df_n = df_asignado[df_asignado['Nodo_Asignado'] == nodo['nombre']]
        if df_n.empty:
            continue
        with st.expander(f"{nodo['nombre']} — {len(df_n)} clientes | {fmt_num(df_n['Peso_KG'].sum(), 1)} Kg | ${fmt_num(df_n['Valor_USD'].sum(), 2)}"):
            cols_det = [c for c in ['Id. Cliente','Nombre de Cliente','Ciudad','Estado',
                        'Peso_KG','Valor_USD','Costo_Flete_Total','Distancia_Nodo']
                        if c in df_n.columns]
            df_det = df_n[cols_det].copy()
            if 'Peso_KG'           in df_det.columns: df_det['Peso_KG']           = df_det['Peso_KG'].apply(lambda x: fmt_num(x, 1))
            if 'Valor_USD'         in df_det.columns: df_det['Valor_USD']         = df_det['Valor_USD'].apply(lambda x: fmt_num(x, 2))
            if 'Costo_Flete_Total' in df_det.columns: df_det['Costo_Flete_Total'] = df_det['Costo_Flete_Total'].apply(lambda x: fmt_num(x, 2))
            if 'Distancia_Nodo'    in df_det.columns: df_det['Distancia_Nodo']    = df_det['Distancia_Nodo'].apply(lambda x: fmt_num(x, 4))
            df_det = df_det.rename(columns={
                'Peso_KG':           'Volumen (Kg)',
                'Valor_USD':         'Valor (USD)',
                'Costo_Flete_Total': 'Flete Gandola (USD)',
                'Distancia_Nodo':    'Distancia (°)'
            }).reset_index(drop=True)
            df_det.index += 1
            st.dataframe(df_det, use_container_width=True)

# =====================================================================
# 9. RENDERIZADO CARTOGRÁFICO
# =====================================================================
def calcular_red_puntos_dorados(
    df_clase_a_vol, df_clase_a_val, df_clase_a_conc,
    df_maestro_completo,
    nombre_p, lat_p, lon_p,
    lista_cendis_existentes,
    radio_kernel=0.45
):
    st.markdown("### Ubicación de Red Óptima Proyectada por Región")
    st.caption("Selecciona una modalidad para visualizar las zonas recomendadas y determinar la ubicación óptima del nuevo CenDis.")
    
    # ── BOTONES DE CONTROL ─────────────────────────────────────────
    col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
    with col_b1:
        btn_vol  = st.button("🔴 Clase A Volumen (Kg)",    use_container_width=True)
    with col_b2:
        btn_val  = st.button("🔵 Clase A Valor Monetario", use_container_width=True)
    with col_b3:
        btn_conc = st.button("🟡 Concentración Clientes",  use_container_width=True)
    with col_b4:
        btn_amb  = st.button("🟠 Ver Ambos (Vol + Val)",   use_container_width=True)
    with col_b5:
        btn_rst  = st.button("🟢 Ver Todos",               use_container_width=True)
    
    if btn_vol:
        st.session_state['vista_mapa'] = 'volumen'
    elif btn_val:
        st.session_state['vista_mapa'] = 'valor'
    elif btn_conc:
        st.session_state['vista_mapa'] = 'concentracion'
    elif btn_amb:
        st.session_state['vista_mapa'] = 'ambos'
    elif btn_rst:
        if 'vista_mapa' in st.session_state:
            del st.session_state['vista_mapa']
    
    vista_activa = 'vista_mapa' in st.session_state
    vista        = st.session_state.get('vista_mapa', None)
    
    # ── CALCULAR PUNTOS DORADOS ────────────────────────────────────
    puntos_vol,  _ = calcular_puntos_dorados_por_region(
        df_clase_a_vol,  'Peso_KG',   lista_cendis_existentes, lat_p, lon_p
    )
    puntos_val,  _ = calcular_puntos_dorados_por_region(
        df_clase_a_val,  'Valor_USD', lista_cendis_existentes, lat_p, lon_p
    )
    puntos_conc, _ = calcular_puntos_dorados_por_region(
        df_clase_a_conc, 'Conteo',    lista_cendis_existentes, lat_p, lon_p,
        radio_kernel=radio_kernel
    )
    
    if not puntos_vol and not puntos_val and not puntos_conc:
        st.error("❌ No se pudieron calcular puntos dorados...")
        return None, None, None

    # ── INICIALIZAR MAPA ───────────────────────────────────────────
    lat_centro  = df_maestro_completo['Latitud'].dropna().mean()
    lon_centro  = df_maestro_completo['Longitud'].dropna().mean()
    mapa_munchy = folium.Map(
        location=[lat_centro, lon_centro],
        zoom_start=7, tiles="CartoDB positron"
    )
    
    # ── PREPARAR CLASIFICACIÓN DE CLIENTES ────────────────────────
    ids_vol  = set(df_clase_a_vol['Id. Cliente'])
    ids_val  = set(df_clase_a_val['Id. Cliente'])
    ids_conc = set(df_clase_a_conc['Id. Cliente'])
    
    df_todos = df_maestro_completo.dropna(subset=['Latitud','Longitud']).copy()
    df_todos = df_todos[(df_todos['Latitud'] != 0) & (df_todos['Longitud'] != 0)]
    df_todos['es_vol']  = df_todos['Id. Cliente'].isin(ids_vol)
    df_todos['es_val']  = df_todos['Id. Cliente'].isin(ids_val)
    df_todos['es_conc'] = df_todos['Id. Cliente'].isin(ids_conc)

    # ── MENSAJE INFORMATIVO ────────────────────────────────────────
    if not vista_activa:
        st.info("🟢 Mostrando infraestructura actual (Planta + CenDis) — presiona un botón para ver análisis")
    elif vista == 'volumen':
        st.info("🔴 Clase A por **Volumen (Kg)** — generan el 80% del volumen")
    elif vista == 'valor':
        st.info("🔵 Clase A por **Valor Monetario** — generan el 80% de la facturación")
    elif vista == 'concentracion':
        st.info("🟡 **Concentración de Clientes** — gravita hacia donde hay más clientes")
    else:
        st.info("🔴 Clase A Volumen  |  🔵 Clase A Valor (cian)  |  🟠 En ambas listas")

    # ══════════════════════════════════════════════════════════════
    # 1️⃣ PRIMERO: CÍRCULOS DE COBERTURA (para que queden atrás)
    # ══════════════════════════════════════════════════════════════
    RADIO_METROS = 200_000
    
    # ── Círculo de Planta ─────────────────────────────────────────
    folium.Circle(
        location=[lat_p, lon_p], radius=RADIO_METROS,
        color='#1A6EBD', weight=2, dash_array='6 4',
        fill=True, fill_color='#1A6EBD', fill_opacity=0.07
    ).add_to(mapa_munchy)
    
    # ── Círculos de CenDis Existentes ─────────────────────────────
    for cendi in lista_cendis_existentes:
        folium.Circle(
            location=[cendi['lat'], cendi['lon']], radius=RADIO_METROS,
            color='#E87722', weight=2, dash_array='6 4',
            fill=True, fill_color='#E87722', fill_opacity=0.07
        ).add_to(mapa_munchy)
    
    # ── Círculos de Puntos Dorados VOLUMEN ────────────────────────
    if vista in ['volumen', 'ambos']:  # ← Sin None, solo aparecen en vistas específicas
        for pd_nodo in puntos_vol:
            folium.Circle(
                location=[pd_nodo['Latitud'], pd_nodo['Longitud']], radius=RADIO_METROS,
                color='#E60F29', weight=2, dash_array='6 4',
                fill=True, fill_color='#E60F29', fill_opacity=0.07
            ).add_to(mapa_munchy)
    
    # ── Círculos de Puntos Dorados VALOR ──────────────────────────
    if vista in ['valor', 'ambos']:
        for pd_nodo in puntos_val:
            folium.Circle(
                location=[pd_nodo['Latitud'], pd_nodo['Longitud']], radius=RADIO_METROS,
                color='#00008B', weight=2, dash_array='6 4',
                fill=True, fill_color='#00008B', fill_opacity=0.07
            ).add_to(mapa_munchy)
    
    # ── Círculos de Puntos Dorados CONCENTRACIÓN ──────────────────
    if vista == 'concentracion':
        for pd_nodo in puntos_conc:
            folium.Circle(
                location=[pd_nodo['Latitud'], pd_nodo['Longitud']], radius=RADIO_METROS,
                color='#FFD700', weight=2, dash_array='6 4',
                fill=True, fill_color='#FFD700', fill_opacity=0.09
            ).add_to(mapa_munchy)

    # ══════════════════════════════════════════════════════════════
    # 2️⃣ SEGUNDO: PUNTOS DE CLIENTES (quedan por encima)
    # ══════════════════════════════════════════════════════════════
    for _, row in df_todos.iterrows():
        es_vol  = row['es_vol']
        es_val  = row['es_val']
        es_conc = row['es_conc']
        
        if not vista_activa:
            color = '#4CAF50'; radio = 5; opac = 0.8
        else:
            es_relevante = (
                (vista == 'volumen'       and es_vol)  or
                (vista == 'valor'         and es_val)  or
                (vista == 'concentracion' and es_conc) or
                (vista == 'ambos'         and (es_vol or es_val))
            )
            if not es_relevante:
                continue
            
            if vista == 'concentracion':
                color = '#FFD700'; radio = 6; opac = 1.0
            elif vista == 'ambos' and es_vol and es_val:
                color = '#FF6B00'; radio = 7; opac = 1.0
            elif vista == 'ambos' and es_vol:
                color = '#E60F29'; radio = 6; opac = 1.0
            elif vista == 'ambos' and es_val:
                color = '#00E5FF'; radio = 6; opac = 1.0
            elif vista == 'volumen':
                color = '#E60F29'; radio = 6; opac = 1.0
            elif vista == 'valor':
                color = '#00E5FF'; radio = 6; opac = 1.0
            else:
                color = '#E60F29'; radio = 6; opac = 1.0
        
        flete_val_txt = row.get('Costo_Flete_Total', 0.0)
        flete_txt     = f"${flete_val_txt:,.2f}" if flete_val_txt > 0 else "Sin tarifa registrada"
        
        etiquetas = []
        if es_vol:  etiquetas.append("🔴 Clase A Volumen")
        if es_val:  etiquetas.append("🔵 Clase A Valor")
        if es_conc: etiquetas.append("🟡 Alta Concentración")
        if not etiquetas: etiquetas.append("⚪ Cliente Regular")
        
        folium.CircleMarker(
            location=[row['Latitud'], row['Longitud']],
            radius=radio,
            popup=(
                f"<b>🏢 {row['Nombre de Cliente']}</b><br>"
                f"{' | '.join(etiquetas)}<br>"
                f"Masa: {row['Peso_KG']:,.1f} Kg<br>"
                f"Valor: ${row['Valor_USD']:,.2f}<br>"
            ),
            tooltip=row['Nombre de Cliente'],
            color="#1E4620", fill=True, fill_color=color, fill_opacity=opac
        ).add_to(mapa_munchy)
        
    # ══════════════════════════════════════════════════════════════
    # 3️⃣ TERCERO: MARCADORES DE INFRAESTRUCTURA (quedan arriba)
    # ══════════════════════════════════════════════════════════════
    
    # ── Marcador de Planta ────────────────────────────────────────
    folium.Marker(
        location=[lat_p, lon_p], popup=f"<b>{nombre_p}</b>",
        icon=folium.Icon(color="blue", icon="industry", prefix="fa")
    ).add_to(mapa_munchy)
    
    # ── Marcadores de CenDis ──────────────────────────────────────
    for cendi in lista_cendis_existentes:
        folium.Marker(
            location=[cendi['lat'], cendi['lon']], popup=f"<b>{cendi['nombre']}</b>",
            icon=folium.Icon(color="orange", icon="box", prefix="fa")
        ).add_to(mapa_munchy)

    # ══════════════════════════════════════════════════════════════
    # 4️⃣ CUARTO: MARCADORES DE PUNTOS DORADOS (siempre visibles)
    # ══════════════════════════════════════════════════════════════
    
    # ── Marcadores de Puntos Dorados VOLUMEN ──────────────────────
    resumen_vol = []
    if vista in ['volumen', 'ambos']:  # ← Sin None
        for pd_nodo in puntos_vol:
            folium.Marker(
                location=[pd_nodo['Latitud'], pd_nodo['Longitud']],
                popup=(
                    f"<b>🔴 Punto Dorado Volumen</b><br>"
                    f"Región: {pd_nodo['Region']}<br>"
                    f"Lat: {pd_nodo['Latitud']} | Lon: {pd_nodo['Longitud']}<br>"
                    f"Clientes sin cobertura: {pd_nodo['Clientes_A']}<br>"
                    f"Volumen zona: {pd_nodo['Peso_KG']:,.1f} Kg<br>"
                    f"Valor zona: ${pd_nodo['Valor_USD']:,.2f}<br>"
                    f"% Demanda descubierta: {pd_nodo['Pct_Demanda']}%"
                ),
                tooltip=f"🔴 PD Volumen — {pd_nodo['Region']}",
                icon=folium.Icon(color="red", icon="star")
            ).add_to(mapa_munchy)
            
            resumen_vol.append({
                "Región":                     pd_nodo['Region'],
                "Latitud":                    pd_nodo['Latitud'],
                "Longitud":                   pd_nodo['Longitud'],
                "Clientes Sin Cobertura":     pd_nodo['Clientes_A'],
                "Total Clientes A Región":    pd_nodo['Clientes_A_Total'],
                "Volumen Sin Cobertura (Kg)": pd_nodo['Peso_KG'],
                "Valor Sin Cobertura (USD)":  pd_nodo['Valor_USD'],
                "% Demanda Descubierta":      pd_nodo['Pct_Demanda'],
            })
    
    # ── Marcadores de Puntos Dorados VALOR ────────────────────────
    resumen_val = []
    if vista in ['valor', 'ambos']:
        for pd_nodo in puntos_val:
            folium.Marker(
                location=[pd_nodo['Latitud'], pd_nodo['Longitud']],
                popup=(
                    f"<b>🔵 Punto Dorado Valor</b><br>"
                    f"Región: {pd_nodo['Region']}<br>"
                    f"Lat: {pd_nodo['Latitud']} | Lon: {pd_nodo['Longitud']}<br>"
                    f"Clientes sin cobertura: {pd_nodo['Clientes_A']}<br>"
                    f"Volumen zona: {pd_nodo['Peso_KG']:,.1f} Kg<br>"
                    f"Valor zona: ${pd_nodo['Valor_USD']:,.2f}<br>"
                    f"% Demanda descubierta: {pd_nodo['Pct_Demanda']}%"
                ),
                tooltip=f"🔵 PD Valor — {pd_nodo['Region']}",
                icon=folium.Icon(color="darkblue", icon="star")
            ).add_to(mapa_munchy)
            
            resumen_val.append({
                "Región":                     pd_nodo['Region'],
                "Latitud":                    pd_nodo['Latitud'],
                "Longitud":                   pd_nodo['Longitud'],
                "Clientes Sin Cobertura":     pd_nodo['Clientes_A'],
                "Volumen Zona (Kg)":          pd_nodo['Peso_KG'],
                "Valor Zona (USD)":           pd_nodo['Valor_USD'],
                "% Demanda Descubierta":      pd_nodo['Pct_Demanda'],
            })
    
    # ── Marcadores de Puntos Dorados CONCENTRACIÓN ────────────────
    resumen_conc = []
    if vista == 'concentracion':
        for pd_nodo in puntos_conc:
            folium.Marker(
                location=[pd_nodo['Latitud'], pd_nodo['Longitud']],
                popup=(
                    f"<b>🟡 Punto Dorado Concentración</b><br>"
                    f"Región: {pd_nodo['Region']}<br>"
                    f"Lat: {pd_nodo['Latitud']} | Lon: {pd_nodo['Longitud']}<br>"
                    f"Clientes sin cobertura: {pd_nodo['Clientes_A']}<br>"
                    f"Total clientes región: {pd_nodo['Clientes_A_Total']}<br>"
                    f"Volumen zona: {pd_nodo['Peso_KG']:,.1f} Kg<br>"
                    f"Valor zona: ${pd_nodo['Valor_USD']:,.2f}<br>"
                    f"% Clientes descubiertos: {pd_nodo['Pct_Demanda']}%"
                ),
                tooltip=f"🟡 PD Concentración — {pd_nodo['Region']}",
                icon=folium.Icon(color="orange", icon="users", prefix="fa")
            ).add_to(mapa_munchy)
            
            resumen_conc.append({
                "Región":                  pd_nodo['Region'],
                "Latitud":                 pd_nodo['Latitud'],
                "Longitud":                pd_nodo['Longitud'],
                "Clientes Sin Cobertura":  pd_nodo['Clientes_A'],
                "Total Clientes Región":   pd_nodo['Clientes_A_Total'],
                "% Clientes Descubiertos": pd_nodo['Pct_Demanda'],
                "Volumen Zona (Kg)":       pd_nodo['Peso_KG'],
                "Valor Zona (USD)":        pd_nodo['Valor_USD'],
            })

    # ── RENDERIZAR MAPA ────────────────────────────────────────────
    st_folium(mapa_munchy, use_container_width=True, height=500)
    
    # ── TABLAS DE RESUMEN ──────────────────────────────────────────
    if resumen_vol:
        st.markdown("#### 🔴 Puntos Dorados — Volumen (Kg)")
        df_rv = pd.DataFrame(resumen_vol).copy()
        if 'Volumen Sin Cobertura (Kg)' in df_rv.columns:
            df_rv['Volumen Sin Cobertura (Kg)'] = df_rv['Volumen Sin Cobertura (Kg)'].apply(lambda x: fmt_num(x, 1))
        if 'Valor Sin Cobertura (USD)' in df_rv.columns:
            df_rv['Valor Sin Cobertura (USD)']  = df_rv['Valor Sin Cobertura (USD)'].apply(lambda x: fmt_num(x, 2))
        st.dataframe(df_rv, use_container_width=True, hide_index=True)

    if resumen_val:
        st.markdown("#### 🔵 Puntos Dorados — Valor Monetario")
        df_rval = pd.DataFrame(resumen_val).copy()
        if 'Volumen Zona (Kg)' in df_rval.columns:
            df_rval['Volumen Zona (Kg)'] = df_rval['Volumen Zona (Kg)'].apply(lambda x: fmt_num(x, 1))
        if 'Valor Zona (USD)' in df_rval.columns:
            df_rval['Valor Zona (USD)']  = df_rval['Valor Zona (USD)'].apply(lambda x: fmt_num(x, 2))
        st.dataframe(df_rval, use_container_width=True, hide_index=True)

    if resumen_conc:
        st.markdown("#### 🟡 Puntos Dorados — Concentración de Clientes")
        df_rc = pd.DataFrame(resumen_conc).copy()
        if 'Volumen Zona (Kg)' in df_rc.columns:
            df_rc['Volumen Zona (Kg)'] = df_rc['Volumen Zona (Kg)'].apply(lambda x: fmt_num(x, 1))
        if 'Valor Zona (USD)' in df_rc.columns:
            df_rc['Valor Zona (USD)']  = df_rc['Valor Zona (USD)'].apply(lambda x: fmt_num(x, 2))
        st.dataframe(df_rc, use_container_width=True, hide_index=True)
    
    return puntos_vol, puntos_val, puntos_conc

# =====================================================================
# 10. HELPER DE EXPORTACIÓN
# =====================================================================
def convertir_df_a_excel(df):
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=True, sheet_name='Clase_A')
    buffer.seek(0)
    return buffer.read()

def check_password():
    if st.session_state.get("autenticado"):
        return True
    
    st.markdown("## 🔐 Acceso Restringido — Munchy")
    usuario = st.text_input("Usuario:", key="login_user")
    clave   = st.text_input("Contraseña:", type="password", key="login_pass")
    
    USUARIOS = {
        "logistica":  "munchy_log_2026",
        "gerencia":   "munchy_ger_2026",
        "admin":      "munchy_admin_2026",
    }
    
    if st.button("Entrar"):
        if USUARIOS.get(usuario) == clave:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos")
    
    return False

if not check_password():
    st.stop()
# =====================================================================
# 11. ORQUESTADOR PRINCIPAL
# =====================================================================
# =====================================================================
# 11. ORQUESTADOR PRINCIPAL
# =====================================================================
def main():
    st.title(" Gemelo Digital Logístico - Munchy")
    st.markdown("Análisis Geográfico de Clientes y Financiero para Nuevos Cendis")
    modalidad, nombre_p, lat_p, lon_p, lista_cendis_existentes, radio_kernel = \
        modulo_controles_simulacion()
    tab_geo, tab_fin = st.tabs([
        "🗺️ Análisis Geográfico",
        "💰 Análisis Financiero"
    ])

    # ================================================================
    with tab_geo:
        st.subheader("Carga de Data Maestra Unificada")
        archivo_unico = st.file_uploader(
            "Sube el archivo maestro de Excel (.xlsx)",
            type=['xlsx'],
            key="uploader_maestro"
        )
        if archivo_unico:
            st.session_state['archivo_maestro'] = archivo_unico
            resultado = cargar_y_optimizar_data_maestra(archivo_unico)
            if resultado[0] is not None:
                df_cli, df_ven, df_fle_limpio, tiene_fletes, _, df_ventas_raw = resultado
                st.session_state['df_ventas_raw'] = df_ventas_raw
                df_maestro = pd.merge(df_ven, df_cli, on='Id. Cliente', how='left')
                df_maestro['Nombre de Cliente'] = df_maestro['Nombre de Cliente'].fillna(
                    df_maestro['Id. Cliente'].astype(str)
                )
                if tiene_fletes and not df_fle_limpio.empty:
                    df_maestro['Ciudad_upper']    = df_maestro['Ciudad'].str.upper().str.strip()
                    df_fle_limpio['Ciudad_upper'] = df_fle_limpio['Ciudad_Flete'].str.upper().str.strip()
                    df_maestro = pd.merge(
                        df_maestro,
                        df_fle_limpio[['Ciudad_upper', 'Costo_Flete_Total']],
                        on='Ciudad_upper', how='left'
                    ).drop(columns=['Ciudad_upper'])
                    df_maestro['Costo_Flete_Total'] = df_maestro['Costo_Flete_Total'].fillna(0.0)
                else:
                    df_maestro['Costo_Flete_Total'] = 0.0

                df_maestro = df_maestro.sort_values('Peso_KG', ascending=False).reset_index(drop=True)
                total_vol  = df_maestro['Peso_KG'].sum()
                total_val  = df_maestro['Valor_USD'].sum()
                df_maestro['Vol_Acum']     = df_maestro['Peso_KG'].cumsum()
                df_maestro['Pct_Acum_Vol'] = (df_maestro['Vol_Acum'] / total_vol * 100) if total_vol > 0 else 0
                df_maestro['Clasificacion_ABC_Vol'] = pd.cut(
                    df_maestro['Pct_Acum_Vol'],
                    bins=[0, 80.0, 95.0, 100.0],
                    labels=['A', 'B', 'C'],
                    include_lowest=True
                )
                df_maestro = df_maestro.sort_values('Valor_USD', ascending=False).reset_index(drop=True)
                df_maestro['Val_Acum']     = df_maestro['Valor_USD'].cumsum()
                df_maestro['Pct_Acum_Val'] = (df_maestro['Val_Acum'] / total_val * 100) if total_val > 0 else 0
                df_maestro['Clasificacion_ABC_Val'] = pd.cut(
                    df_maestro['Pct_Acum_Val'],
                    bins=[0, 80.0, 95.0, 100.0],
                    labels=['A', 'B', 'C'],
                    include_lowest=True
                )
                df_maestro['Conteo']   = 1.0
                df_clientes_a_conc     = df_maestro.copy()
                df_clientes_a_vol = df_maestro[df_maestro['Clasificacion_ABC_Vol'] == 'A'].copy()
                df_clientes_a_val = df_maestro[df_maestro['Clasificacion_ABC_Val'] == 'A'].copy()
                vol_a    = df_clientes_a_vol['Peso_KG'].sum()
                val_a    = df_clientes_a_val['Valor_USD'].sum()
                en_ambos = len(set(df_clientes_a_vol['Id. Cliente']) &
                               set(df_clientes_a_val['Id. Cliente']))

                st.markdown("---")
                st.subheader("Resultados de la Simulación Geográfica")
                st.markdown("##### Totales Globales")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("⚖️ Demanda Total",        f"{fmt_num(total_vol, 1)} Kg")
                with col2:
                    st.metric("💵 Valor Total Facturado", f"${fmt_num(total_val, 2)}")
                with col3:
                    st.metric("👥 Clientes Totales",      f"{len(df_maestro)}")

                st.markdown("##### Clientes Clase A")
                col4, col5, col6 = st.columns(3)
                with col4:
                    st.metric("🔴 Clase A Volumen", f"{len(df_clientes_a_vol)} clientes",
                              delta=f"{fmt_num(vol_a, 1)} Kg")
                with col5:
                    st.metric("🔵 Clase A Valor",   f"{len(df_clientes_a_val)} clientes",
                              delta=f"${fmt_num(val_a, 2)}")
                with col6:
                    st.metric("🟠 En Ambas Listas", f"{en_ambos} clientes")

                st.markdown("---")
                resultado_mapa = calcular_red_puntos_dorados(
                    df_clientes_a_vol, df_clientes_a_val, df_clientes_a_conc,
                    df_maestro,
                    nombre_p, lat_p, lon_p,
                    lista_cendis_existentes,
                    radio_kernel=radio_kernel
                )
                puntos_vol  = resultado_mapa[0] if resultado_mapa[0] is not None else []
                puntos_val  = resultado_mapa[1] if resultado_mapa[1] is not None else []
                puntos_conc = resultado_mapa[2] if resultado_mapa[2] is not None else []

                st.markdown("---")
                vista_actual = st.session_state.get('vista_mapa', None)
                if vista_actual == 'valor':
                    puntos_activos = puntos_val
                elif vista_actual == 'concentracion':
                    puntos_activos = puntos_conc
                else:
                    puntos_activos = puntos_vol

                df_asignado, nodos = asignar_clientes_a_nodos(
                    df_maestro, puntos_activos,
                    nombre_p, lat_p, lon_p,
                    lista_cendis_existentes
                )
                mostrar_tabla_cobertura(df_asignado, nodos)

                st.markdown("---")
                st.subheader("Clientes que Conforman el 80% de la Demanda")

                if vista_actual is None:
                    st.info("💡 Presiona un botón del mapa para ver la lista de clientes.")

                elif vista_actual == 'volumen':
                    st.markdown("#### 🔴 Clientes Clase A — Volumen (Kg)")
                    cols_v = [c for c in ['Id. Cliente','Nombre de Cliente','Ciudad','Estado',
                                          'Peso_KG','Valor_USD']
                              if c in df_clientes_a_vol.columns]
                    df_dv = df_clientes_a_vol[cols_v].copy().rename(columns={
                        'Peso_KG':'Volumen (Kg)', 'Valor_USD':'Valor (USD)'
                    }).sort_values('Volumen (Kg)', ascending=False).reset_index(drop=True)
                    df_dv.index += 1

                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1: st.metric("👥 Total Clientes", f"{len(df_dv)}")
                    with col_r2: st.metric("⚖️ Volumen Total",  f"{fmt_num(df_dv['Volumen (Kg)'].sum(), 1)} Kg")
                    with col_r3: st.metric("💵 Valor Total",    f"${fmt_num(df_dv['Valor (USD)'].sum(), 2)}")

                    top_sel = st.radio("Mostrar:", options=[5, 20, 50, 100, len(df_dv)],
                        format_func=lambda x: f"Top {x}" if x != len(df_dv) else "Ver Todos",
                        horizontal=True, key="top_vol")

                    # Aplicar formato latino a columnas numéricas antes de mostrar
                    df_dv_display = df_dv.head(top_sel).copy()
                    df_dv_display['Volumen (Kg)'] = df_dv_display['Volumen (Kg)'].apply(lambda x: fmt_num(x, 1))
                    df_dv_display['Valor (USD)']  = df_dv_display['Valor (USD)'].apply(lambda x: fmt_num(x, 2))
                    st.dataframe(df_dv_display, use_container_width=True)

                    st.download_button("📥 Descargar (.xlsx)", data=convertir_df_a_excel(df_dv),
                        file_name="clase_a_volumen.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

                elif vista_actual == 'valor':
                    st.markdown("#### 🔵 Clientes Clase A — Valor Monetario (USD)")
                    cols_u = [c for c in ['Id. Cliente','Nombre de Cliente','Ciudad','Estado',
                                          'Peso_KG','Valor_USD','Costo_Flete_Total']
                              if c in df_clientes_a_val.columns]
                    df_du = df_clientes_a_val[cols_u].copy().rename(columns={
                        'Peso_KG':'Volumen (Kg)', 'Valor_USD':'Valor (USD)',
                        'Costo_Flete_Total':'Flete Gandola (USD)'
                    }).sort_values('Valor (USD)', ascending=False).reset_index(drop=True)
                    df_du.index += 1

                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1: st.metric("👥 Total Clientes", f"{len(df_du)}")
                    with col_r2: st.metric("⚖️ Volumen Total",  f"{fmt_num(df_du['Volumen (Kg)'].sum(), 1)} Kg")
                    with col_r3: st.metric("💵 Valor Total",    f"${fmt_num(df_du['Valor (USD)'].sum(), 2)}")

                    top_sel = st.radio("Mostrar:", options=[5, 20, 50, 100, len(df_du)],
                        format_func=lambda x: f"Top {x}" if x != len(df_du) else "Ver Todos",
                        horizontal=True, key="top_val")

                    # Aplicar formato latino a columnas numéricas antes de mostrar
                    df_du_display = df_du.head(top_sel).copy()
                    df_du_display['Volumen (Kg)'] = df_du_display['Volumen (Kg)'].apply(lambda x: fmt_num(x, 1))
                    df_du_display['Valor (USD)']  = df_du_display['Valor (USD)'].apply(lambda x: fmt_num(x, 2))
                    if 'Flete Gandola (USD)' in df_du_display.columns:
                        df_du_display['Flete Gandola (USD)'] = df_du_display['Flete Gandola (USD)'].apply(lambda x: fmt_num(x, 2))
                    st.dataframe(df_du_display, use_container_width=True)

                    # ✅ CORREGIDO: era "concentracion_clientes.xlsx"
                    st.download_button("📥 Descargar (.xlsx)", data=convertir_df_a_excel(df_du),
                        file_name="clase_a_valor.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

                elif vista_actual == 'concentracion':
                    st.markdown("#### 🟡 Clientes — Concentración Geográfica")
                    cols_c = [c for c in ['Id. Cliente','Nombre de Cliente','Ciudad','Estado',
                                          'Peso_KG','Valor_USD','Costo_Flete_Total']
                              if c in df_clientes_a_conc.columns]
                    df_dc = df_clientes_a_conc[cols_c].copy().rename(columns={
                        'Peso_KG':'Volumen (Kg)', 'Valor_USD':'Valor (USD)',
                        'Costo_Flete_Total':'Flete Gandola (USD)'
                    }).sort_values('Volumen (Kg)', ascending=False).reset_index(drop=True)
                    df_dc.index += 1

                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1: st.metric("👥 Total Clientes", f"{len(df_dc)}")
                    with col_r2: st.metric("⚖️ Volumen Total",  f"{fmt_num(df_dc['Volumen (Kg)'].sum(), 1)} Kg")
                    with col_r3: st.metric("💵 Valor Total",    f"${fmt_num(df_dc['Valor (USD)'].sum(), 2)}")

                    top_sel = st.radio("Mostrar:", options=[5, 20, 50, 100, len(df_dc)],
                        format_func=lambda x: f"Top {x}" if x != len(df_dc) else "Ver Todos",
                        horizontal=True, key="top_conc")

                    # ✅ CORREGIDO: bloque _display que faltaba completamente
                    df_dc_display = df_dc.head(top_sel).copy()
                    df_dc_display['Volumen (Kg)'] = df_dc_display['Volumen (Kg)'].apply(lambda x: fmt_num(x, 1))
                    df_dc_display['Valor (USD)']  = df_dc_display['Valor (USD)'].apply(lambda x: fmt_num(x, 2))
                    if 'Flete Gandola (USD)' in df_dc_display.columns:
                        df_dc_display['Flete Gandola (USD)'] = df_dc_display['Flete Gandola (USD)'].apply(lambda x: fmt_num(x, 2))
                    st.dataframe(df_dc_display, use_container_width=True)

                    st.download_button("📥 Descargar (.xlsx)", data=convertir_df_a_excel(df_dc),
                        file_name="concentracion_clientes.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

                elif vista_actual == 'ambos':
                    st.markdown("#### 🔴 Clase A — Volumen (Kg)")
                    cols_v = [c for c in ['Id. Cliente','Nombre de Cliente','Ciudad','Estado',
                                          'Peso_KG','Valor_USD','Costo_Flete_Total']
                              if c in df_clientes_a_vol.columns]
                    df_dv = df_clientes_a_vol[cols_v].copy().rename(columns={
                        'Peso_KG':'Volumen (Kg)', 'Valor_USD':'Valor (USD)',
                        'Costo_Flete_Total':'Flete Gandola (USD)'
                    }).sort_values('Volumen (Kg)', ascending=False).reset_index(drop=True)
                    df_dv.index += 1

                    col_r1, col_r2, col_r3 = st.columns(3)
                    with col_r1: st.metric("👥 Total Clientes", f"{len(df_dv)}")
                    with col_r2: st.metric("⚖️ Volumen Total",  f"{fmt_num(df_dv['Volumen (Kg)'].sum(), 1)} Kg")
                    with col_r3: st.metric("💵 Valor Total",    f"${fmt_num(df_dv['Valor (USD)'].sum(), 2)}")

                    top_dv = st.radio("Mostrar:", options=[5, 20, 50, 100, len(df_dv)],
                        format_func=lambda x: f"Top {x}" if x != len(df_dv) else "Ver Todos",
                        horizontal=True, key="top_ambos_vol")

                    # Aplicar formato latino a columnas numéricas antes de mostrar
                    df_dv_display = df_dv.head(top_dv).copy()
                    df_dv_display['Volumen (Kg)'] = df_dv_display['Volumen (Kg)'].apply(lambda x: fmt_num(x, 1))
                    df_dv_display['Valor (USD)']  = df_dv_display['Valor (USD)'].apply(lambda x: fmt_num(x, 2))
                    if 'Flete Gandola (USD)' in df_dv_display.columns:
                        df_dv_display['Flete Gandola (USD)'] = df_dv_display['Flete Gandola (USD)'].apply(lambda x: fmt_num(x, 2))
                    st.dataframe(df_dv_display, use_container_width=True)

                    st.download_button("📥 Descargar Clase A Volumen (.xlsx)",
                        data=convertir_df_a_excel(df_dv), file_name="clase_a_volumen.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key="dl_ambos_vol")

                    st.markdown("---")
                    st.markdown("#### 🔵 Clase A — Valor Monetario (USD)")
                    cols_u = [c for c in ['Id. Cliente','Nombre de Cliente','Ciudad','Estado',
                                          'Peso_KG','Valor_USD','Costo_Flete_Total']
                              if c in df_clientes_a_val.columns]
                    df_du = df_clientes_a_val[cols_u].copy().rename(columns={
                        'Peso_KG':'Volumen (Kg)', 'Valor_USD':'Valor (USD)',
                        'Costo_Flete_Total':'Flete Gandola (USD)'
                    }).sort_values('Valor (USD)', ascending=False).reset_index(drop=True)
                    df_du.index += 1

                    col_r4, col_r5, col_r6 = st.columns(3)
                    with col_r4: st.metric("👥 Total Clientes", f"{len(df_du)}")
                    with col_r5: st.metric("⚖️ Volumen Total",  f"{fmt_num(df_du['Volumen (Kg)'].sum(), 1)} Kg")
                    with col_r6: st.metric("💵 Valor Total",    f"${fmt_num(df_du['Valor (USD)'].sum(), 2)}")

                    top_du = st.radio("Mostrar:", options=[5, 20, 50, 100, len(df_du)],
                        format_func=lambda x: f"Top {x}" if x != len(df_du) else "Ver Todos",
                        horizontal=True, key="top_ambos_val")

                    # Aplicar formato latino a columnas numéricas antes de mostrar
                    df_du_display = df_du.head(top_du).copy()
                    df_du_display['Volumen (Kg)'] = df_du_display['Volumen (Kg)'].apply(lambda x: fmt_num(x, 1))
                    df_du_display['Valor (USD)']  = df_du_display['Valor (USD)'].apply(lambda x: fmt_num(x, 2))
                    if 'Flete Gandola (USD)' in df_du_display.columns:
                        df_du_display['Flete Gandola (USD)'] = df_du_display['Flete Gandola (USD)'].apply(lambda x: fmt_num(x, 2))
                    st.dataframe(df_du_display, use_container_width=True)

                    # ✅ CORREGIDO: segunda tabla duplicada eliminada
                    st.download_button("📥 Descargar Clase A Valor (.xlsx)",
                        data=convertir_df_a_excel(df_du), file_name="clase_a_valor.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key="dl_ambos_val")

                st.markdown("---")
                st.subheader("Demanda por Región Geográfica")
                df_region = df_maestro.copy()
                df_region[['Region','Subregion']] = df_region.apply(
                    lambda r: pd.Series(clasificar_region(
                        r.get('Ciudad',''), r.get('Estado','')
                    )), axis=1
                )
                resumen_region = (df_region
                    .groupby(['Region','Subregion'])
                    .agg(Peso_KG=('Peso_KG','sum'), Valor_USD=('Valor_USD','sum'))
                    .reset_index()
                    .sort_values('Peso_KG', ascending=False))
                resumen_region['Toneladas']   = (resumen_region['Peso_KG'] / 1000).round(1)
                resumen_region['Valor (USD)'] = resumen_region['Valor_USD'].round(2)
                resumen_region['% Vol Total'] = (resumen_region['Peso_KG'] / resumen_region['Peso_KG'].sum() * 100).round(1)
                resumen_region['% Val Total'] = (resumen_region['Valor_USD'] / resumen_region['Valor_USD'].sum() * 100).round(1)

                resumen_principal = (df_region
                    .groupby('Region')
                    .agg(Peso_KG=('Peso_KG','sum'), Valor_USD=('Valor_USD','sum'))
                    .reset_index()
                    .sort_values('Peso_KG', ascending=False))
                resumen_principal['Toneladas']   = (resumen_principal['Peso_KG'] / 1000).round(1)
                resumen_principal['Valor (USD)'] = resumen_principal['Valor_USD'].round(2)
                resumen_principal['% Volumen']   = (resumen_principal['Peso_KG'] / resumen_principal['Peso_KG'].sum() * 100).round(1)
                resumen_principal['% Valor']     = (resumen_principal['Valor_USD'] / resumen_principal['Valor_USD'].sum() * 100).round(1)

                st.markdown("#### Resumen por Región Principal")
                n_regiones = len(resumen_principal)
                cols_reg   = st.columns(min(4, n_regiones))
                for i, (_, row) in enumerate(resumen_principal.head(4).iterrows()):
                    with cols_reg[i % 4]:
                        st.metric(
                            label=f"📍 {row['Region']}",
                            value=f"{fmt_num(row['Toneladas'], 1)} Ton",
                            delta=f"${fmt_num(row['Valor (USD)'], 0)} | {fmt_num(row['% Volumen'], 1)}% vol"
                        )
                if n_regiones > 4:
                    cols_reg2 = st.columns(min(4, n_regiones - 4))
                    for i, (_, row) in enumerate(resumen_principal.iloc[4:].iterrows()):
                        with cols_reg2[i]:
                            st.metric(
                                label=f"📍 {row['Region']}",
                                value=f"{fmt_num(row['Toneladas'], 1)} Ton",
                                delta=f"${fmt_num(row['Valor (USD)'], 0)} | {fmt_num(row['% Volumen'], 1)}% vol"
                            )

                st.markdown("---")
                st.markdown("#### Detalle por Subregión")

                resumen_region_display = resumen_region[['Region','Subregion','Toneladas','Valor (USD)','% Vol Total','% Val Total']].copy()
                resumen_region_display['Toneladas']   = resumen_region_display['Toneladas'].apply(lambda x: fmt_num(x, 1))
                resumen_region_display['Valor (USD)'] = resumen_region_display['Valor (USD)'].apply(lambda x: fmt_num(x, 2))
                st.dataframe(resumen_region_display, use_container_width=True, hide_index=True)

                # ── Agregar columna Region al df_maestro ──────────────────────
                df_maestro[['Region', 'Subregion']] = df_maestro.apply(
                    lambda r: pd.Series(clasificar_region(
                        r.get('Ciudad', ''), r.get('Estado', '')
                    )), axis=1
                )

                st.session_state['puntos_vol']            = puntos_vol
                st.session_state['puntos_val']            = puntos_val
                st.session_state['puntos_conc']           = puntos_conc
                st.session_state['df_maestro_financiero'] = df_maestro  # ← ya tiene 'Region'
            else:
                st.error(resultado[4])
        else:
            st.info("💡 Sube el archivo maestro unificado de Munchy para activar el motor geográfico.")

    # ================================================================
    with tab_fin:
        if 'df_maestro_financiero' not in st.session_state:
            st.info("💡 Primero carga el archivo maestro en **🗺️ Análisis Geográfico**.")
        else:
            modulo_analisis_financiero(
                df_maestro              = st.session_state['df_maestro_financiero'],
                df_ventas_raw           = st.session_state.get('df_ventas_raw', pd.DataFrame()),
                puntos_vol              = st.session_state.get('puntos_vol',  []),
                puntos_val              = st.session_state.get('puntos_val',  []),
                nombre_p                = nombre_p,
                lat_p                   = lat_p,
                lon_p                   = lon_p,
                lista_cendis_existentes = lista_cendis_existentes,
                archivo_maestro         = st.session_state.get('archivo_maestro', None),
            )

if __name__ == "__main__":
    main()
    