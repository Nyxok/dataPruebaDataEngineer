import sqlite3
import csv
from pathlib import Path


# ============================================================
# PRUEBA TÉCNICA - DATA ENGINEER
# PIPELINE DE PROCESAMIENTO DE ARCHIVOS CSV
# ============================================================
#
# Objetivo:
# Procesar los archivos CSV de forma secuencial, almacenar sus
# registros en una base de datos SQLite y mantener estadísticas
# incrementales sobre la columna "price".
#
# El pipeline debe:
# - Procesar los archivos principales uno por uno.
# - Evitar cargar todos los archivos simultáneamente en memoria.
# - Almacenar los registros en una base de datos.
# - Mantener estadísticas incrementales de los datos cargados.
# - Procesar validation.csv utilizando el mismo flujo.
# - Validar los resultados mediante consultas directas a la BD.
#
# Tecnologías:
# - Python 3
# - SQLite
# - csv
# - pathlib
#
# SQLite se utiliza porque está integrado con Python, no requiere
# un servidor adicional y es suficiente para el volumen de datos
# de esta prueba.
# ============================================================


# ============================================================
# 1. CONFIGURACIÓN DE RUTAS
# ============================================================
#
# Las rutas se construyen a partir de la ubicación del proyecto,
# evitando depender de rutas absolutas específicas del equipo.
#
# Estructura esperada:
#
# dataPruebaDataEngineer/
# ├── data/
# ├── database/
# ├── src/
# └── README.md
#

try:
    BASE_DIR = Path(__file__).resolve().parent.parent

except NameError:
    # Permite ejecutar el código en entornos donde __file__
    # no esté disponible, como un notebook.
    BASE_DIR = Path.cwd().parent


DATABASE_PATH = BASE_DIR / "database" / "pipeline.db"
DATA_PATH = BASE_DIR / "data"

# La carpeta se crea automáticamente si no existe.
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. CONEXIÓN A LA BASE DE DATOS
# ============================================================
#
# Todos los archivos CSV se almacenan en la misma base de datos.
# SQLite permite trabajar directamente desde Python sin necesidad
# de administrar un servidor de base de datos.
#

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

print("Conexión a la base de datos exitosa")
print(f"Base de datos: {DATABASE_PATH}")
print(f"Carpeta de datos: {DATA_PATH}")


# ============================================================
# 3. CREACIÓN DE LAS TABLAS
# ============================================================
#
# Se utilizan tres tablas con responsabilidades diferentes:
#
# transactions:
#     Almacena los registros válidos de los archivos CSV.
#
# statistics:
#     Mantiene las estadísticas acumuladas de forma incremental.
#
# rejected_rows:
#     Conserva las filas que no cumplen las validaciones y
#     registra el motivo del rechazo.
#
# Las tablas se reinician en cada ejecución para comenzar la prueba
# desde cero y evitar duplicar información.
#


cursor.execute("DROP TABLE IF EXISTS transactions")
cursor.execute("DROP TABLE IF EXISTS statistics")
cursor.execute("DROP TABLE IF EXISTS rejected_rows")


# ------------------------------------------------------------
# 3.1 TABLA DE TRANSACCIONES
# ------------------------------------------------------------
#
# Se agrega source_file para conservar la trazabilidad del archivo
# del cual proviene cada registro.
#

cursor.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        price REAL,
        user_id INTEGER,
        source_file TEXT NOT NULL
    )
""")


# ------------------------------------------------------------
# 3.2 TABLA DE ESTADÍSTICAS
# ------------------------------------------------------------
#
# Se mantiene un único registro que funciona como acumulador.
#
# Para evitar recorrer nuevamente transactions, se almacenan:
#
# - total_rows
# - valid_price_count
# - price_sum
# - price_min
# - price_max
#
# El promedio se obtiene mediante:
#
#     promedio = price_sum / valid_price_count
#
# De esta forma el promedio no necesita recalcularse sobre todos
# los registros almacenados.
#

cursor.execute("""
    CREATE TABLE statistics (
        id INTEGER PRIMARY KEY,
        total_rows INTEGER NOT NULL DEFAULT 0,
        valid_price_count INTEGER NOT NULL DEFAULT 0,
        price_sum REAL NOT NULL DEFAULT 0,
        price_min REAL,
        price_max REAL
    )
""")


# ------------------------------------------------------------
# 3.3 TABLA DE FILAS RECHAZADAS
# ------------------------------------------------------------
#
# Las filas inválidas no detienen el procesamiento completo.
# Se conservan para mantener trazabilidad y facilitar su revisión.
#

cursor.execute("""
    CREATE TABLE rejected_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT NOT NULL,
        row_number INTEGER NOT NULL,
        raw_row TEXT,
        reason TEXT
    )
