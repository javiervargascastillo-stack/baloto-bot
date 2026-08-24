import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from database import init_db, guardar_sorteo

meses = {"Enero":"01","Febrero":"02","Marzo":"03","Abril":"04","Mayo":"05","Junio":"06","Julio":"07","Agosto":"08","Septiembre":"09","Octubre":"10","Noviembre":"11","Diciembre":"12"}

def poblar_ultimo_ano():
    init_db()
    hace_un_ano = datetime.now() - timedelta(days=365)
    print(f"📥 Descargando historial de sorteos desde {hace_un_ano.strftime('%Y-%m-%d')}...")
    headers = {"User-Agent": "Mozilla/5.0"}

    for page in range(1, 16):
        url = f"https://baloto.com/filtro-historico-de-resultados.php?page={page}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                break
            soup = BeautifulSoup(res.text, "html.parser")
            tabla = soup.find("table")
            if not tabla:
                break
            filas = tabla.find_all("tr")[1:]
            for fila in filas:
                cols = [c.text.strip() for c in fila.find_all("td")]
                if len(cols) >= 2:
                    partes = cols[0].split(" de ")
                    if len(partes) == 3:
                        dia, mes, anio = partes[0].zfill(2), meses.get(partes[1].capitalize(), "01"), partes[2]
                        fecha_dt = datetime.strptime(f"{anio}-{mes}-{dia}", "%Y-%m-%d")
                        if fecha_dt < hace_un_ano:
                            print("🏁 Se alcanzó el límite de 1 año de antigüedad.")
                            return
                        partes_nums = [int(n.strip()) for n in cols[1].split("-")]
                        if len(partes_nums) == 6:
                            guardar_sorteo(
                                fecha=fecha_dt.strftime("%Y-%m-%d"),
                                numeros=partes_nums[:5],
                                superbalota=partes_nums[5]
                            )
        except Exception as e:
            print(f"Error procesando página {page}: {e}")
            break

if __name__ == "__main__":
    poblar_ultimo_ano()
