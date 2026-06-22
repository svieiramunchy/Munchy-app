# =====================================================================
# utils_munchy.py
# Funciones y datos compartidos entre app.py y modulo_analisis_financiero.py
# =====================================================================

# =====================================================================
# CONSTANTES
# =====================================================================
CALETA_GANDOLA  = 50.0
RADIO_COBERTURA = 1.80

TARIFAS_GANDOLA = {
    'PLANTA': {
        'MARACAY':                  128.0,
        'LA VICTORIA':              128.0,
        'VILLA DE CURA':            128.0,
        'GUACARA':                  128.0,
        'TEJERIAS':                 128.0,
        'SAN JUAN DE LOS MORROS':   128.0,
        'VALENCIA':                 179.2,
        'LOS TEQUES':               179.2,
        'PARACOTOS':                179.2,
        'GUIGUE':                   204.8,
        'CAMPO CARABOBO':           230.4,
        'CUA':                      230.4,
        'CHARALLAVE':               179.2,
        'BEJUMA':                   256.0,
        'STA TERESA':               256.0,
        'SANTA TERESA':             256.0,
        'MORON':                    256.0,
        'PTO CABELLO':              256.0,
        'PUERTO CABELLO':           256.0,
        'CARACAS':                  256.0,
        'LITORAL':                  300.0,
        'TUCACAS':                  300.0,
        'NIRGUA':                   300.0,
        'LA GUAIRA':                300.0,
        'CATIA LA MAR':             300.0,
        'SAN CARLOS':               300.0,
        'GUATIRE':                  300.0,
        'SAN FELIPE':               300.0,
        'CALABOZO':                 300.0,
        'ACARIGUA':                 300.0,
        'ARAURE':                   300.0,
        'BARQUISIMETO':             378.0,
        'DUACA':                    378.0,
        'TUREN':                    378.0,
        'HIGUEROTE':                378.0,
        'VALLE DE LAS PASCUAS':     378.0,
        'SAN FERNANDO DE APURE':    384.0,
        'GUANARE':                  384.0,
        'CORO':                     460.8,
        'TUCUPIDO':                 460.8,
        'CARORA':                   460.8,
        'BARINAS':                  537.6,
        'PUNTO FIJO':               460.0,
        'BARCELONA':                460.0,
        'PUERTO LA CRUZ':           600.0,
        'BOCONO':                   560.0,
        'VALERA':                   600.0,
        'ANACO':                    600.0,
        'CUMANA':                   600.0,
        'EL TIGRE':                 600.0,
        'PORLAMAR':                 620.0,
        'MARACAIBO':                620.0,
        'VILLA DEL ROSARIO':        620.0,
        'MATURIN':                  874.8,
        'EL VIGIA':                 874.8,
        'CARUPANO':                 899.1,
        'CARIPITO':                 884.0,
        'CIUDAD BOLIVAR':           884.0,
        'SAN CRISTOBAL':            884.0,
        'SAN FELIX':                928.2,
        'UPATA':                    928.2,
        'TUCUPITA':                 928.2,
        'MERIDA':                   884.0,
        'LA GRITA':                 884.0,
        'GUASDUALITO':              884.0,
        'SANTA BARBARA DEL ZULIA':  884.0,
        'CIUDAD GUAYANA':           928.2,
    },
    'CCS': {
        'CARACAS':          205.85,
        'LOS TEQUES':       205.85,
        'OCUMARE DEL TUY':  218.0,
        'LA GUAIRA':        205.85,
        'CATIA LA MAR':     205.85,
        'GUATIRE':          218.5,
        'HIGUEROTE':        218.5,
        'GUARENAS':         218.5,
        'CHARALLAVE':       205.85,
        'CUA':              205.85,
    },
    'BQTO': {
        'BARQUISIMETO':             270.0,
        'CABUDARE':                 270.0,
        'YARITAGUA':                270.0,
        'SAN FELIPE':               360.72,
        'ACARIGUA':                 360.72,
        'ARAURE':                   360.72,
        'CARORA':                   360.72,
        'OSPINO':                   399.6,
        'BEJUMA':                   345.6,
        'MORON':                    345.6,
        'SAN CARLOS':               437.4,
        'GUANARE':                  475.2,
        'TINAQUILLO':               475.2,
        'BARINAS':                  693.36,
        'CORO':                     693.36,
        'CIUDAD OJEDA':             703.08,
        'CABIMAS':                  712.8,
        'MARACAIBO':                807.84,
        'PUNTO FIJO':               772.2,
        'EL VIGIA':                 817.56,
        'MERIDA':                   930.96,
        'VALERA':                   693.36,
        'SAN CRISTOBAL':            1188.0,
        'TARIBA':                   1188.0,
        'LA FRIA':                  1045.44,
        'LA GRITA':                 1140.48,
        'SANTA BARBARA DEL ZULIA':  1045.44,
        'VILLA DEL ROSARIO':        930.96,
        'TOVAR':                    1045.44,
        'EJIDO':                    1045.44,
    },
}

