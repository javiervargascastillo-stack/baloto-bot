import os
import sys
import sqlite3
import requests
from collections import Counter

# Configuración de codificación UTF-8 para consola de Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Lee las credenciales de las variables de entorno (GitHub Actions) o valores por defecto
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8879192174:AAEXx_k8F9on9arUsBK1qAf4EVhRWjVVU3o')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '8868366458')

def generar_y_enviar_reporte():
    conn = sqlite3.connect('baloto.db')
    cursor = conn.cursor()

    # 1. Historial ordenado por fecha DESCENDENTE
    cursor.execute('''
        SELECT fecha, b1, b2, b3, b4, b5, sb, r1, r2, r3, r4, r5, rsb 
        FROM sorteos 
        ORDER BY fecha DESC
    ''')
    sorteos = cursor.fetchall()
    conn.close()

    if not sorteos:
        print("❌ No hay sorteos en la base de datos.")
        sys.exit(1)

    total_sorteos = len(sorteos)
    fecha_mas_reciente = sorteos[0][0]
    fecha_mas_antigua = sorteos[-1][0]

    # Balotas principales de los últimos 3 sorteos (Baloto + Revancha)
    num_ultimo = set(sorteos[0][1:6] + sorteos[0][7:12]) if len(sorteos) > 0 else set()
    num_penultimo = set(sorteos[1][1:6] + sorteos[1][7:12]) if len(sorteos) > 1 else set()
    num_antepenultimo = set(sorteos[2][1:6] + sorteos[2][7:12]) if len(sorteos) > 2 else set()

    # Superbalotas de los últimos 3 sorteos (Baloto + Revancha)
    sb_ultimo = {sorteos[0][6], sorteos[0][12]} if len(sorteos) > 0 else set()
    sb_penultimo = {sorteos[1][6], sorteos[1][12]} if len(sorteos) > 1 else set()
    sb_antepenultimo = {sorteos[2][6], sorteos[2][12]} if len(sorteos) > 2 else set()

    # Conjuntos consolidados de los últimos 3 sorteos para exclusión
    recientes_balotas = num_ultimo | num_penultimo | num_antepenultimo
    recientes_superbalotas = sb_ultimo | sb_penultimo | sb_antepenultimo

    # 2. Conteo de frecuencias
    conteo_balotas = Counter()
    conteo_superbalotas = Counter()

    for s in sorteos:
        conteo_balotas.update(s[1:6])
        conteo_balotas.update(s[7:12])
        conteo_superbalotas.update([s[6], s[12]])

    frecuencia_balotas = conteo_balotas.most_common()
    frecuencia_superbalotas = conteo_superbalotas.most_common()

    top_6_balotas = set([num for num, _ in frecuencia_balotas[:6]])
    top_6_superbalotas = set([sb for sb, _ in frecuencia_superbalotas[:6]])

    # 3. Filtrar pronóstico: Excluir números/superbalotas presentes en los últimos 3 sorteos
    balotas_filtradas = [num for num, _ in frecuencia_balotas if num not in recientes_balotas]
    superbalotas_filtradas = [sb for sb, _ in frecuencia_superbalotas if sb not in recientes_superbalotas]

    pronostico_balotas = sorted(balotas_filtradas[:5])
    pronostico_sb = superbalotas_filtradas[0] if superbalotas_filtradas else frecuencia_superbalotas[0][0]
    str_pronostico = " - ".join([f"{n:02d}" for n in pronostico_balotas])

    # 4. Formatear FRECUENCIA CONSOLIDADA BALOTAS
    lineas_frecuencia = []
    for num, frec in frecuencia_balotas:
        etiqueta_recencia = ""
        if num in top_6_balotas:
            if num in num_ultimo:
                etiqueta_recencia = " 🔴 [Último]"
            elif num in num_penultimo:
                etiqueta_recencia = " 🟠 [Penúltimo]"
            elif num in num_antepenultimo:
                etiqueta_recencia = " 🟡 [Antepenúltimo]"

        lineas_frecuencia.append(f"Balota {num:02d}: {frec} apariciones{etiqueta_recencia}")

    # 5. Formatear FRECUENCIA CONSOLIDADA SUPERBALOTAS
    lineas_superbalotas = []
    for sb, frec in frecuencia_superbalotas:
        etiqueta_recencia = ""
        if sb in top_6_superbalotas:
            if sb in sb_ultimo:
                etiqueta_recencia = " 🔴 [Último]"
            elif sb in sb_penultimo:
                etiqueta_recencia = " 🟠 [Penúltimo]"
            elif sb in sb_antepenultimo:
                etiqueta_recencia = " 🟡 [Antepenúltimo]"

        lineas_superbalotas.append(f"Superbalota {sb:02d}: {frec} apariciones{etiqueta_recencia}")

    # 6. Formatear HISTORIAL
    lineas_historial = []
    for s in sorteos:
        fecha, b1, b2, b3, b4, b5, sb, r1, r2, r3, r4, r5, rsb = s
        lineas_historial.append(
            f"<b>{fecha}</b>\n"
            f"• Baloto: {b1:02d}-{b2:02d}-{b3:02d}-{b4:02d}-{b5:02d} (SB: {sb:02d})\n"
            f"• Revancha: {r1:02d}-{r2:02d}-{r3:02d}-{r4:02d}-{r5:02d} (SB: {rsb:02d})"
        )

    # Construcción del mensaje consolidado
    mensaje = f"📅 <b>PERIODO HISTÓRICO: {fecha_mas_antigua} al {fecha_mas_reciente} ({total_sorteos} sorteos)</b>\n\n"
    
    mensaje += f"🎯 <b>PRONÓSTICO SUGERIDO (Excluyendo Recientes)</b>\n"
    mensaje += f"• Números: <b>{str_pronostico}</b>\n"
    mensaje += f"• Superbalota: <b>{pronostico_sb:02d}</b>\n\n"

    mensaje += "<b>📊 FRECUENCIA CONSOLIDADA (Mayor a Menor)</b>\n\n"
    mensaje += "\n".join(lineas_frecuencia[:12]) + "\n\n"

    mensaje += "<b>🔴 SUPERBALOTAS (Mayor a Menor)</b>\n\n"
    mensaje += "\n".join(lineas_superbalotas[:10]) + "\n\n"

    mensaje += "<b>📅 HISTORIAL DE SORTEOS DEL ÚLTIMO AÑO (Descendente)</b>\n\n"
    mensaje += "\n\n".join(lineas_historial[:5])

    # Envío a Telegram
    if TELEGRAM_TOKEN and TELEGRAM_TOKEN != "8879192174:AAEXx_k8F9on9arUsBK1qAf4EVhRWjVVU3o":
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensaje,
            "parse_mode": "HTML"
        }
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            print("✅ Reporte enviado correctamente a Telegram.")
        else:
            print(f"⚠️ Error al enviar a Telegram: {res.text}")
            sys.exit(1)
    else:
        print("⚠️ No se ha configurado un TELEGRAM_TOKEN válido.")
        sys.exit(1)

if __name__ == '__main__':
    generar_y_enviar_reporte()
