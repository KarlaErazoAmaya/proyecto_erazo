-- =============================================================
-- Queries analíticas — Violencia contra las Mujeres en México
-- Fuente: SESNSP 2015-2025 | Schema: violencia_dwh
-- =============================================================
-- Usa USING() porque id_tiempo, id_entidad, id_delito son los
-- nombres EXACTOS de las llaves en dim_tiempo, dim_entidad y
-- dim_delito (consistentes con 01_schema_ddl.sql y el README).
-- =============================================================

-- --------------------------------------------------------------
-- 0. Validación de carga
-- --------------------------------------------------------------

SELECT 'dim_tiempo' AS tabla, COUNT(*) AS registros
FROM violencia_dwh.dim_tiempo

UNION ALL

SELECT 'dim_entidad', COUNT(*)
FROM violencia_dwh.dim_entidad

UNION ALL

SELECT 'dim_delito', COUNT(*)
FROM violencia_dwh.dim_delito

UNION ALL

SELECT 'fact_victimas', COUNT(*)
FROM violencia_dwh.fact_victimas;

-- ---------------------------------------------------------------
-- 1. Ranking de entidades por feminicidios (RANK)
--    Responde: ¿qué entidades concentran más feminicidios cada año?
-- ---------------------------------------------------------------
SELECT
    de.nombre_entidad,
    dt.anio,
    SUM(fv.num_victimas) AS total_feminicidios,
    RANK() OVER (
        PARTITION BY dt.anio
        ORDER BY SUM(fv.num_victimas) DESC
    ) AS ranking_anual
FROM violencia_dwh.fact_victimas fv
JOIN violencia_dwh.dim_tiempo   dt USING (id_tiempo)
JOIN violencia_dwh.dim_entidad  de USING (id_entidad)
JOIN violencia_dwh.dim_delito   dd USING (id_delito)
WHERE dd.subtipo_delito = 'Feminicidio'
GROUP BY de.nombre_entidad, dt.anio
ORDER BY dt.anio, ranking_anual;


-- ---------------------------------------------------------------
-- 2. Variación año a año (LAG)
--    Responde: ¿en qué estados crece más la violencia letal?
-- ---------------------------------------------------------------
WITH anual AS (
    SELECT
        de.nombre_entidad,
        dt.anio,
        SUM(fv.num_victimas) AS total
    FROM violencia_dwh.fact_victimas fv
    JOIN violencia_dwh.dim_tiempo   dt USING (id_tiempo)
    JOIN violencia_dwh.dim_entidad  de USING (id_entidad)
    JOIN violencia_dwh.dim_delito   dd USING (id_delito)
    WHERE dd.es_letal = TRUE
    GROUP BY de.nombre_entidad, dt.anio
)
SELECT
    nombre_entidad,
    anio,
    total,
    LAG(total) OVER (PARTITION BY nombre_entidad ORDER BY anio) AS anio_anterior,
    total - LAG(total) OVER (PARTITION BY nombre_entidad ORDER BY anio) AS variacion_absoluta,
    ROUND(
        100.0 * (total - LAG(total) OVER (PARTITION BY nombre_entidad ORDER BY anio))
        / NULLIF(LAG(total) OVER (PARTITION BY nombre_entidad ORDER BY anio), 0)
    , 1) AS pct_cambio
FROM anual
ORDER BY pct_cambio DESC NULLS LAST;


-- ---------------------------------------------------------------
-- 3. CTE — Estados con mayor proporción de delitos letales
--    Responde: ¿dónde la violencia contra mujeres es más letal,
--    proporcionalmente, no solo en volumen absoluto?
-- ---------------------------------------------------------------
WITH totales AS (
    SELECT
        de.nombre_entidad,
        SUM(fv.num_victimas)                                   AS total_delitos,
        SUM(fv.num_victimas) FILTER (WHERE dd.es_letal = TRUE) AS delitos_letales
    FROM violencia_dwh.fact_victimas fv
    JOIN violencia_dwh.dim_entidad de USING (id_entidad)
    JOIN violencia_dwh.dim_delito  dd USING (id_delito)
    GROUP BY de.nombre_entidad
)
SELECT
    nombre_entidad,
    total_delitos,
    delitos_letales,
    ROUND(100.0 * delitos_letales / NULLIF(total_delitos, 0), 1) AS pct_letal
FROM totales
ORDER BY pct_letal DESC;


-- ---------------------------------------------------------------
-- 4. Función analítica — Percentil 90 por subtipo de delito (PERCENTILE_CONT)
--    Responde: ¿qué meses/entidades son atípicamente altos
--    respecto al comportamiento normal de cada delito?
-- ---------------------------------------------------------------
SELECT
    dd.subtipo_delito,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY fv.num_victimas) AS mediana_mensual,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY fv.num_victimas) AS p90_mensual,
    MAX(fv.num_victimas)                                          AS maximo_mensual
FROM violencia_dwh.fact_victimas fv
JOIN violencia_dwh.dim_delito dd USING (id_delito)
GROUP BY dd.subtipo_delito
ORDER BY p90_mensual DESC;


-- ---------------------------------------------------------------
-- 5. Bono — Top 10 entidades por incidencia acumulada total
--    (para alimentar la visualización 3 del dashboard)
-- ---------------------------------------------------------------
SELECT
    de.nombre_entidad,
    de.region,
    SUM(fv.num_victimas) AS total_acumulado
FROM violencia_dwh.fact_victimas fv
JOIN violencia_dwh.dim_entidad de USING (id_entidad)
GROUP BY de.nombre_entidad, de.region
ORDER BY total_acumulado DESC
LIMIT 10;


-- ---------------------------------------------------------------
-- 6. Bono — Serie mensual nacional para detectar estacionalidad
--    (para alimentar la visualización 1 del dashboard)
-- ---------------------------------------------------------------
SELECT
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    SUM(fv.num_victimas) AS total_mensual
FROM violencia_dwh.fact_victimas fv
JOIN violencia_dwh.dim_tiempo dt USING (id_tiempo)
JOIN violencia_dwh.dim_delito dd USING (id_delito)
WHERE dd.subtipo_delito = 'Feminicidio'
GROUP BY dt.anio, dt.mes, dt.nombre_mes
ORDER BY dt.anio, dt.mes;

-- ---------------------------------------------------------------
-- 7. Datos para mapa por entidad
--    Responde: ¿qué entidades concentran más víctimas registradas?
--    Útil para el mapa coroplético en Power BI.
-- ---------------------------------------------------------------
SELECT
    de.nombre_entidad,
    de.region,
    SUM(fv.num_victimas) AS total_victimas
FROM violencia_dwh.fact_victimas fv
JOIN violencia_dwh.dim_entidad de USING (id_entidad)
GROUP BY de.nombre_entidad, de.region
ORDER BY total_victimas DESC;

-- ---------------------------------------------------------------
-- 8. Evolución anual por subtipo de delito
--    Responde: ¿qué delitos presentan mayor crecimiento?
-- ---------------------------------------------------------------

SELECT
    dt.anio,
    dd.subtipo_delito,
    SUM(fv.num_victimas) AS total_victimas
FROM violencia_dwh.fact_victimas fv
JOIN violencia_dwh.dim_tiempo dt USING (id_tiempo)
JOIN violencia_dwh.dim_delito dd USING (id_delito)
GROUP BY dt.anio, dd.subtipo_delito
ORDER BY dt.anio, dd.subtipo_delito;