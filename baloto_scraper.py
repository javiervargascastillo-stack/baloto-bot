import requests
from bs4 import BeautifulSoup

def obtener_ultimo_sorteo():
    url = "https://baloto.com/resultados"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        tabla = soup.find("table")
        if not tabla:
            return None
        filas = tabla.find_all("tr")[1:]
        for fila in filas:
            cols = [c.text.strip() for c in fila.find_all("td")]
            if len(cols) >= 2:
                fecha_str, resultado_str = cols[0], cols[1]
                meses = {"Enero":"01","Febrero":"02","Marzo":"03","Abril":"04","Mayo":"05","Junio":"06","Julio":"07","Agosto":"08","Septiembre":"09","Octubre":"10","Noviembre":"11","Diciembre":"12"}
                partes = fecha_str.split(" de ")
                if len(partes) == 3:
                    dia, mes, anio = partes[0].zfill(2), meses.get(partes[1].capitalize(), "01"), partes[2]
                    fecha_iso = f"{anio}-{mes}-{dia}"
                    partes_nums = [int(n.strip()) for n in resultado_str.split("-")]
                    if len(partes_nums) == 6:
                        return {"fecha": fecha_iso, "numeros": partes_nums[:5], "superbalota": partes_nums[5]}
    except Exception as e:
        print(f"⚠️ Error en scraping: {e}")
    return None
