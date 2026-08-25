import os
import sys
import sqlite3
import requests
from collections import Counter
from datetime import datetime

from baloto_scraper import obtener_ultimo_sorteo
from database import guardar_sorteo

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def parse_fecha(f_str):
    """Convierte cadena de fecha a datetime soportando múltiples formatos."""
    if not f_str or not isinstance(f_str, str):
        return datetime.now()
    
    f_clean = f_str.strip()
    formatos = (
        "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", 
        "%Y-%m-%dT%H:%M:%S", "%d-%b-%Y"
    )
    
    for fmt in formatos:
        try:
            return datetime.strptime(f_clean, fmt)
        except ValueError:
            pass
            
    print(f"⚠️ Formato de fecha no reconocido: '{f_clean}'. Usando fecha actual.")
    return datetime.now()

def generar_y_enviar_reporte():
    # 0. Actualizar base de datos vía Web Scraping
    print("🔍 Verificando si hay nuevos sorteos...")
    try:
        sorteo_nuevo = obtener_ultimo_sorteo()
        if sorteo_nuevo:
            # Intento de guardado según firmas soportadas sin alterar lógica previa
            if 'revancha_numeros' in sorteo_nuevo and 'revancha_superbalota' in sorteo_nuevo:
                try:
                    guardar_sorteo(
                        sorteo_nuevo['fecha'], sorteo_nuevo['numeros'], sorteo_nuevo['superbalota'],
                        sorteo_nuevo['revancha_numeros'], sorteo_nuevo['revancha_superbalota']
                    )
                except TypeError:
                    guardar_sorteo(sorteo_nuevo['fecha'], sorteo_nuevo['numeros'], sorteo_nuevo['superbalota'])
            else:
                guardar_sorteo(sorteo_nuevo['fecha'], sorteo_nuevo['numeros'], sorteo_nuevo['superbalota'])
    except Exception as e:
        print(f"⚠️ No se pudo ejecutar el scraper: {e}")

    # 1. Consultar historial Baloto Tradicional
    conn = sqlite3.connect('baloto.db')
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(sorteos)")
    columnas = [col[1] for col in cursor.fetchall()]
    
    if 'b1' in columnas:
        cols_query = "b1, b2, b3, b4, b5, sb"
    else:
        cols_query = "n1, n2, n3, n4, n5, superbalota"

    cursor.execute(f"SELECT fecha, {cols_query} FROM sorteos ORDER BY fecha DESC")
    sorteos = cursor.fetchall()

    if not sorteos:
        print("❌ No hay sorteos en la base de datos.")
        conn.close()
        sys.exit(1)

