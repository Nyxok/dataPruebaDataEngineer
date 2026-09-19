# Prueba Técnica - Data Engineer

## Descripción

Este proyecto implementa un pipeline de procesamiento de datos para cargar archivos CSV en una base de datos SQLite y mantener estadísticas incrementales sobre el campo `price`.

La solución procesa los archivos CSV de forma secuencial, evitando mantener todos los archivos simultáneamente en memoria.

## Estructura del proyecto

```text
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
* Módulos estándar: `csv`, `sqlite3` y `pathlib`

SQLite viene integrada con Python, por lo que no requiere un servidor de base de datos adicional.

## Funcionamiento

Los archivos `2012-1.csv` a `2012-5.csv` se procesan uno a uno y sus registros se almacenan en la tabla `transactions`.

Las estadísticas de `price` se mantienen de forma incremental en la tabla `statistics`, sin volver a recorrer los datos ya cargados.

También se cuenta con una tabla `rejected_rows` para registrar filas que no cumplan las validaciones. Los `price` vacíos se permiten y se almacenan como `NULL`.

Finalmente, `validation.csv` se procesa mediante el mismo flujo y los resultados se comparan contra una consulta directa a la base de datos.

