import os
import sys
import sqlite3
import requests
from collections import Counter

from baloto_scraper import obtener_ultimo_sorteo
from database import guardar_sorteo

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Carga segura desde variables de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def generar_y_enviar_reporte():
    # 0. Actualizar base de datos vía Web Scraping
    print("🔍 Verificando si hay nuevos sorteos...")
    try:
        sorteo_nuevo = obtener_ultimo_sorteo()
        if sorteo_nuevo:
            guardar_sorteo(sorteo_nuevo['fecha'], sorteo_nuevo['numeros'], sorteo_nuevo['superbalota'])
    except Exception as e:
        print(f"⚠️ No se pudo ejecutar el scraper: {e}")

    # 1. Consultar historial ordenado por fecha DESCENDENTE
    conn = sqlite3.connect('baloto.db')
    cursor = conn.cursor()
    
    # Inspeccionar columnas para soportar esquemas previos (b1..b5 o n1..n5)
    cursor.execute("PRAGMA table_info(sorteos)")
    columnas = [col[1] for col in cursor.fetchall()]
    
    if 'b1' in columnas:
        cols_query = "b1, b2, b3, b4, b5, sb"
    else:
        cols_query = "n1, n2, n3, n4, n5, superbalota"

    cursor.execute(f"SELECT fecha, {cols_query} FROM sorteos ORDER BY fecha DESC")
    sorteos = cursor.fetchall()
    conn.close()

    if not sorteos:
        print("❌ No hay sorteos en la base de datos.")
        sys.exit(1)

    total_sorteos = len(sorteos)
    fecha_mas_reciente = sorteos[0][0]
    fecha_mas_antigua = sorteos[-1][0]

    # Números de los últimos 3 sorteos para exclusión
    num_ultimo = set(sorteos[0][1:6]) if len(sorteos) > 0 else set()
    num_penultimo = set(sorteos[1][1:6]) if len(sorteos) > 1 else set()
    num_antepenultimo = set(sorteos[2][1:6]) if len(sorteos) > 2 else set()

    sb_ultimo = {sorteos[0][6]} if len(sorteos) > 0 else set()
    sb_penultimo = {sorteos[1][6]} if len(sorteos) > 1 else set()
    sb_antepenultimo = {sorteos[2][6]} if len(sorteos) > 2 else set()

    recientes_balotas = num_ultimo | num_penultimo | num_antepenultimo
    recientes_superbalotas = sb_ultimo | sb_penultimo | sb_antepenultimo

    # 2. Conteo de frecuencias
    conteo_balotas = Counter()
    conteo_superbalotas = Counter()

    for s in sorteos:
        conteo_balotas.update(s[1:6])
        conteo_superbalotas.update([s[6]])

    frecuencia_balotas = conteo_balotas.most_common()
    frecuencia_superbalotas = conteo_superbalotas.most_common()

    top_6_balotas = set([num for num, _ in frecuencia_balotas[:6]])
    top_6_superbalotas = set([sb for sb, _ in frecuencia_superbalotas[:6]])

    # 3. Pronóstico
    balotas_filtradas = [num for num, _ in frecuencia_balotas if num not in recientes_balotas]
    superbalotas_filtradas = [sb for sb, _ in frecuencia_superbalotas if sb not in recientes_superbalotas]

    pronostico_balotas = sorted(balotas_filtradas[:5])
    pronostico_sb = superbalotas_filtradas[0] if superbalotas_filtradas else frecuencia_superbalotas[0][0]
    str_pronostico = " - ".join([f"{n:02d}" for n in pronostico_balotas])

    # 4. Formatear Frecuencia Balotas
    lineas_frecuencia = []
    for num, frec in frecuencia_balotas:
        etiqueta = ""
        if num in top_6_balotas:
            if num in num_ultimo:
                etiqueta = " 🔴 [Último]"
            elif num in num_penultimo:
                etiqueta = " 🟠 [Penúltimo]"
            elif num in num_antepenultimo:
                etiqueta = " 🟡 [Antepenúltimo]"
        lineas_frecuencia.append(f"Balota {num:02d}: {frec} apariciones{etiqueta}")

    # 5. Formatear Frecuencia Superbalotas
    lineas_superbalotas = []
    for sb, frec in frecuencia_superbalotas:
        etiqueta = ""
        if sb in top_6_superbalotas:
            if sb in sb_ultimo:
                etiqueta = " 🔴 [Último]"
            elif sb in sb_penultimo:
                etiqueta = " 🟠 [Penúltimo]"
            elif sb in sb_antepenultimo:
                etiqueta = " 🟡 [Antepenúltimo]"
        lineas_superbalotas.append(f"Superbalota {sb:02d}: {frec} apariciones{etiqueta}")

    # 6. Formatear Historial
    lineas_historial = []
    for s in sorteos[:5]:
        fecha, n1, n2, n3, n4, n5, sb = s
        lineas_historial.append(f"<b>{fecha}</b>: {n1:02d}-{n2:02d}-{n3:02d}-{n4:02d}-{n5:02d} (SB: {sb:02d})")

    # Mensaje consolidado
    mensaje = f"📅 <b>PERIODO HISTÓRICO: {fecha_mas_antigua} al {fecha_mas_reciente} ({total_sorteos} sorteos)</b>\n\n"
    mensaje += f"🎯 <b>PRONÓSTICO SUGERIDO (Excluyendo Recientes)</b>\n"
    mensaje += f"• Números: <b>{str_pronostico}</b>\n"
    mensaje += f"• Superbalota: <b>{pronostico_sb:02d}</b>\n\n"
    mensaje += "<b>📊 FRECUENCIA BALOTAS</b>\n" + "\n".join(lineas_frecuencia[:10]) + "\n\n"
    mensaje += "<b>🔴 SUPERBALOTAS</b>\n" + "\n".join(lineas_superbalotas[:8]) + "\n\n"
    mensaje += "<b>📅 ÚLTIMOS SORTEOS</b>\n" + "\n".join(lineas_historial)

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
