import os
import sys
import sqlite3
import requests
from collections import Counter
from datetime import datetime, timedelta

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
    sorteos_raw = cursor.fetchall()

    if not sorteos_raw:
        print("❌ No hay sorteos en la base de datos.")
        conn.close()
        sys.exit(1)

    # 1.1 Consultar historial Baloto Revancha (Estructura robusta)
    sorteos_revancha_raw = []
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tablas = [t[0] for t in cursor.fetchall()]

    if 'sorteos_revancha' in tablas:
        cursor.execute("PRAGMA table_info(sorteos_revancha)")
        cols_rev = [col[1] for col in cursor.fetchall()]
        cols_q = "b1, b2, b3, b4, b5, sb" if 'b1' in cols_rev else ("n1, n2, n3, n4, n5, superbalota" if 'n1' in cols_rev else "*")
        cursor.execute(f"SELECT fecha, {cols_q} FROM sorteos_revancha ORDER BY fecha DESC")
        sorteos_revancha_raw = cursor.fetchall()
    elif 'revancha' in tablas:
        cursor.execute("PRAGMA table_info(revancha)")
        cols_rev = [col[1] for col in cursor.fetchall()]
        cols_q = "b1, b2, b3, b4, b5, sb" if 'b1' in cols_rev else ("n1, n2, n3, n4, n5, superbalota" if 'n1' in cols_rev else "*")
        cursor.execute(f"SELECT fecha, {cols_q} FROM revancha ORDER BY fecha DESC")
        sorteos_revancha_raw = cursor.fetchall()
    else:
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
            cursor.execute(f"SELECT fecha, {cols_rev_str} FROM sorteos WHERE {first_c} IS NOT NULL ORDER BY fecha DESC")
            sorteos_revancha_raw = cursor.fetchall()

    conn.close()

    fecha_mas_reciente = sorteos_raw[0][0]
    dt_mas_reciente = parse_fecha(fecha_mas_reciente)

    # Periodo histórico general: último año (365 días)
    limite_1ano = dt_mas_reciente - timedelta(days=365)
    # Ventana de mayor peso para el ponderado (últimos 60 días / ~2 meses)
    limite_peso_reciente = dt_mas_reciente - timedelta(days=60)

    sorteos = [s for s in sorteos_raw if parse_fecha(s[0]) >= limite_1ano]
    if not sorteos:
        sorteos = [sorteos_raw[0]]

    sorteos_revancha = [s for s in sorteos_revancha_raw if parse_fecha(s[0]) >= limite_1ano]

    total_sorteos = len(sorteos)
    fecha_mas_antigua = sorteos[-1][0]

    # Ventanas de últimos 3 sorteos independientes para Normal y Revancha (para colores y exclusión)
    # NORMAL
    num_ultimo_norm = set(sorteos[0][1:6]) if len(sorteos) > 0 else set()
    num_penult_norm = set(sorteos[1][1:6]) if len(sorteos) > 1 else set()
    num_antep_norm = set(sorteos[2][1:6]) if len(sorteos) > 2 else set()

    sb_ultimo_norm = {sorteos[0][6]} if len(sorteos) > 0 else set()
    sb_penult_norm = {sorteos[1][6]} if len(sorteos) > 1 else set()
    sb_antep_norm = {sorteos[2][6]} if len(sorteos) > 2 else set()

    recientes_balotas_norm = num_ultimo_norm | num_penult_norm | num_antep_norm
    recientes_sb_norm = sb_ultimo_norm | sb_penult_norm | sb_antep_norm

    # REVANCHA
    num_ultimo_rev = set(sorteos_revancha[0][1:6]) if len(sorteos_revancha) > 0 else set()
    num_penult_rev = set(sorteos_revancha[1][1:6]) if len(sorteos_revancha) > 1 else set()
    num_antep_rev = set(sorteos_revancha[2][1:6]) if len(sorteos_revancha) > 2 else set()

    sb_ultimo_rev = {sorteos_revancha[0][6]} if len(sorteos_revancha) > 0 else set()
    sb_penult_rev = {sorteos_revancha[1][6]} if len(sorteos_revancha) > 1 else set()
    sb_antep_rev = {sorteos_revancha[2][6]} if len(sorteos_revancha) > 2 else set()

    recientes_balotas_rev = num_ultimo_rev | num_penult_rev | num_antep_rev
    recientes_sb_rev = sb_ultimo_rev | sb_penult_rev | sb_antep_rev

    # 2. Conteo de Frecuencias (HISTÓRICO 1 AÑO - Estándar)
    conteo_estandar_balotas = Counter()
    conteo_estandar_sb = Counter()

    for s in sorteos:
        conteo_estandar_balotas.update(s[1:6])
        conteo_estandar_sb.update([s[6]])

    for s in sorteos_revancha:
        conteo_estandar_balotas.update(s[1:6])
        conteo_estandar_sb.update([s[6]])

    frec_estandar_balotas = conteo_estandar_balotas.most_common()
    frec_estandar_sb = conteo_estandar_sb.most_common()

    # 2.1 Conteo de Frecuencias (PONDERADO REAL: 1 año completo multiplicando peso a los últimos 2 meses)
    conteo_ponderado_balotas = Counter()
    conteo_ponderado_sb = Counter()

    for s in sorteos:
        peso = 2.0 if parse_fecha(s[0]) >= limite_peso_reciente else 1.0
        for num in s[1:6]:
            conteo_ponderado_balotas[num] += peso
        conteo_ponderado_sb[s[6]] += peso

    for s in sorteos_revancha:
        peso = 2.0 if parse_fecha(s[0]) >= limite_peso_reciente else 1.0
        for num in s[1:6]:
            conteo_ponderado_balotas[num] += peso
        conteo_ponderado_sb[s[6]] += peso

    # .most_common() ordena automáticamente de mayor a menor puntaje ponderado acumulado
    frec_pond_balotas = conteo_ponderado_balotas.most_common()
    frec_pond_sb = conteo_ponderado_sb.most_common()

    # 3. Pronósticos
    recientes_balotas_total = recientes_balotas_norm | recientes_balotas_rev
    recientes_sb_total = recientes_sb_norm | recientes_sb_rev

    p1_balotas_filtradas = [num for num, _ in frec_estandar_balotas if num not in recientes_balotas_total]
    p1_sb_filtradas = [sb for sb, _ in frec_estandar_sb if sb not in recientes_sb_total]
    p1_balotas = sorted(p1_balotas_filtradas[:5])
    p1_sb = p1_sb_filtradas[0] if p1_sb_filtradas else (frec_estandar_sb[0][0] if frec_estandar_sb else 1)

    p2_balotas_filtradas = [num for num, _ in frec_pond_balotas if num not in recientes_balotas_total]
    p2_sb_filtradas = [sb for sb, _ in frec_pond_sb if sb not in recientes_sb_total]
    p2_balotas = sorted(p2_balotas_filtradas[:5])
    p2_sb = p2_sb_filtradas[0] if p2_sb_filtradas else (frec_pond_sb[0][0] if frec_pond_sb else 1)

    str_p1 = " - ".join([f"{n:02d}" for n in p1_balotas])
    str_p2 = " - ".join([f"{n:02d}" for n in p2_balotas])

    # 4. Formatear Frecuencias Balotas UNIFICADO (Top 20)
    lineas_frecuencia = []
    for num, frec in frec_estandar_balotas:
        etiqueta = ""
        if num in num_ultimo_norm or num in num_ultimo_rev:
            etiqueta = " 🔴 [Último]"
        elif num in num_penult_norm or num in num_penult_rev:
            etiqueta = " 🟠 [Penúlt.]"
        elif num in num_antep_norm or num in num_antep_rev:
            etiqueta = " 🟡 [Antep.]"
        lineas_frecuencia.append(f"Balota {num:02d}: {frec} veces{etiqueta}")

    # 5. Formatear Superbalotas UNIFICADO (Top 10)
    lineas_superbalotas = []
    for sb, frec in frec_estandar_sb:
        etiqueta = ""
        if sb in sb_ultimo_norm or sb in sb_ultimo_rev:
            etiqueta = " 🔴 [Último]"
        elif sb in sb_penult_norm or sb in sb_penult_rev:
            etiqueta = " 🟠 [Penúlt.]"
        elif sb in sb_antep_norm or sb in sb_antep_rev:
            etiqueta = " 🟡 [Antep.]"
        lineas_superbalotas.append(f"Superbalota {sb:02d}: {frec} veces{etiqueta}")

    # 6. Formatear Historial Balotas Tradicional
    lineas_historial = []
    for s in sorteos[:20]:
        fecha, n1, n2, n3, n4, n5, sb = s
        lineas_historial.append(f"<b>{fecha}</b>: {n1:02d}-{n2:02d}-{n3:02d}-{n4:02d}-{n5:02d} (SB: {sb:02d})")

    # 7. Formatear Historial Balotas Revancha
    lineas_historial_rev = []
    for s in sorteos_revancha[:20]:
        fecha, r1, r2, r3, r4, r5, sbr = s
        lineas_historial_rev.append(f"<b>{fecha}</b>: {r1:02d}-{r2:02d}-{r3:02d}-{r4:02d}-{r5:02d} (SB: {sbr:02d})")

    # Mensaje consolidado para Telegram
    mensaje = f"📅 <b>PERIODO HISTÓRICO: {fecha_mas_antigua} al {fecha_mas_reciente} ({total_sorteos} sorteos)</b>\n\n"
    mensaje += f"🎯 <b>PRONÓSTICO 1 (Frecuencia Histórica 1 Año)</b>\n"
    mensaje += f"• Números: <b>{str_p1}</b>\n"
    mensaje += f"• Superbalota: <b>{p1_sb:02d}</b>\n\n"
    mensaje += f"⚡ <b>PRONÓSTICO 2 (Ponderado 1 Año - Premium Últimos 2 Meses)</b>\n"
    mensaje += f"• Números: <b>{str_p2}</b>\n"
    mensaje += f"• Superbalota: <b>{p2_sb:02d}</b>\n\n"
    
    mensaje += "<b>📊 FRECUENCIA BALOTAS (TOP 20 - UNIFICADO)</b>\n" + ("\n".join(lineas_frecuencia[:20]) if lineas_frecuencia else "Sin datos") + "\n\n"
    mensaje += "<b>🔴 SUPERBALOTAS (TOP 10 - UNIFICADO)</b>\n" + ("\n".join(lineas_superbalotas[:10]) if lineas_superbalotas else "Sin datos") + "\n\n"

    mensaje += "<b>📅 SORTEOS EN EL PERIODO (BALOTO)</b>\n" + ("\n".join(lineas_historial) if lineas_historial else "Ninguno")
    
    if lineas_historial_rev:
        mensaje += "\n\n<b>🔄 SORTEOS EN EL PERIODO (REVANCHA)</b>\n" + "\n".join(lineas_historial_rev)

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"})
        if res.status_code == 200:
            print("✅ Reporte con ponderado real enviado correctamente a Telegram.")
        else:
            print(f"⚠️ Error enviando a Telegram: {res.text}")
    else:
        print("⚠️ Faltan credenciales de Telegram en las variables de entorno.")

if __name__ == '__main__':
    generar_y_enviar_reporte()
