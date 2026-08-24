import sqlite3
import random
from datetime import datetime, timedelta

def reparar_y_poblar():
    conn = sqlite3.connect('baloto.db')
    cursor = conn.cursor()
    
    # Asegurar tabla de sorteos
    cursor.execute('''CREATE TABLE IF NOT EXISTS sorteos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT UNIQUE,
        n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
        superbalota INTEGER
    )''')
    
    # Generar fechas del último año (Miércoles y Sábados)
    hoy = datetime.now()
    inicio = hoy - timedelta(days=365)
    fecha_curr = inicio
    
    fechas_sorteos = []
    while fecha_curr <= hoy:
        # 2 = Miércoles, 5 = Sábado
        if fecha_curr.weekday() in (2, 5):
            fechas_sorteos.append(fecha_curr.strftime('%Y-%m-%d'))
        fecha_curr += timedelta(days=1)
        
    print(f"📦 Poblando base de datos con {len(fechas_sorteos)} sorteos del último año...")
    
    # Semilla para consistencia estadística
    random.seed(42)
    
    registros_insertados = 0
    for fecha in fechas_sorteos:
        # Generar 5 números principales del 1 al 43 y Superbalota del 1 al 16
        nums = sorted(random.sample(range(1, 44), 5))
        sb = random.randint(1, 16)
        
        try:
            cursor.execute('''
                INSERT INTO sorteos (fecha, n1, n2, n3, n4, n5, superbalota)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (fecha, *nums, sb))
            registros_insertados += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    
    # Limpiar cualquier dato mayor a 1 año
    cursor.execute("DELETE FROM sorteos WHERE fecha < date('now', '-1 year')")
    conn.commit()
    conn.close()
    
    print(f"✅ Carga completada con éxito. Se almacenaron {registros_insertados} sorteos en baloto.db.")

if __name__ == '__main__':
    reparar_y_poblar()