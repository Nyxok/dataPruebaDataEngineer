import sqlite3
import csv
from pathlib import Path


# ============================================================
# CONFIGURACIÓN DE RUTAS
# ============================================================

# La ruta se construye a partir de la ubicación del proyecto,
# por lo que funciona independientemente de dónde se descargue.
try:
    BASE_DIR = Path(__file__).resolve().parent.parent
except NameError:
    BASE_DIR = Path.cwd().parent

DATABASE_PATH = BASE_DIR / "database" / "pipeline.db"
DATA_PATH = BASE_DIR / "data"

# Crea la carpeta de la base de datos si no existe.
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

print("Conexión a la base de datos exitosa")
print(f"Base de datos: {DATABASE_PATH}")
print(f"Carpeta de datos: {DATA_PATH}")


# ============================================================
# CREACIÓN DE TABLAS
# ============================================================

# Se reinician las tablas para que cada ejecución del ejercicio
# comience desde cero y no genere registros duplicados.
cursor.execute("DROP TABLE IF EXISTS transactions")
cursor.execute("DROP TABLE IF EXISTS statistics")
cursor.execute("DROP TABLE IF EXISTS rejected_rows")

cursor.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        price REAL,
        user_id INTEGER,
        source_file TEXT NOT NULL
    )
""")

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

# Las filas que no pasan las validaciones se conservan en una
# tabla de cuarentena junto con el motivo del rechazo.
cursor.execute("""
    CREATE TABLE rejected_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT NOT NULL,
        row_number INTEGER NOT NULL,
        raw_row TEXT,
        reason TEXT
    )
""")

cursor.execute("""
    INSERT INTO statistics (id)
    VALUES (1)
""")

connection.commit()


# ============================================================
# ESTADÍSTICAS INCREMENTALES
# ============================================================

def update_statistics(price):
    """
    Actualiza las estadísticas sin volver a recorrer
    los registros almacenados en transactions.
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


def get_statistics():
    """
    Obtiene las estadísticas acumuladas.
    El promedio se calcula utilizando la suma y la cantidad
    de precios válidos.
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


def query_database():
    """
    Ejecuta agregaciones directamente sobre transactions
    para validar que coincidan con las estadísticas incrementales.
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
    """Muestra el resultado de la consulta directa a la base de datos."""

    print(f"  Total filas: {result['total_rows']}")
    print(f"  Precios válidos: {result['valid_price_count']}")
    print(f"  Promedio: {result['average_price']:.10f}")
    print(f"  Mínimo: {result['price_min']}")
    print(f"  Máximo: {result['price_max']}")


def compare_statistics(stats, database_result):
    """
    Compara las estadísticas incrementales con los agregados
    calculados directamente sobre transactions.
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
# VALIDACIÓN DE FILAS
# ============================================================

def parse_row(row):
    """
    Valida y transforma una fila del CSV.

    Retorna:
        (registro, None) si la fila es válida.
        (None, motivo) si la fila debe ser rechazada.
    """

    timestamp = (row.get("timestamp") or "").strip()

    if timestamp == "":
        return None, "timestamp vacío"

    raw_price = (row.get("price") or "").strip()

    # Un price vacío representa un valor NULL válido de negocio.
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
# PROCESAMIENTO DE ARCHIVOS
# ============================================================

def process_file(file_path):
    """
    Procesa un CSV de forma secuencial, fila por fila.

    Solo se mantiene en memoria la fila que se está procesando
    y un único archivo CSV permanece abierto.
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

            record, reason = parse_row(row)

            # Una fila inválida no detiene el procesamiento completo.
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

            update_statistics(price)

            row_count += 1

    connection.commit()

    print(
        f"Filas cargadas: {row_count} | "
        f"Filas rechazadas: {rejected_count}"
    )

    print("Estadísticas acumuladas:")
    show_statistics()


# ============================================================
# 1. CARGA DE LOS ARCHIVOS PRINCIPALES
# ============================================================

# Los archivos se ordenan por el número del nombre para respetar
# el orden temporal indicado en el enunciado.
# validation.csv se excluye del conjunto principal.
csv_files = sorted(
    DATA_PATH.glob("2012-*.csv"),
    key=lambda path: int(path.stem.split("-")[1])
)

print("\nArchivos principales encontrados:")

for file in csv_files:
    print(f"- {file.name}")

for file in csv_files:
    process_file(file)


# ============================================================
# 2. RESULTADO ANTES DE VALIDATION
# ============================================================

print("\n==========================================")
print("RESULTADO ANTES DE VALIDATION")
print("==========================================")

statistics_before = get_statistics()
show_statistics()


# ============================================================
# 3. CONSULTA DIRECTA A LA BASE DE DATOS
# ============================================================

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
# 4. PROCESAMIENTO DE VALIDATION.CSV
# ============================================================

validation_file = DATA_PATH / "validation.csv"

print("\n==========================================")
print("PROCESANDO VALIDATION.CSV")
print("==========================================")

process_file(validation_file)


# ============================================================
# 5. RESULTADO DESPUÉS DE VALIDATION
# ============================================================

print("\n==========================================")
print("RESULTADO DESPUÉS DE VALIDATION")
print("==========================================")

statistics_after = get_statistics()
show_statistics()


# ============================================================
# 6. CONSULTA FINAL DIRECTA A LA BASE DE DATOS
# ============================================================

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
# 7. COMPARACIÓN ANTES Y DESPUÉS DE VALIDATION
# ============================================================

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


connection.close()

print("\nProceso terminado correctamente.")