import os
import requests
from database import init_db, guardar_sorteo
from baloto_scraper import obtener_ultimo_sorteo
from estadistica import generar_reporte_y_pronostico

def enviar_telegram(mensaje):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        print('❌ Error: Falta configurar TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.')
        return
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    res = requests.post(url, json={'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'Markdown'})
    if res.status_code == 200:
        print('✅ ¡Mensaje enviado con éxito a Telegram!')
    else:
        print(f'❌ Error enviando a Telegram: {res.text}')

def main():
    init_db()
    sorteo = obtener_ultimo_sorteo()
    if sorteo:
        guardar_sorteo(sorteo['fecha'], sorteo['numeros'], sorteo['superbalota'])
    reporte = generar_reporte_y_pronostico()
    print(reporte)
    enviar_telegram(reporte)

if __name__ == '__main__':
    main()