""")


# Registro inicial del acumulador de estadísticas.

cursor.execute("""
    INSERT INTO statistics (id)
    VALUES (1)
""")

connection.commit()


# ============================================================
# 4. ACTUALIZACIÓN INCREMENTAL DE ESTADÍSTICAS
# ============================================================
#
# Esta función actualiza las estadísticas utilizando únicamente
# el nuevo registro procesado.
#
# No se vuelve a recorrer transactions ni se ejecutan funciones
# como AVG(price) sobre todo el histórico después de cada fila.
#
# Para el promedio se mantiene la suma y la cantidad de precios
# válidos:
#
#     nueva_suma = suma_anterior + nuevo_precio
#     nuevo_conteo = conteo_anterior + 1
#     promedio = nueva_suma / nuevo_conteo
#
# Esto permite mantener el estado acumulado de forma incremental.
#


def update_statistics(price):
    """
    Actualiza el acumulador de estadísticas con el precio
    de la fila actual.
    """

    cursor.execute("""
        SELECT
            total_rows,
            valid_price_count,
            price_sum,
            price_min,
            price_max
        FROM statistics
        WHERE id = 1
    """)

    stats = cursor.fetchone()

    total_rows = stats[0] + 1
    valid_price_count = stats[1]
    price_sum = stats[2]
    price_min = stats[3]
    price_max = stats[4]


    # Los precios NULL no participan en promedio, mínimo ni máximo.

    if price is not None:

        valid_price_count += 1
        price_sum += price

        if price_min is None or price < price_min:
            price_min = price

        if price_max is None or price > price_max:
            price_max = price


    cursor.execute("""
        UPDATE statistics
        SET
            total_rows = ?,
            valid_price_count = ?,
            price_sum = ?,
            price_min = ?,
            price_max = ?
        WHERE id = 1
    """, (
        total_rows,
        valid_price_count,
        price_sum,
        price_min,
        price_max
    ))


# ============================================================
# 5. OBTENCIÓN DE ESTADÍSTICAS INCREMENTALES
# ============================================================
#
# El promedio se calcula a partir de los valores acumulados.
# No es necesario consultar nuevamente transactions.
#


def get_statistics():
    """
    Obtiene las estadísticas acumuladas actualmente.
    """

    cursor.execute("""
        SELECT
            total_rows,
            valid_price_count,
            price_sum,
            price_min,
            price_max
        FROM statistics
        WHERE id = 1
    """)

    stats = cursor.fetchone()

    total_rows = stats[0]
    valid_price_count = stats[1]
    price_sum = stats[2]
    price_min = stats[3]
    price_max = stats[4]

    if valid_price_count > 0:
        average_price = price_sum / valid_price_count
    else:
        average_price = None

    return {
        "total_rows": total_rows,
        "valid_price_count": valid_price_count,
        "average_price": average_price,
        "price_min": price_min,
        "price_max": price_max
    }


def show_statistics():
    """Muestra las estadísticas incrementales actuales."""

    stats = get_statistics()

    if stats["average_price"] is None:
        average_text = "sin precios válidos aún"
    else:
        average_text = f"{stats['average_price']:.10f}"

    print(f"  Total filas: {stats['total_rows']}")
    print(f"  Precios válidos: {stats['valid_price_count']}")
    print(f"  Promedio: {average_text}")
    print(f"  Mínimo: {stats['price_min']}")
    print(f"  Máximo: {stats['price_max']}")


# ============================================================
# 6. CONSULTA DIRECTA A LA BASE DE DATOS
# ============================================================
#
# Esta función se utiliza únicamente para validar los resultados
# del cálculo incremental.
#
# Aquí sí se utilizan COUNT, AVG, MIN y MAX directamente sobre
# transactions.
#
# La consulta no forma parte de la actualización incremental;
# sirve como mecanismo independiente de comprobación.
#


def query_database():
    """
    Calcula las estadísticas directamente sobre transactions.
    """

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(price),
            AVG(price),
            MIN(price),
            MAX(price)
        FROM transactions
    """)

    result = cursor.fetchone()

    return {
        "total_rows": result[0],
        "valid_price_count": result[1],
        "average_price": result[2],
        "price_min": result[3],
        "price_max": result[4]
    }


def show_database_query(result):
    """Muestra el resultado de la consulta directa a SQLite."""

    print(f"  Total filas: {result['total_rows']}")
    print(f"  Precios válidos: {result['valid_price_count']}")
    print(f"  Promedio: {result['average_price']:.10f}")
    print(f"  Mínimo: {result['price_min']}")
    print(f"  Máximo: {result['price_max']}")


