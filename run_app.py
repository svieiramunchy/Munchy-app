import sys
import subprocess
import os

# =====================================================================
# TRUCO MAESTRO: Detectar la ubicación exacta del proyecto
# =====================================================================
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_COMPLETA_APP = os.path.join(DIRECTORIO_ACTUAL, "app.py")

# Auto-instalador de todas las dependencias del proyecto
try:
    from streamlit.web import cli as stcli
except ModuleNotFoundError:
    print("⚠️ Instalando librerías... Espera unos segundos.")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "streamlit",
        "pandas",
        "numpy",
        "openpyxl",
        "folium",
        "streamlit-folium",
        "scikit-learn",
        "geopy",
        "plotly",
    ])
    from streamlit.web import cli as stcli

# Verificar que app.py existe
if not os.path.exists(RUTA_COMPLETA_APP):
    print(f"❌ No se encontró app.py en: {RUTA_COMPLETA_APP}")
    sys.exit(1)

if __name__ == "__main__":
    print(f"🚀 Arrancando: {RUTA_COMPLETA_APP}")
    sys.argv = ["streamlit", "run", RUTA_COMPLETA_APP]
    sys.exit(stcli.main())