CIUDADES_VENEZUELA = {
    # Capital
    'CARACAS':                 (10.4806,  -66.9036),
    'LOS TEQUES':              (10.3419,  -67.0427),
    'GUARENAS':                (10.4697,  -66.5397),
    'GUATIRE':                 (10.4731,  -66.5322),
    'CHARALLAVE':              (10.2427,  -66.8744),
    'CUA':                     (10.1600,  -66.8797),
    'HIGUEROTE':               (10.4978,  -66.0933),
    'CATIA LA MAR':            (10.6032,  -67.0300),
    'LA GUAIRA':               (10.6032,  -66.9341),
    'OCUMARE DEL TUY':         (10.1131,  -66.7756),
    # Centro
    'MARACAY':                 (10.2469,  -67.5958),
    'TURMERO':                 (10.2283,  -67.4792),
    'CAGUA':                   (10.1878,  -67.4578),
    'VILLA DE CURA':           (10.0433,  -67.4900),
    'LA VICTORIA':             (10.2283,  -67.3319),
    'SAN JUAN DE LOS MORROS':  ( 9.9094,  -67.3553),
    'VALENCIA':                (10.1621,  -68.0073),
    'GUACARA':                 (10.2333,  -67.8833),
    'NAGUANAGUA':              (10.2500,  -68.0167),
    'SAN CARLOS':              ( 9.6500,  -68.5833),
    'TINAQUILLO':              ( 9.9167,  -68.3000),
    # Centro-Occidente
    'BARQUISIMETO':            (10.0644,  -69.3570),
    'CABUDARE':                (10.0283,  -69.2733),
    'CARORA':                  (10.1747,  -70.0778),
    'ACARIGUA':                ( 9.5606,  -69.2003),
    'ARAURE':                  ( 9.5700,  -69.2100),
    'GUANARE':                 ( 9.0417,  -69.7417),
    'TUREN':                   ( 9.2833,  -69.1000),
    'SAN FELIPE':              (10.3400,  -68.7442),
    'BARINAS':                 ( 8.6228,  -70.2081),
    'CORO':                    (11.4053,  -69.6817),
    'PUNTO FIJO':              (11.7033,  -70.2136),
    # Occidente
    'MARACAIBO':               (10.6544,  -71.6375),
    'SAN FRANCISCO':           (10.6000,  -71.6500),
    'CABIMAS':                 (10.3933,  -71.4581),
    'CIUDAD OJEDA':            (10.2058,  -71.3078),
    'SANTA BARBARA DEL ZULIA': ( 8.9753,  -71.1669),
    'VILLA DEL ROSARIO':       (10.3217,  -72.3133),
    # Andes
    'MERIDA':                  ( 8.5897,  -71.1561),
    'VALERA':                  ( 9.3194,  -70.6069),
    'EL VIGIA':                ( 8.6231,  -71.6561),
    'SAN CRISTOBAL':           ( 7.7667,  -72.2258),
    'TARIBA':                  ( 7.8167,  -72.2167),
    'LA FRIA':                 ( 8.2117,  -72.2483),
    'LA GRITA':                ( 8.1333,  -71.9833),
    'TOVAR':                   ( 8.3408,  -71.7544),
    'BOCONO':                  ( 9.2578,  -70.2567),
    # Oriente Norte
    'BARCELONA':               (10.1333,  -64.6833),
    'PUERTO LA CRUZ':          (10.2119,  -64.6331),
    'LECHERIA':                (10.1744,  -64.6878),
    'ANACO':                   ( 9.4400,  -64.4700),
    'EL TIGRE':                ( 8.8892,  -64.2556),
    'PORLAMAR':                (10.9631,  -63.8475),
    'PAMPATAR':                (10.9908,  -63.8044),
    'CUMANA':                  (10.4597,  -64.1736),
    'CARUPANO':                (10.6681,  -63.2558),
    # Oriente Sur
    'MATURIN':                 ( 9.7456,  -63.1808),
    'CARIPITO':                (10.1119,  -63.0997),
    'CIUDAD BOLIVAR':          ( 8.1228,  -63.5494),
    'CIUDAD GUAYANA':          ( 8.3539,  -62.6422),
    'SAN FELIX':               ( 8.3700,  -62.6500),
    'UPATA':                   ( 8.0139,  -62.4003),
    'TUCUPITA':                ( 9.0594,  -62.0522),
    'PUERTO AYACUCHO':         ( 5.6639,  -67.6233),
    'PUNTA DE MATA':           ( 9.6833,  -63.6167),
}