# ============================================================
# 7. COMPARACIÓN DE RESULTADOS
# ============================================================
#
# Se comparan:
#
# 1. Las estadísticas mantenidas incrementalmente.
# 2. Las estadísticas calculadas directamente mediante SQL.
#
# Si coinciden, se valida que el cálculo incremental está
# produciendo los mismos resultados que una agregación sobre
# los datos almacenados.
#


def compare_statistics(stats, database_result):
    """
    Compara las estadísticas incrementales contra los resultados
    calculados directamente mediante SQL.
    """

    rows = [
        ("Total filas", stats["total_rows"], database_result["total_rows"]),
        (
            "Precios válidos",
            stats["valid_price_count"],
            database_result["valid_price_count"]
        ),
        (
            "Promedio",
            stats["average_price"],
            database_result["average_price"]
        ),
        ("Mínimo", stats["price_min"], database_result["price_min"]),
        ("Máximo", stats["price_max"], database_result["price_max"])
    ]

    print(
        f"  {'Métrica':<18}"
        f"{'Incremental':>18}"
        f"{'SQL':>18}"
        f"{'Diferencia':>14}"
    )

    print("  " + "-" * 68)

    matches = True

    for name, incremental_value, database_value in rows:

        difference = abs(
            float(incremental_value) - float(database_value)
        )

        # Se utiliza una pequeña tolerancia para diferencias
        # de precisión propias de los valores float.

        if difference > 1e-9:
            matches = False

        print(
            f"  {name:<18}"
            f"{float(incremental_value):>18.10f}"
            f"{float(database_value):>18.10f}"
            f"{difference:>14.2e}"
        )

    print("  " + "-" * 68)

    if matches:
        print("  RESULTADO: los valores coinciden")
    else:
        print("  RESULTADO: hay diferencias")

    return matches


# ============================================================
# 8. VALIDACIÓN Y TRANSFORMACIÓN DE LAS FILAS
# ============================================================
#
# Antes de almacenar cada registro se realizan validaciones básicas.
#
# Reglas:
#
# timestamp:
#     Es obligatorio y no puede estar vacío.
#
# price:
#     Puede estar vacío. En ese caso se almacena como NULL.
#     Si tiene valor, debe ser numérico y no negativo.
#
# user_id:
#     Puede estar vacío.
#     Si tiene valor, debe ser un número entero.
#
# Las filas que no cumplen las reglas se almacenan en
# rejected_rows junto con el motivo del rechazo.
#
# Un registro con price NULL sigue siendo válido y se almacena
# en transactions; simplemente no participa en las estadísticas
# de precio.
#


def parse_row(row):
    """
    Valida y transforma una fila proveniente del CSV.

    Retorna:
        (registro, None) si es válida.
        (None, motivo) si debe ser rechazada.
    """

    timestamp = (row.get("timestamp") or "").strip()

    if timestamp == "":
        return None, "timestamp vacío"


    raw_price = (row.get("price") or "").strip()

    if raw_price == "":
        price = None

    else:
        try:
            price = float(raw_price)

        except ValueError:
            return None, f"price no numérico: {raw_price}"

        if price < 0:
            return None, f"price negativo: {price}"


    raw_user_id = (row.get("user_id") or "").strip()

    if raw_user_id == "":
        user_id = None

    else:
        try:
            user_id = int(raw_user_id)

        except ValueError:
            return None, f"user_id no entero: {raw_user_id}"


    return (timestamp, price, user_id), None


# ============================================================
# 9. PROCESAMIENTO DE UN ARCHIVO CSV
# ============================================================
#
# Cada archivo se procesa de forma secuencial y fila por fila.
#
# Al procesar una fila a la vez, no es necesario cargar el archivo
# completo en memoria y tampoco se mantienen los cinco CSV abiertos
# simultáneamente.



