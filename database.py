import sqlite3

def init_db(db_name='baloto.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS sorteos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT UNIQUE,
        n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
        superbalota INTEGER
    )""")
    conn.commit()
    conn.close()

def limpiar_datos_antiguos(db_name='baloto.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sorteos WHERE fecha < date('now', '-1 year')")
    eliminados = cursor.rowcount
    conn.commit()
    conn.close()
    if eliminados > 0:
        print(f"🧹 Depuración: Se eliminaron {eliminados} registro(s) mayores a 1 año.")

def guardar_sorteo(fecha, numeros, superbalota, db_name='baloto.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    numeros_ordenados = sorted(numeros)
    try:
        cursor.execute("""INSERT INTO sorteos (fecha, n1, n2, n3, n4, n5, superbalota)
                          VALUES (?, ?, ?, ?, ?, ?, ?)""", (fecha, *numeros_ordenados, superbalota))
        conn.commit()
        print(f"✅ Sorteo del {fecha} guardado exitosamente.")
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
    limpiar_datos_antiguos(db_name)