# 1.1 Consultar historial Baloto Revancha
    sorteos_revancha = []
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tablas = [t[0] for t in cursor.fetchall()]

    if 'sorteos_revancha' in tablas:
        cursor.execute("PRAGMA table_info(sorteos_revancha)")
        cols_rev = [col[1] for col in cursor.fetchall()]
        cols_q = "b1, b2, b3, b4, b5, sb" if 'b1' in cols_rev else ("n1, n2, n3, n4, n5, superbalota" if 'n1' in cols_rev else "*")
        cursor.execute(f"SELECT fecha, {cols_q} FROM sorteos_revancha ORDER BY fecha DESC LIMIT 20")
        sorteos_revancha = cursor.fetchall()
    elif 'revancha' in tablas:
        cursor.execute("PRAGMA table_info(revancha)")
        cols_rev = [col[1] for col in cursor.fetchall()]
        cols_q = "b1, b2, b3, b4, b5, sb" if 'b1' in cols_rev else ("n1, n2, n3, n4, n5, superbalota" if 'n1' in cols_rev else "*")
        cursor.execute(f"SELECT fecha, {cols_q} FROM revancha ORDER BY fecha DESC LIMIT 20")
        sorteos_revancha = cursor.fetchall()
    else:
        # Buscar columnas de revancha en la misma tabla 'sorteos'
        col_r_balotas = []
        for prefijo in ['r', 'rb', 'rn', 'rev']:
            cands = [f"{prefijo}{i}" for i in range(1, 6)]
            if all(c in columnas for c in cands):
                col_r_balotas = cands
                break
        
        col_r_sb = None
        for cand_sb in ['sbr', 'rsb', 'rsuperbalota', 'rev_sb', 'sb_revancha', 'superbalota_revancha', 'sb_r', 'sb']:
            if cand_sb in columnas and cand_sb not in col_r_balotas:
                col_r_sb = cand_sb
                break

        if col_r_balotas and col_r_sb:
            cols_rev_str = ", ".join(col_r_balotas) + f", {col_r_sb}"
            first_c = col_r_balotas[0]
            cursor.execute(f"SELECT fecha, {cols_rev_str} FROM sorteos WHERE {first_c} IS NOT NULL ORDER BY fecha DESC LIMIT 20")
            sorteos_revancha = cursor.fetchall()

    conn.close()

    total_sorteos = len(sorteos)
    fecha_mas_reciente = sorteos[0][0]
    fecha_mas_antigua = sorteos[-1][0]
    dt_mas_reciente = parse_fecha(fecha_mas_reciente)

    # Ventana de exclusión (Últimos 3 sorteos)
    num_ultimo = set(sorteos[0][1:6]) if len(sorteos) > 0 else set()
    num_penultimo = set(sorteos[1][1:6]) if len(sorteos) > 1 else set()
    num_antepenultimo = set(sorteos[2][1:6]) if len(sorteos) > 2 else set()

    sb_ultimo = {sorteos[0][6]} if len(sorteos) > 0 else set()
    sb_penultimo = {sorteos[1][6]} if len(sorteos) > 1 else set()
    sb_antepenultimo = {sorteos[2][6]} if len(sorteos) > 2 else set()

    recientes_balotas = num_ultimo | num_penultimo | num_antepenultimo
    recientes_superbalotas = sb_ultimo | sb_penultimo | sb_antepenultimo

    # 2. Conteo de Frecuencias (Estándar y Ponderada)
    conteo_estandar_balotas = Counter()
    conteo_estandar_sb = Counter()
    
    conteo_ponderado_balotas = Counter()
    conteo_ponderado_sb = Counter()

    for s in sorteos:
        dt_sorteo = parse_fecha(s[0])
        dias_diferencia = (dt_mas_reciente - dt_sorteo).days
        peso = 1.5 if dias_diferencia <= 90 else 1.0

        conteo_estandar_balotas.update(s[1:6])
        conteo_estandar_sb.update([s[6]])

        for num in s[1:6]:
            conteo_ponderado_balotas[num] += peso
        conteo_ponderado_sb[s[6]] += peso

    frec_estandar_balotas = conteo_estandar_balotas.most_common()
    frec_estandar_sb = conteo_estandar_sb.most_common()

    frec_pond_balotas = conteo_ponderado_balotas.most_common()
    frec_pond_sb = conteo_ponderado_sb.most_common()

    top_6_balotas = set([num for num, _ in frec_estandar_balotas[:6]])
    top_6_superbalotas = set([sb for sb, _ in frec_estandar_sb[:6]])

    # 3. Pronósticos
    p1_balotas_filtradas = [num for num, _ in frec_estandar_balotas if num not in recientes_balotas]
    p1_sb_filtradas = [sb for sb, _ in frec_estandar_sb if sb not in recientes_superbalotas]
    p1_balotas = sorted(p1_balotas_filtradas[:5])
    p1_sb = p1_sb_filtradas[0] if p1_sb_filtradas else frec_estandar_sb[0][0]

    p2_balotas_filtradas = [num for num, _ in frec_pond_balotas if num not in recientes_balotas]
    p2_sb_filtradas = [sb for sb, _ in frec_pond_sb if sb not in recientes_superbalotas]
    p2_balotas = sorted(p2_balotas_filtradas[:5])
    p2_sb = p2_sb_filtradas[0] if p2_sb_filtradas else frec_pond_sb[0][0]

    str_p1 = " - ".join([f"{n:02d}" for n in p1_balotas])
    str_p2 = " - ".join([f"{n:02d}" for n in p2_balotas])

    # 4. Formatear Frecuencia Balotas
    lineas_frecuencia = []
    for num, frec in frec_estandar_balotas:
        etiqueta = ""
        if num in top_6_balotas:
            if num in num_ultimo:
                etiqueta = " 🔴 [Último]"
            elif num in num_penultimo:
                etiqueta = " 🟠 [Penúlt.]"
            elif num in num_antepenultimo:
                etiqueta = " 🟡 [Antep.]"
        lineas_frecuencia.append(f"Balota {num:02d}: {frec} veces{etiqueta}")

    # 5. Formatear Frecuencia Superbalotas
    lineas_superbalotas = []
    for sb, frec in frec_estandar_sb:
        etiqueta = ""
        if sb in top_6_superbalotas:
            if sb in sb_ultimo:
                etiqueta = " 🔴 [Último]"
            elif sb in sb_penultimo:
                etiqueta = " 🟠 [Penúlt.]"
            elif sb in sb_antepenultimo:
                etiqueta = " 🟡 [Antep.]"
        lineas_superbalotas.append(f"Superbalota {sb:02d}: {frec} veces{etiqueta}")

    # 6. Formatear Historial Balotas Tradicional (Últimos 20)
    lineas_historial = []
    for s in sorteos[:20]:
        fecha, n1, n2, n3, n4, n5, sb = s
        lineas_historial.append(f"<b>{fecha}</b>: {n1:02d}-{n2:02d}-{n3:02d}-{n4:02d}-{n5:02d} (SB: {sb:02d})")

    # 7. Formatear Historial Balotas Revancha (Últimos 20)
    lineas_historial_rev = []
    for s in sorteos_revancha[:20]:
        fecha, r1, r2, r3, r4, r5, sbr = s
        lineas_historial_rev.append(f"<b>{fecha}</b>: {r1:02d}-{r2:02d}-{r3:02d}-{r4:02d}-{r5:02d} (SB: {sbr:02d})")

    # Mensaje consolidado
    mensaje = f"📅 <b>PERIODO HISTÓRICO: {fecha_mas_antigua} al {fecha_mas_reciente} ({total_sorteos} sorteos)</b>\n\n"
    mensaje += f"🎯 <b>PRONÓSTICO 1 (Frecuencia Histórica)</b>\n"
    mensaje += f"• Números: <b>{str_p1}</b>\n"
    mensaje += f"• Superbalota: <b>{p1_sb:02d}</b>\n\n"
    mensaje += f"⚡ <b>PRONÓSTICO 2 (Ponderado 3M x1.5)</b>\n"
    mensaje += f"• Números: <b>{str_p2}</b>\n"
    mensaje += f"• Superbalota: <b>{p2_sb:02d}</b>\n\n"
    mensaje += "<b>📊 FRECUENCIA BALOTAS</b>\n" + "\n".join(lineas_frecuencia[:10]) + "\n\n"
    mensaje += "<b>🔴 SUPERBALOTAS</b>\n" + "\n".join(lineas_superbalotas[:8]) + "\n\n"
    mensaje += "<b>📅 ÚLTIMOS 20 SORTEOS BALOTO</b>\n" + "\n".join(lineas_historial)
    
    if lineas_historial_rev:
        mensaje += "\n\n<b>🔄 ÚLTIMOS 20 SORTEOS REVANCHA</b>\n" + "\n".join(lineas_historial_rev)

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"})
        if res.status_code == 200:
            print("✅ Reporte enviado correctamente a Telegram.")
        else:
            print(f"⚠️ Error enviando a Telegram: {res.text}")
    else:
        print("⚠️ Faltan credenciales de Telegram en las variables de entorno.")

if __name__ == '__main__':
    generar_y_enviar_reporte()