def process_file(file_path):
    """
    Procesa un archivo CSV de forma secuencial.
    """

    print(f"\nProcesando archivo: {file_path.name}")

    row_count = 0
    rejected_count = 0


    with open(
        file_path,
        mode="r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)


        for row_number, row in enumerate(reader, start=1):

            # Primero se valida y transforma la fila.

            record, reason = parse_row(row)


            # Si no cumple las validaciones se registra en cuarentena
            # y se continúa con la siguiente fila.

            if reason is not None:

                cursor.execute("""
                    INSERT INTO rejected_rows (
                        source_file,
                        row_number,
                        raw_row,
                        reason
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    file_path.name,
                    row_number,
                    str(row),
                    reason
                ))

                rejected_count += 1
                continue


            # Los registros válidos se almacenan en transactions.

            timestamp, price, user_id = record

            cursor.execute("""
                INSERT INTO transactions (
                    timestamp,
                    price,
                    user_id,
                    source_file
                )
                VALUES (?, ?, ?, ?)
            """, (
                timestamp,
                price,
                user_id,
                file_path.name
            ))


            # Inmediatamente después de cargar la fila se actualiza
            # el acumulador de estadísticas.

            update_statistics(price)

            row_count += 1


    # Se confirma la transacción después de procesar el archivo.

    connection.commit()


    print(
        f"Filas cargadas: {row_count} | "
        f"Filas rechazadas: {rejected_count}"
    )

    print("Estadísticas acumuladas:")
    show_statistics()


# ============================================================
# 10. PROCESAMIENTO DE LOS ARCHIVOS PRINCIPALES
# ============================================================
#
# El conjunto principal está compuesto por:
#
#     2012-1.csv
#     2012-2.csv
#     2012-3.csv
#     2012-4.csv
#     2012-5.csv
#
# Se utiliza el patrón 2012-*.csv para excluir automáticamente
# validation.csv.
#
# Los archivos se ordenan numéricamente para respetar el orden
# temporal indicado en el enunciado.
#


csv_files = sorted(
    DATA_PATH.glob("2012-*.csv"),
    key=lambda path: int(path.stem.split("-")[1])
)


print("\nArchivos principales encontrados:")

for file in csv_files:
    print(f"- {file.name}")


# Cada archivo termina de procesarse antes de iniciar el siguiente.

for file in csv_files:
    process_file(file)


# ============================================================
# 11. RESULTADO DESPUÉS DE LOS ARCHIVOS PRINCIPALES
# ============================================================
#
# Después de procesar los cinco archivos se muestran las
# estadísticas acumuladas y se validan mediante una consulta SQL.
#


print("\n==========================================")
print("RESULTADO ANTES DE VALIDATION")
print("==========================================")


statistics_before = get_statistics()

show_statistics()


print("\n==========================================")
print("CONSULTA DIRECTA A LA BASE DE DATOS")
print("==========================================")


database_before = query_database()

show_database_query(database_before)


print("\nComprobación incremental vs SQL:")

compare_statistics(
    statistics_before,
    database_before
)


# ============================================================
# 12. PROCESAMIENTO DE VALIDATION.CSV
# ============================================================
#
# validation.csv se procesa utilizando exactamente el mismo
# process_file() utilizado para los archivos principales.
#
# Esto garantiza que los nuevos registros pasen por las mismas
# validaciones, almacenamiento y actualización de estadísticas.
#


validation_file = DATA_PATH / "validation.csv"


print("\n==========================================")
print("PROCESANDO VALIDATION.CSV")
print("==========================================")


process_file(validation_file)


# ============================================================
# 13. RESULTADO DESPUÉS DE VALIDATION
# ============================================================
#
# Se vuelven a consultar las estadísticas después de incorporar
# los nuevos registros.
#


print("\n==========================================")
print("RESULTADO DESPUÉS DE VALIDATION")
print("==========================================")


statistics_after = get_statistics()

show_statistics()


# ============================================================
# 14. CONSULTA FINAL A LA BASE DE DATOS
# ============================================================
#
# Se realiza nuevamente la consulta SQL para comprobar que las
# estadísticas incrementales siguen coincidiendo con los valores
# calculados directamente sobre transactions.
#


print("\n==========================================")
print("CONSULTA FINAL DIRECTA A LA BASE DE DATOS")
print("==========================================")


database_after = query_database()

show_database_query(database_after)


print("\nComprobación incremental vs SQL:")

compare_statistics(
    statistics_after,
    database_after
)


# ============================================================
# 15. COMPARACIÓN ANTES VS DESPUÉS DE VALIDATION
# ============================================================
#
# Finalmente se muestran los cambios producidos al incorporar
# validation.csv.
#
# Esto permite evidenciar cómo evolucionaron las estadísticas
# del pipeline después de recibir nuevos datos.
#


print("\n==========================================")
print("CÓMO CAMBIARON LOS VALORES")
print("==========================================")


print(
    f"  {'Métrica':<18}"
    f"{'Antes':>18}"
    f"{'Después':>18}"
    f"{'Cambio':>16}"
)


print("  " + "-" * 70)


comparison = [
    ("Total filas", "total_rows"),
    ("Promedio", "average_price"),
    ("Mínimo", "price_min"),
    ("Máximo", "price_max")
]


for name, key in comparison:

    before_value = float(database_before[key])
    after_value = float(database_after[key])

    print(
        f"  {name:<18}"
        f"{before_value:>18.6f}"
        f"{after_value:>18.6f}"
        f"{after_value - before_value:>+16.6f}"
    )


# ============================================================
# 16. CIERRE DEL PROCESO
# ============================================================
#
# Una vez terminada la ejecución se cierra la conexión con SQLite.
#


connection.close()

print("\nProceso terminado correctamente.")