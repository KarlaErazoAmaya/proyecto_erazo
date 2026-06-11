# Violencia contra las Mujeres en México (2015–2025)
### Análisis de incidencia delictiva por entidad federativa

> Proyecto Final · Módulo 4: Inteligencia de negocios y SQL avanzado  
> Diplomado en Bases de Datos y Sistemas de Información — IIMAS, UNAM · 2025

---

## Resumen ejecutivo

| Campo | Valor |
|---|---|
| **Pregunta analítica** | ¿Cómo ha evolucionado la incidencia de los principales delitos contra las mujeres en México entre 2015 y 2025, y qué entidades federativas presentan los mayores niveles y tendencias de crecimiento? |
| **Dataset** | Incidencia Delictiva Estatal (SESNSP) 2015–2025 |
| **Fuente** | [sesnsp.gob.mx — Datos abiertos de incidencia delictiva estatal](https://www.gob.mx/sesnsp/acciones-y-programas/datos-abiertos-de-incidencia-delictiva) |
| **Modelo** | Estrella: 1 fact + 3 dimensiones (tiempo, entidad, delito) |
| **Infraestructura** | AWS Aurora PostgreSQL — schema `violencia_dwh` |
| **ETL** | Python (pandas + SQLAlchemy) |
| **SQL avanzado** | Window functions (`RANK`, `LAG`), CTEs, funciones analíticas (`PERCENTILE_CONT`) |
| **Dashboard** | Power BI |

---

## Problema y motivación

La violencia contra las mujeres es uno de los principales problemas de seguridad y derechos humanos en México. En los últimos años, ha aumentado la cantidad de delitos como el feminicidio, el homicidio doloso, las lesiones dolosas y la violencia familiar.

Las autoridades publican información sobre la incidencia delictiva de forma regular. Sin embargo, el gran volumen de datos dificulta la identificación de patrones territoriales y temporales.

Este proyecto buscará responder cuatro preguntas:

1. ¿Qué entidades federativas concentran el mayor número de delitos contra las mujeres?
2. ¿Cómo ha evolucionado la incidencia de estos delitos entre 2015 y 2025?
3. ¿Hay estados donde el crecimiento de la violencia ha sido significativamente mayor que el promedio nacional? 
4. ¿Cuáles son los delitos que presentan las tendencias de crecimiento más preocupantes?

La respuesta a estas preguntas permite identificar focos de atención para el diseño de políticas públicas y estrategias de prevención.

---

## Origen de los datos

**Fuente:** Secretariado Ejecutivo del Sistema Nacional de Seguridad Pública (SESNSP)  
**Descarga directa:** https://www.gob.mx/sesnsp/acciones-y-programas/datos-abiertos-de-incidencia-delictiva  
**Archivo:** `Estatal-Delitos-2015-2025 (Excel/CSV)`

El dataset contiene más de 8,800 registros de víctimas de feminicidio entre 2015 y 2020, además de otros delitos contra las mujeres, generando decenas de miles de observaciones para análisis temporal y geográfico.

### Estructura del archivo fuente

El archivo original contiene **todos los delitos del fuero común** con la siguiente estructura:

| Columna | Descripción |
|---|---|
| `Año` | Año del registro (2015–2025) |
| `Clave_Entidad` | Clave INEGI de la entidad federativa (1–32) |
| `Entidad` | Nombre de la entidad federativa |
| `Bien jurídico afectado` | Categoría jurídica (ej. "La vida y la integridad corporal") |
| `Tipo de delito` | Delito específico (ej. "Feminicidio", "Homicidio", "Lesiones") |
| `Subtipo de delito` | Desglose del tipo (ej. "Homicidio doloso", "Homicidio culposo") |
| `Modalidad` | Medio o circunstancia (ej. "Con arma de fuego", "Con arma blanca") |
| `Enero` … `Diciembre` | Número de víctimas registradas por mes |

El ETL filtra únicamente los subtipos relevantes para el análisis de violencia contra las mujeres.

### Delitos seleccionados para el análisis

Como el dataset no contiene información individual de las víctimas, el análisis se realiza agregado mensual por entidad federativa y tipo de delito. 

| Tipo de delito | Subtipo | Categoría analítica |
|---|---|---|
| Feminicidio | Feminicidio | Violencia letal intencional |
| Homicidio | Homicidio doloso | Violencia letal intencional |
| Homicidio | Homicidio culposo | Violencia letal no intencional |
| Lesiones | Lesiones dolosas | Violencia no letal |
| Lesiones | Lesiones culposas | Violencia no letal |
| Trata de personas | Trata de personas | Violencia no letal |
| Violencia familiar | Violencia familiar | Violencia no letal |
| Violencia de género | Violencia de género en todas sus modalidades | Violencia no letal |
| Acoso sexual | Acoso sexual | Violencia no letal |
| Hostigamiento sexual | Hostigamiento sexual | Violencia no letal |

### Flujo end-to-end

```
┌──────────────────────────────────────────────┐
│  SESNSP (portal público)                     │
│  gob.mx/sesnsp/datos-abiertos-incidencia     │
│                                              │
│  • Excel/CSV con todos los delitos           │
│    del fuero común 2015–2025                 │
│  • Columnas: Año, Entidad, Bien jurídico,    │
│    Tipo, Subtipo, Modalidad, Ene–Dic         │
└──────────────────────┬───────────────────────┘
                       │  pandas read_excel / read_csv
                       ▼
┌──────────────────────────────────────────────┐
│  ETL Python — etl_pipeline.py                │
│                                              │
│  Extract:   lee archivo fuente               │
│  Transform: filtra subtipos de interés,      │
│             conversión formato ancho→largo,  │
│             normalización de nombres,        │
│             construcción de dimensiones,     │
│             generación de surrogate keys     │
│  Load:      to_sql() con SQLAlchemy          │
│  Validate:  conteo vs origen                 │
└──────────────────────┬───────────────────────┘
                       │  INSERT
                       ▼
┌──────────────────────────────────────────────┐
│  AWS Aurora PostgreSQL                       │
│  Schema: violencia_dwh                       │
│                                              │
│  • 3 dimensiones pobladas                    │
│  • fact_victimas                             │
└──────────────────────┬───────────────────────┘
                       │  conexión directa
                       ▼
┌──────────────────────────────────────────────┐
│  Dashboard Power BI                          │
│  3+ visualizaciones interactivas             │
└──────────────────────────────────────────────┘
```

---

## Estructura del repositorio

```
proyecto-violencia-mujeres/
├── README.md                          ← este archivo
├── datasets/
│   └── README_datasets.md             ← instrucciones de descarga
├── scripts/
│   ├── 01_schema_ddl.sql              ← creación del modelo dimensional
│   └── etl_pipeline.py                ← ETL completo Extract → Transform → Load
├── dashboard/
│   └── violencia_mujeres.pbix         ← dashboard Power BI
└── docs/
    └── diagrama_modelo.svg            ← diagrama del esquema estrella
```

---

## Modelo dimensional

### Grano de la tabla de hechos

Cada registro de `fact_victimas` representa el número de víctimas registradas para un subtipo de delito específico en una entidad federativa durante un mes determinado.

### Esquema estrella

```
                    ┌──────────────────┐
                    │   dim_tiempo     │
                    │                  │
                    │ tiempo_key PK    │
                    │ anio             │
                    │ mes              │
                    │ nombre_mes       │
                    │ trimestre        │
                    │ semestre         │
                    │ periodo_label    │
                    │ es_anio_pandemia │
                    └────────┬─────────┘
                             │
┌──────────────────┐  ┌──────┴───────────────────────┐  ┌──────────────────┐
│   dim_entidad    │◄─│       fact_victimas           │─►│   dim_delito     │
│                  │  │                               │  │                  │
│ entidad_key PK   │  │ id_hecho PK                   │  │ delito_key PK    │
│ clave_entidad    │  │ tiempo_key FK                 │  │ tipo_delito      │
│ nombre_entidad   │  │ entidad_key FK                │  │ subtipo_delito   │
│ region           │  │ delito_key FK                 │  │ bien_juridico    │
└──────────────────┘  │                               │  │ categoria        │
                      │ num_victimas                  │  │ es_letal         │
                      │ fuente                        │  └──────────────────┘
                      │ fecha_carga                   │
                      └───────────────────────────────┘
```

### Decisiones de diseño

**Grano de la fact:** una fila por (entidad × subtipo de delito × mes). Cada fila es un agregado mensual, no una víctima individual. El campo `id_hecho` es la llave surrogate del hecho.

**`subtipo_delito` y `bien_juridico` en dim_delito:** el archivo fuente tiene tres niveles (tipo → subtipo → modalidad). Se consolidan tipo y subtipo en la dimensión para tener el grano correcto de análisis. La modalidad (arma de fuego, arma blanca, etc.) se omite en esta versión para mantener el modelo simple y enfocado.

**`region` en dim_entidad:** agrupa los 32 estados en regiones geográficas (Norte, Centro, Sur, CDMX) para análisis de clusters sin joins adicionales — desnormalización deliberada siguiendo la metodología Kimball.

**`es_letal` en dim_delito:** flag que separa delitos letales (feminicidio, homicidio) de no letales (lesiones, trata, violencia familiar) con un filtro simple.

**`es_anio_pandemia` en dim_tiempo:** controla el efecto COVID-19 en 2020–2021, donde el confinamiento alteró tanto la incidencia real como el registro de denuncias.

---

## Cómo ejecutar

### Requisitos previos

```bash
pip install pandas sqlalchemy psycopg2-binary openpyxl
```

### 1. Descargar el dataset

1. Ir a: https://www.gob.mx/sesnsp/acciones-y-programas/datos-abiertos-de-incidencia-delictiva
2. Descargar: **"Estatal-Delitos-2015-2025"**
3. Guardar en: `datasets/Estatal-Delitos-2015-2025.xlsx`

### 2. Crear el schema en Aurora

```bash
psql "postgresql://postgres:TU_PASSWORD@TU_HOST.rds.amazonaws.com:5432/northwind" \
     -f scripts/01_schema_ddl.sql
```

### 3. Correr el ETL

```bash
export AURORA_HOST=TU_HOST.rds.amazonaws.com
export AURORA_PASSWORD=TU_PASSWORD

python scripts/etl_pipeline.py
```

### 4. Abrir el dashboard

Abrir `dashboard/violencia_mujeres.pbix` en Power BI Desktop.

---

## SQL avanzado — técnicas aplicadas

### 1. Window function — Ranking de entidades por feminicidios (`RANK`)
```sql
SELECT
    de.nombre_entidad,
    dt.anio,
    SUM(fv.num_victimas) AS total_feminicidios,
    RANK() OVER (
        PARTITION BY dt.anio
        ORDER BY SUM(fv.num_victimas) DESC
    ) AS ranking_anual
FROM violencia_dwh.fact_victimas fv
JOIN violencia_dwh.dim_tiempo  dt USING (tiempo_key)
JOIN violencia_dwh.dim_entidad de USING (entidad_key)
JOIN violencia_dwh.dim_delito  dd USING (delito_key)
WHERE dd.subtipo_delito = 'Feminicidio'
GROUP BY de.nombre_entidad, dt.anio;
```

### 2. Window function — Variación año a año (`LAG`)
```sql
WITH anual AS (
    SELECT
        de.nombre_entidad,
        dt.anio,
        SUM(fv.num_victimas) AS total
    FROM violencia_dwh.fact_victimas fv
    JOIN violencia_dwh.dim_tiempo  dt USING (tiempo_key)
    JOIN violencia_dwh.dim_entidad de USING (entidad_key)
    JOIN violencia_dwh.dim_delito  dd USING (delito_key)
    WHERE dd.es_letal = TRUE
    GROUP BY de.nombre_entidad, dt.anio
)
SELECT
    nombre_entidad,
    anio,
    total,
    LAG(total) OVER (PARTITION BY nombre_entidad ORDER BY anio) AS anio_anterior,
    ROUND(100.0 * (total - LAG(total) OVER (
        PARTITION BY nombre_entidad ORDER BY anio)
    ) / NULLIF(LAG(total) OVER (
        PARTITION BY nombre_entidad ORDER BY anio), 0), 1) AS pct_cambio
FROM anual
ORDER BY pct_cambio DESC NULLS LAST;
```

### 3. CTE — Estados con mayor proporción de delitos letales
```sql
WITH totales AS (
    SELECT
        de.nombre_entidad,
        SUM(fv.num_victimas)                                   AS total_delitos,
        SUM(fv.num_victimas) FILTER (WHERE dd.es_letal = TRUE) AS delitos_letales
    FROM violencia_dwh.fact_victimas fv
    JOIN violencia_dwh.dim_entidad de USING (entidad_key)
    JOIN violencia_dwh.dim_delito  dd USING (delito_key)
    GROUP BY de.nombre_entidad
)
SELECT
    nombre_entidad,
    total_delitos,
    delitos_letales,
    ROUND(100.0 * delitos_letales / NULLIF(total_delitos, 0), 1) AS pct_letal
FROM totales
ORDER BY pct_letal DESC;
```

### 4. Función analítica — Percentil 90 por subtipo de delito (`PERCENTILE_CONT`)
```sql
SELECT
    dd.subtipo_delito,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY fv.num_victimas) AS mediana_mensual,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY fv.num_victimas) AS p90_mensual
FROM violencia_dwh.fact_victimas fv
JOIN violencia_dwh.dim_delito dd USING (delito_key)
GROUP BY dd.subtipo_delito
ORDER BY p90_mensual DESC;
```

---

## Dashboard propuesto

| # | Visualización | Objetivo |
|---|---|---|
| 1 | **Evolución temporal de feminicidios por entidad federativa** (gráfica de líneas) | Identificar tendencias de crecimiento o disminución a lo largo del tiempo |
| 2 | **Mapa coroplético de México** por incidencia acumulada de delitos contra las mujeres | Detectar concentración geográfica y entidades de alto riesgo |
| 3 | **Ranking Top 10 entidades** con mayor incidencia acumulada (barras horizontales) | Comparar entidades y priorizar focos de atención |
| 4 | **Variación porcentual anual** calculada con `LAG()` *(--)* | Detectar incrementos atípicos por estado y año |

---

## Hallazgos preliminares (se completará en la entrega final)

*(Esta sección se completará con los resultados del dashboard tras cargar los datos completos 2015–2025.)*

Se espera identificar patrones temporales y geográficos en los delitos contra las mujeres, así como las entidades con mayor incidencia y crecimiento durante el periodo analizado. El uso de window functions y CTEs permitirá detectar tendencias que no son visibles en reportes estáticos.

---

## Referencias

- [SESNSP — Datos abiertos de incidencia delictiva](https://www.gob.mx/sesnsp/acciones-y-programas/datos-abiertos-de-incidencia-delictiva)
- [SESNSP — Informe de violencia contra las mujeres](https://www.gob.mx/sesnsp/documentos/informe-de-violencia-contra-las-mujeres)
- Material del módulo 4 — IIMAS, UNAM: OLAP, ETL Python, SQL avanzado