# =====================================================================
# FUNCIONES COMPARTIDAS
# =====================================================================
def clasificar_region(ciudad, estado):
    estado = str(estado).upper().strip()
    ciudad = str(ciudad).upper().strip()
    if estado in ['ANZOATEGUI', 'NUEVA ESPARTA', 'SUCRE'] or \
       any(c in ciudad for c in ['BARCELONA', 'PUERTO LA CRUZ', 'LECHERIA',
           'ANACO', 'EL TIGRE', 'PORLAMAR', 'PAMPATAR', 'CUMANA',
           'CARUPANO', 'JUAN GRIEGO']):
        return 'Oriente', 'Oriente Norte'
    if estado in ['BOLIVAR', 'DELTA AMACURO', 'AMAZONAS'] or \
       estado == 'MONAGAS' or \
       any(c in ciudad for c in ['MATURIN', 'CARIPITO', 'CIUDAD BOLIVAR',
           'CIUDAD GUAYANA', 'SAN FELIX', 'UPATA', 'TUCUPITA',
           'PUERTO AYACUCHO', 'PUNTA DE MATA']):
        return 'Oriente', 'Oriente Sur'
    if estado in ['DISTRITO CAPITAL', 'LA GUAIRA'] or \
       estado == 'MIRANDA' or \
       any(c in ciudad for c in ['CARACAS', 'LOS TEQUES', 'GUARENAS',
           'GUATIRE', 'CHARALLAVE', 'CUA', 'HIGUEROTE',
           'CATIA LA MAR', 'LA GUAIRA', 'SANTA TERESA']):
        return 'Capital', 'Capital'
    if estado in ['ARAGUA', 'CARABOBO', 'COJEDES'] or \
       any(c in ciudad for c in ['MARACAY', 'VALENCIA', 'TURMERO', 'CAGUA',
           'VILLA DE CURA', 'MARIARA', 'SAN CARLOS', 'TINAQUILLO',
           'GUACARA', 'NAGUANAGUA']):
        return 'Centro', 'Centro'
    if estado in ['LARA', 'PORTUGUESA', 'YARACUY', 'BARINAS', 'FALCON'] or \
       any(c in ciudad for c in ['BARQUISIMETO', 'CABUDARE', 'CARORA',
           'ACARIGUA', 'ARAURE', 'GUANARE', 'TUREN', 'SAN FELIPE',
           'BARINAS', 'CORO', 'PUNTO FIJO']):
        return 'Centro-Occidente', 'Centro-Occidente'
    if estado in ['MERIDA', 'TRUJILLO', 'TACHIRA'] or \
       any(c in ciudad for c in ['MERIDA', 'VALERA', 'EL VIGIA', 'BOCONO',
           'TOVAR', 'SAN CRISTOBAL', 'TARIBA', 'LA FRIA']):
        return 'Occidente-Andes', 'Andes'
    if estado in ['ZULIA'] or \
       any(c in ciudad for c in ['MARACAIBO', 'SAN FRANCISCO', 'CABIMAS',
           'CIUDAD OJEDA', 'SANTA BARBARA']):
        return 'Occidente-Andes', 'Occidente'
    return 'Otros', 'Otros'


def obtener_tarifa_gandola(ciudad, tabulador='PLANTA'):
    ciudad_norm = str(ciudad).upper().strip()
    tarifas     = TARIFAS_GANDOLA.get(tabulador, {})
    if ciudad_norm in tarifas:
        return tarifas[ciudad_norm] + CALETA_GANDOLA
    for clave, valor in tarifas.items():
        if clave in ciudad_norm or ciudad_norm in clave:
            return valor + CALETA_GANDOLA
    return 0.0


def obtener_coords_ciudad(ciudad_input):
    ciudad_norm = str(ciudad_input).upper().strip()
    if ciudad_norm in CIUDADES_VENEZUELA:
        return CIUDADES_VENEZUELA[ciudad_norm]
    for clave, coords in CIUDADES_VENEZUELA.items():
        if ciudad_norm in clave or clave in ciudad_norm:
            return coords
    return None, None

import numpy as np
def _distancia(lat1, lon1, lat2, lon2):
    """Distancia haversine simplificada corregida por latitud."""
    dlat = lat1 - lat2
    dlon = (lon1 - lon2) * np.cos(np.radians((lat1 + lat2) / 2.0))
    return np.sqrt(dlat**2 + dlon**2)