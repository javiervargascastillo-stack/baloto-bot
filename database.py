import sqlite3

DB_NAME = 'baloto.db'

def init_db(DB_NAME='baloto.db'):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS sorteos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT UNIQUE,
        n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
        superbalota INTEGER
    )""")
    conn.commit()
    conn.close()

def limpiar_datos_antiguos(DB_NAME='baloto.db'):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sorteos WHERE fecha < date('now', '-1 year')")
    eliminados = cursor.rowcount
    conn.commit()
    conn.close()
    if eliminados > 0:
        print(f"🧹 Depuración: Se eliminaron {eliminados} registro(s) mayores a 1 año.")

def guardar_sorteo(*args, **kwargs):
    """
    Guarda o actualiza el sorteo completo en baloto.db aplanando 
    automáticamente los argumentos recibidos.
    """
    conn = sqlite3.connect('baloto.db')
    cursor = conn.cursor()

    elementos = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            elementos.extend(arg)
        elif isinstance(arg, dict):
            fecha = arg.get('fecha')
            b = arg.get('numeros', []) + [arg.get('superbalota')]
            r = arg.get('revancha_numeros', []) + [arg.get('revancha_superbalota')]
            elementos = [fecha] + b + r
            break
        else:
            elementos.append(arg)

    if len(elementos) == 13:
        sql = """
            INSERT OR REPLACE INTO sorteos 
            (fecha, b1, b2, b3, b4, b5, sb, r1, r2, r3, r4, r5, rsb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(sql, tuple(elementos))
        conn.commit()
        print(f"✅ Sorteo del {elementos[0]} guardado exitosamente con Baloto y Revancha.")
    else:
        print(f"⚠️ Se recibieron {len(elementos)} elementos en lugar de 13. Estructura: {elementos}")

    conn.close()
    limpiar_datos_antiguos(DB_NAME)
