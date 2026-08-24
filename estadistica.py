import pandas as pd
import numpy as np
import sqlite3

def generar_reporte_y_pronostico(db_name='baloto.db'):
    conn = sqlite3.connect(db_name)
    df = pd.read_sql_query('SELECT * FROM sorteos', conn)
    conn.close()
    if df.empty:
        return '📊 *BALOTO PRONÓSTICO* 📊\n\nNo hay suficientes datos almacenados todavía.'
    todos_numeros = df[['n1', 'n2', 'n3', 'n4', 'n5']].values.flatten()
    freq = pd.Series(todos_numeros).value_counts()
    mas_frecuentes = freq.head(5).index.tolist()
    sb_freq = df['superbalota'].value_counts()
    sb = sb_freq.index[0] if not sb_freq.empty else 1
    return f'📊 *BALOTO PRONÓSTICO* 📊\n\n🔥 *Números frecuentes:* {mas_frecuentes}\n⭐ *Superbalota sugerida:* {sb}'
