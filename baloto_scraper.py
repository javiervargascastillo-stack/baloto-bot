import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Mapeo de meses en español para conversión a YYYY-MM-DD
MESES = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
}

def normalizar_fecha(texto_fecha):
    """Convierte cadenas como '26 de Agosto de 2026' a '2026-08-26'."""
    try:
        texto_clean = texto_fecha.lower().strip()
        # Buscar patrón: día de mes de año
        match = re.search(r'(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})', texto_clean)
        if match:
            dia, mes_nombre, anio = match.groups()
            mes = MESES.get(mes_nombre, '01')
            return f"{anio}-{mes}-{int(dia):02d}"
    except Exception as e:
        print(f"⚠️ Error al formatear fecha '{texto_fecha}': {e}")
    
    return datetime.now().strftime("%Y-%m-%d")

def obtener_ultimo_sorteo():
    url = "https://baloto.com/resultados"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Error HTTP {response.status_code} al acceder a {url}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Extraer bloques de resultados (Baloto y Revancha)
        # La web usa contenedores o filas con información de sorteo
        filas = soup.find_all(['div', 'tr'], class_=re.compile(r'(sorteo|resultado|card)', re.I))
        
        # Extracción general de números en la página usando expresiones regulares si las tablas cambian
        texto_pagina = soup.get_text()
        
        # Buscar fechas tipo "26 de Agosto de 2026"
        fechas_encontradas = re.findall(r'\d{1,2}\s+de\s+[A-Za-z]+\s+de\s+\d{4}', texto_pagina)
        fecha_raw = fechas_encontradas[0] if fechas_encontradas else None

        if not fecha_raw:
            print("⚠️ No se pudo extraer la fecha del último sorteo desde el HTML.")
            return None

        fecha_formateada = normalizar_fecha(fecha_raw)

        # Buscar todos los bloques de 6 números (5 balotas + 1 superbalota)
        # Patrón típico: 5 números entre 1-43 y 1 número entre 1-16
        bloques_numeros = []
        
        # Buscar por elementos con clases numéricas o estructuras típicas
        bolas = soup.find_all(['span', 'div', 'p'], class_=re.compile(r'(ball|balota|number|num)', re.I))
        numeros_extraidos = [int(b.get_text().strip()) for b in bolas if b.get_text().strip().isdigit()]

        # Si el selector específico no encuentra nada, buscar en listas o spans generales
        if len(numeros_extraidos) < 12:
            # Fallback: Extraer de etiquetas de texto aisladas
            etiquetas = soup.find_all(['span', 'div', 'td'])
            numeros_extraidos = []
            for eq in etiquetas:
                txt = eq.get_text().strip()
                if txt.isdigit() and 1 <= int(txt) <= 43:
                    numeros_extraidos.append(int(txt))

        if len(numeros_extraidos) >= 12:
            baloto_nums = numeros_extraidos[0:5]
            baloto_sb = numeros_extraidos[5]
            
            revancha_nums = numeros_extraidos[6:11]
            revancha_sb = numeros_extraidos[11]

            return {
                'fecha': fecha_formateada,
                'numeros': baloto_nums,
                'superbalota': baloto_sb,
                'revancha_numeros': revancha_nums,
                'revancha_superbalota': revancha_sb
            }
        else:
            print(f"⚠️ Se encontraron {len(numeros_extraidos)} números, se requerían al menos 12.")
            return None

    except Exception as e:
        print(f"❌ Excepción en baloto_scraper: {e}")
        return None

if __name__ == '__main__':
    print(obtener_ultimo_sorteo())