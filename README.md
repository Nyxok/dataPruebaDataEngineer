# Prueba Técnica - Data Engineer

## Descripción

Pipeline en Python para procesar archivos CSV de forma secuencial, almacenarlos en SQLite y mantener estadísticas incrementales sobre `price`.

La solución procesa un archivo a la vez y no carga todos los archivos simultáneamente en memoria.

## Estructura

dataPruebaDataEngineer/
│
├── data/
│   ├── 2012-1.csv
│   ├── 2012-2.csv
│   ├── 2012-3.csv
│   ├── 2012-4.csv
│   ├── 2012-5.csv
│   └── validation.csv
│
├── database/
│   └── pipeline.db
│
├── src/
│   └── pipeline.py
│
└── README.md
```

## Tecnologías

* Python 3
* SQLite
* `csv`
* `sqlite3`
* `pathlib`

## Flujo

```text
CSV
 ↓
Lectura secuencial
 ↓
Validación
 ↓
Carga en SQLite
 ↓
Actualización incremental de estadísticas
 ↓
Validación de resultados mediante SQL
```

Los archivos `2012-1.csv` a `2012-5.csv` se procesan en orden. Posteriormente, `validation.csv` se procesa utilizando el mismo flujo.

## Estadísticas

Durante el procesamiento se mantienen de forma incremental:

* Total de filas.
* Cantidad de precios válidos.
* Suma de `price`.
* Mínimo.
* Máximo.
* Promedio.

El promedio se obtiene a partir de la suma y la cantidad de precios válidos, evitando recalcular `AVG(price)` sobre todos los registros después de cada carga.

## Validaciones

Los registros son validados antes de almacenarse.

* `timestamp` es obligatorio.
* `price` puede ser `NULL`, pero si tiene valor debe ser numérico y no negativo.
* `user_id` puede ser `NULL`, pero si tiene valor debe ser entero.
* Las filas rechazadas se almacenan en `rejected_rows` con su motivo.

## Ejecución

Desde la carpeta raíz:

```bash
python src/pipeline.py
```

La base de datos `pipeline.db` se crea automáticamente en la carpeta `database/`.

Durante la ejecución se muestran las estadísticas acumuladas, la consulta directa a la base de datos y la comparación antes y después de procesar `validation.csv`.
