-- =============================================================
-- Proyecto Final — Violencia contra las Mujeres en México
-- Fuente: SESNSP — Incidencia Delictiva Estatal 2015–2025
-- Módulo 4: Inteligencia de negocios y SQL avanzado
-- Diplomado IIMAS, UNAM
-- Erazo Amaya Karla Yoloxochitl 
-- =============================================================

CREATE SCHEMA IF NOT EXISTS violencia_dwh;
SET search_path = violencia_dwh;

-- ---------------------------------------------------------------
-- 1. dim_tiempo
--    Grano: un registro por (año, mes) → 132 filas (2015-2025)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_tiempo (
    id_tiempo        SERIAL      PRIMARY KEY,
    anio             SMALLINT    NOT NULL,
    mes              SMALLINT    NOT NULL,
    nombre_mes       VARCHAR(20) NOT NULL,
    trimestre        SMALLINT    NOT NULL,
    semestre         SMALLINT    NOT NULL,
    periodo_label    VARCHAR(10) NOT NULL,         -- ej. '2023-03'
    es_anio_pandemia BOOLEAN     NOT NULL DEFAULT FALSE  -- TRUE en 2020-2021
);

-- ---------------------------------------------------------------
-- 2. dim_entidad
--    Una fila por entidad federativa (32 estados)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_entidad (
    id_entidad     SERIAL      PRIMARY KEY,
    clave_entidad  SMALLINT    NOT NULL UNIQUE,    -- clave INEGI 01–32
    nombre_entidad VARCHAR(60) NOT NULL,
    region         VARCHAR(30) NOT NULL            -- 'Norte','Centro','Sur','CDMX'
);

-- ---------------------------------------------------------------
-- 3. dim_delito
--    Catálogo de subtipos de delito seleccionados para el análisis
--    Jerarquía real del archivo SESNSP:
--    Bien jurídico → Tipo de delito → Subtipo de delito
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_delito (
    id_delito      SERIAL       PRIMARY KEY,
    bien_juridico  VARCHAR(80)  NOT NULL,   -- ej. 'La vida y la integridad corporal'
    tipo_delito    VARCHAR(80)  NOT NULL,   -- ej. 'Homicidio', 'Lesiones'
    subtipo_delito VARCHAR(80)  NOT NULL,   -- ej. 'Homicidio doloso', 'Lesiones culposas'
    categoria      VARCHAR(50)  NOT NULL,   -- 'Violencia letal intencional', etc.
    es_letal       BOOLEAN      NOT NULL,   -- TRUE para feminicidio y homicidio
    descripcion    VARCHAR(200)
);

-- ---------------------------------------------------------------
-- 4. fact_victimas
--    Grano: una fila por (entidad × subtipo de delito × mes)
--    Cada fila es un agregado mensual, NO una víctima individual
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_victimas (
    id_hecho     SERIAL    PRIMARY KEY,
    id_tiempo    INT       NOT NULL REFERENCES dim_tiempo(id_tiempo),
    id_entidad   INT       NOT NULL REFERENCES dim_entidad(id_entidad),
    id_delito    INT       NOT NULL REFERENCES dim_delito(id_delito),

    -- Métrica principal
    num_victimas INT       NOT NULL DEFAULT 0,

    -- Trazabilidad
    fuente       VARCHAR(100) DEFAULT 'SESNSP - Incidencia delictiva estatal',
    fecha_carga  TIMESTAMP    DEFAULT NOW()
);

-- Índices para acelerar queries analíticas
CREATE INDEX IF NOT EXISTS idx_fact_tiempo   ON fact_victimas(id_tiempo);
CREATE INDEX IF NOT EXISTS idx_fact_entidad  ON fact_victimas(id_entidad);
CREATE INDEX IF NOT EXISTS idx_fact_delito   ON fact_victimas(id_delito);
