"""
=============================================================================
DASHBOARD INTERACTIVO DE CONTROL Y ANÁLISIS
Proyecto: Punto de equilibrio y sensibilidad en un proyecto turístico regional
Finanzas I (055D) - UNCP | Dr. Ciro Iván Machacuay Meza
=============================================================================
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_from_directory
import pandas as pd

app = Flask(__name__, template_folder="templates")

BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
DATOS_DIR = BASE_DIR / "datos"
SALIDAS_DIR = BASE_DIR / "salidas"
LOGS_FILE = BASE_DIR / "log_ejecucion.txt"
HASH_FILE = BASE_DIR / "hash_sha256.txt"

# Usar el intérprete de Python en ejecución
PYTHON_EXE = sys.executable

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/salidas/<path:filename>")
def servir_salidas(filename):
    return send_from_directory(SALIDAS_DIR, filename)

@app.route("/api/status")
def get_status():
    """Retorna el estado actual de los archivos y salidas del proyecto."""
    status = {
        "crudo_api": (DATOS_DIR / "datos_crudos_api.json").exists(),
        "crudo_mincetur": (DATOS_DIR / "datos_crudos_mincetur.csv").exists(),
        "procesados": (DATOS_DIR / "datos_procesados_turismo.csv").exists(),
        "hash_sha256": "",
        "num_filas_procesadas": 0,
        "salidas_disponibles": {
            "figura1": (SALIDAS_DIR / "figura1_evolucion_ocupacion_equilibrio.png").exists(),
            "figura2": (SALIDAS_DIR / "figura2_sensibilidad_demanda.png").exists(),
            "figura3": (SALIDAS_DIR / "figura3_vulnerabilidad_departamental.png").exists(),
            "tabla1": (SALIDAS_DIR / "tabla1_estadisticas_descriptivas.csv").exists(),
            "tabla2": (SALIDAS_DIR / "tabla2_ranking_equilibrio_departamental.csv").exists(),
            "tabla3": (SALIDAS_DIR / "tabla3_modelo_sensibilidad.csv").exists()
        }
    }
    
    if HASH_FILE.exists():
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            status["hash_sha256"] = f.read().strip()
            
    if (DATOS_DIR / "datos_procesados_turismo.csv").exists():
        try:
            df = pd.read_csv(DATOS_DIR / "datos_procesados_turismo.csv", usecols=["periodo"])
            status["num_filas_procesadas"] = len(df)
        except Exception:
            pass
            
    return jsonify(status)

@app.route("/api/run/<int:paso>", methods=["POST"])
def run_step(paso):
    """Ejecuta un script específico (1 a 4) y retorna el log de ejecución."""
    mapa_scripts = {
        1: "01_extraccion_api.py",
        2: "02_scraping_web.py",
        3: "03_limpieza_datos.py",
        4: "04_analisis.py"
    }
    
    if paso not in mapa_scripts:
        return jsonify({"success": False, "error": f"Paso {paso} no válido."}), 400
        
    script_path = SCRIPTS_DIR / mapa_scripts[paso]
    t0 = time.time()
    
    try:
        proc = subprocess.run(
            [PYTHON_EXE, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=str(BASE_DIR)
        )
        t1 = time.time()
        duracion = round(t1 - t0, 2)
        
        salida_std = proc.stdout
        salida_err = proc.stderr
        exito = (proc.returncode == 0)
        
        return jsonify({
            "success": exito,
            "script": mapa_scripts[paso],
            "duracion_segundos": duracion,
            "stdout": salida_std,
            "stderr": salida_err,
            "returncode": proc.returncode
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/datos/api-raw")
def get_api_raw():
    """Devuelve datos de BCRP y Banco Mundial extraídos."""
    archivo = DATOS_DIR / "datos_crudos_api.json"
    if not archivo.exists():
        return jsonify({"error": "Aún no se ha ejecutado la Vía 1"}), 404
    with open(archivo, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/api/datos/mincetur-sample")
def get_mincetur_sample():
    """Devuelve muestra filtrada de datos crudos de MINCETUR."""
    archivo = DATOS_DIR / "datos_crudos_mincetur.csv"
    if not archivo.exists():
        return jsonify({"error": "Aún no se ha ejecutado la Vía 2"}), 404
    
    region = request.args.get("region", "")
    limite = int(request.args.get("limit", 25))
    
    df = pd.read_csv(archivo)
    if region:
        df = df[df["region"].str.contains(region, case=False, na=False)]
    
    return jsonify({
        "total_registros": len(df),
        "columnas": list(df.columns),
        "filas": df.head(limite).to_dict(orient="records")
    })

@app.route("/api/datos/procesados-sample")
def get_procesados_sample():
    """Devuelve muestra del dataset final procesado."""
    archivo = DATOS_DIR / "datos_procesados_turismo.csv"
    if not archivo.exists():
        return jsonify({"error": "Aún no se ha ejecutado la limpieza (Vía 3)"}), 404
        
    region = request.args.get("region", "")
    limite = int(request.args.get("limit", 25))
    
    df = pd.read_csv(archivo)
    if region:
        df = df[df["region"].str.contains(region, case=False, na=False)]
        
    return jsonify({
        "total_registros": len(df),
        "columnas": list(df.columns),
        "filas": df.head(limite).to_dict(orient="records")
    })

@app.route("/api/datos/tabla/<nombre>")
def get_tabla_salida(nombre):
    """Devuelve las tablas estimadas en formato JSON."""
    archivo = SALIDAS_DIR / f"{nombre}.csv"
    if not archivo.exists():
        return jsonify({"error": f"La tabla {nombre} no existe"}), 404
    df = pd.read_csv(archivo)
    return jsonify({
        "columnas": list(df.columns),
        "filas": df.to_dict(orient="records")
    })

@app.route("/api/logs")
def get_logs():
    """Retorna el contenido de log_ejecucion.txt."""
    if not LOGS_FILE.exists():
        return jsonify({"logs": "Aún no hay logs registrados."})
    with open(LOGS_FILE, "r", encoding="utf-8") as f:
        contenido = f.read()
    return jsonify({"logs": contenido})

if __name__ == "__main__":
    puerto = 5000
    print(f"Iniciando Dashboard Finanzas UNCP en http://127.0.0.1:{puerto}")
    app.run(host="127.0.0.1", port=puerto, debug=False)
