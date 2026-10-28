"""Modelo de consulta generado; fórmulas idénticas al actualizador local. No usa ODBC."""
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
os.environ.setdefault("POLARS_MAX_THREADS", "2")
import polars as pl

ESQUEMA = {
    'ID': pl.Float64, 'AREA': pl.String, 'PROCESO': pl.String, 'PROBOPR': pl.String,
    'ESTRATEG': pl.String, 'ACTIVID': pl.String, 'META': pl.String, 'TAREAS': pl.String,
    'FECINICIAL': pl.Datetime('ns'), 'FECFINAL': pl.Datetime('ns'),
    'RESPONSABLE': pl.String, 'RECURSOS': pl.String, 'INDICADOR': pl.String,
    'RESREAL': pl.String, 'EJECUCION': pl.Float64, 'CRONOGRAMA': pl.Float64,
    'LOGMETA': pl.Float64, 'FACTLIM': pl.String, 'IDENC': pl.String, 'PERIODO': pl.Int64,
    'ANO': pl.Int64, 'CALIFICACION': pl.Float64, 'ESTADO': pl.String, 'OBSESTADO': pl.String,
    'Trimestre': pl.String, 'Trimestre Incial': pl.Int64, 'Filtro': pl.String,
    'Año': pl.Int64, 'llave': pl.String, 'Proceso Final': pl.String,
}


PLAN, ESTRATEGIAS, MATRIZ, CORPORATIVAS = 'Planes Operativos', 'Estrategias', 'Matriz Objetivos', 'Estrategias Corporativas'


ESQUEMAS = {
    PLAN: ESQUEMA,
    ESTRATEGIAS: {
        **dict(list(ESQUEMA.items())[:28]), 'ID': pl.Int64,
        'EJECUCION': pl.String, 'CRONOGRAMA': pl.String, 'LOGMETA': pl.String, 'CALIFICACION': pl.String,
        'CRUCE ESTRATEGIAS': pl.String, 'Peso': pl.Float64, 'LLAVE': pl.Int64,
        'Calificación': pl.Float64, 'valor': pl.Float64, 'prueba': pl.Float64, 'LLAVE2': pl.String,
    },
    MATRIZ: {'Cod_Política': pl.Int64, 'Política': pl.String, 'Cod_Obj': pl.Int64,
        'Objetivo': pl.String, 'Area': pl.String, 'Cod_Estrategia': pl.Int64,
        'Estratégia': pl.String, 'Cuenta': pl.Int64, 'Peso': pl.Float64,
        'valor 1 trim': pl.Float64, 'Peso 1 trim': pl.Float64, 'VALOR': pl.Float64,
        'PESO2': pl.Float64, 'Trimestre': pl.String, 'Lllave': pl.String},
    CORPORATIVAS: {'Area': pl.String, 'Cod_Estrategia': pl.Int64, 'Estratégia': pl.String, 'Cruce': pl.String},
}


TRIMESTRES = ('1er Trimestre', '2do Trimestre', '3er Trimestre', '4to Trimestre')


METAS = dict(zip(TRIMESTRES, (.25, .5, .75, 1.)))


RELACIONES = (
    (PLAN, 'IDENC', ESTRATEGIAS, 'IDENC'),
    (CORPORATIVAS, 'Cod_Estrategia', MATRIZ, 'Cod_Estrategia'),
    ('Trimestres', 'Trimestre', ESTRATEGIAS, 'Trimestre'),
    ('Trimestres', 'Trimestre', MATRIZ, 'Trimestre'),
    ('Metas', 'Trimestre', PLAN, 'Trimestre'),
)


CALENDARIOS = {
    'LocalDateTable_d0877634-0e73-4823-a111-776ba6bd19f7': (PLAN, 'FECINICIAL'),
    'LocalDateTable_e2b2ac52-1e62-41ee-89cd-3f4366ff3a0c': (PLAN, 'FECFINAL'),
    'LocalDateTable_0baccae0-ccd1-4113-b182-0cf7ef527e89': (ESTRATEGIAS, 'FECINICIAL'),
    'LocalDateTable_c9e851ec-cdba-4381-9d60-9223d73cbb04': (ESTRATEGIAS, 'FECFINAL'),
    'LocalDateTable_78b5bc63-b819-4ef1-b387-0ad792d53779': ('Fecha Actualización', 'Fecha Actualización'),
}


AREA_REPLACEMENTS = {'Apoyo Direccion': 'PROCESOS DE APOYO DIRECCIÓN', 'Administracion': 'ADMINISTRATIVA'}


PROCESS_REPLACEMENTS = {
    'INFRAESTRUCTURA': 'Infraestructura', 'MERCADEO ESTRATÉGICO': 'Mercadeo Estratégico',
    'CRÉDITO': 'Crédito', 'ÁREA DE CULTURA': 'Área de Cultura', 'IMPUESTOS': 'Impuestos',
    'CRECE EMPRESARIAL': 'Crece Empresarial', 'CISE SEDE LA VIRGINIA': 'CISE la Virginia',
    'CONTABILIDAD': 'Contabilidad', 'GESTIÓN FINANCIERA': 'Gestión Financiera',
}


FINAL_PROCESS = {
    'Agencia de Empelo / Fosfec': 'Agencia de Empleo / Fosfec',
    'Atecnion Integral A La Niñez': 'Atención Integral a la Niñez',
    'Desarrollo Fisico': 'Infraestructura', 'Administracion Jde': 'Sistemas Informáticos Financieros',
}


class ErrorDatos(ValueError):
    """Error de configuración o de datos que puede mostrarse sin credenciales."""


def _lazy(table):
    return table.lazy() if isinstance(table, pl.DataFrame) else table


def _sum(expression):
    return pl.when(expression.count() > 0).then(expression.sum()).otherwise(None)


def _count(expression):
    return pl.when(expression.count() > 0).then(expression.count().cast(pl.Int64)).otherwise(None)


def _divide(numerator, denominator, alternate=None):
    return pl.when(denominator.is_null() | (denominator == 0)).then(pl.lit(alternate, dtype=pl.Float64)).otherwise(numerator / denominator)


def _group(frame, columns, expressions):
    schema = frame.collect_schema()
    keys = [f'__grupo_{i}' for i in range(len(columns))]
    normalized = [
        (pl.col(c).str.to_lowercase() if schema[c] == pl.String else pl.col(c)).alias(k)
        for c, k in zip(columns, keys)]
    return frame.with_columns(normalized).group_by(keys, maintain_order=True).agg(
        [pl.col(c).first().alias(c) for c in columns] + expressions).drop(keys)


class ModeloPowerBI:
    """Tablas Parquet diferidas y medidas con las relaciones originales.

    Filtros: {'Planes Operativos': {'ANO': [2026], 'Filtro': ['Aplica']}}.
    Una lista vacía selecciona cero filas. None selecciona BLANK.
    Las tablas Resumen son desconectadas, como en el PBIX.
    """
    def __init__(self, origen='modelo_powerbi'):
        self.carpeta = None
        if isinstance(origen, dict):
            self._tablas = {name: _lazy(table) for name, table in origen.items()}
        else:
            self.carpeta = Path(origen).expanduser().resolve()
            pointer = self.carpeta / 'actual.json'
            if not pointer.is_file():
                raise ErrorDatos('No hay una carga completa. Ejecute actualizar_modelo primero.')
            manifest = json.loads(pointer.read_text(encoding='utf-8'))
            self._tablas = {}
            for name, relative in manifest['tablas'].items():
                path = (self.carpeta / relative).resolve()
                if not path.is_relative_to(self.carpeta) or not path.is_file():
                    raise ErrorDatos('La carga contiene una ruta inválida o un archivo ausente.')
                self._tablas[name] = pl.scan_parquet(path)
        self.tablas = tuple(self._tablas)

    def tabla(self, nombre, filtros=None):
        if nombre not in self._tablas:
            raise ErrorDatos(f'Tabla no inventariada: {nombre}')
        context = filtros or {}
        for name, selections in context.items():
            if name not in self._tablas or not isinstance(selections, dict):
                raise ErrorDatos('Los filtros deben indicar una tabla y sus columnas.')
            if set(selections) - set(self._tablas[name].collect_schema()):
                raise ErrorDatos(f'El filtro contiene columnas desconocidas de {name}.')
        filtered, affected = {}, {}

        def has_filter(name):
            if name not in affected:
                affected[name] = bool(context.get(name)) or any(has_filter(parent)
                    for parent, _, child, _ in RELACIONES if child == name)
            return affected[name]

        def visit(name):
            if name in filtered:
                return filtered[name]
            table = self._tablas[name]
            schema = table.collect_schema()
            for column, selection in context.get(name, {}).items():
                values = list(selection) if isinstance(selection, (list, tuple, set)) else [selection]
                expression = pl.col(column)
                if schema[column] == pl.String:
                    expression = expression.str.to_lowercase()
                    values = [v.lower() if isinstance(v, str) else v for v in values]
                nonnull = [v for v in values if v is not None]
                condition = expression.is_in(nonnull).fill_null(False) if nonnull else pl.lit(False)
                if None in values:
                    condition = condition | expression.is_null()
                table = table.filter(condition)
            for parent, parent_key, child, child_key in RELACIONES:
                if child != name or not has_filter(parent):
                    continue
                dimension = visit(parent)
                left, right = pl.col(child_key), pl.col(parent_key)
                if schema[child_key] == pl.String:
                    left, right = left.str.to_lowercase(), right.str.to_lowercase()
                dimension = dimension.select(right.alias('__relacion')).unique()
                table = table.with_columns(left.alias('__relacion')).join(dimension,
                    on='__relacion', how='semi', nulls_equal=True).drop('__relacion')
            filtered[name] = table
            return table
        return visit(nombre)

    def _planes(self, filtros):
        row = self.tabla(PLAN, filtros).select(pl.col('TAREAS').count().alias('tareas'),
            pl.col('CALIFICACION').mean().alias('nota'), pl.col('Trimestre').n_unique().alias('n'),
            pl.col('Trimestre').first().alias('trimestre')).collect(engine='streaming').row(0, named=True)
        quarter = row['trimestre']
        meta = {k.lower(): v for k, v in METAS.items()}.get(quarter.lower()) if row['n'] == 1 and quarter else None
        compliance = 0. if meta is None else row['nota'] / meta if row['nota'] is not None else None
        # Literal autorizado: el filtro Estrategias[ANO]=2024 no retropropaga a Planes.
        return {'Meta Trim': meta, '% Cumplimiento': compliance, 'Tareas 2024': row['tareas'] - 2}

    def medida(self, nombre, filtros=None):
        if nombre == 'prueba':
            raise ErrorDatos('Planes Operativos[prueba] está sin fórmula en el PBIX; permanece bloqueada.')
        if nombre in {'Meta Trim', '% Cumplimiento', 'Tareas 2024'}:
            return self._planes(filtros)[nombre]
        if nombre == 'Hora Actualización':
            value = self.tabla('Fecha Actualización', filtros).select(pl.col('Fecha Actualización').max()).collect().item()
            return value - timedelta(hours=5) if value is not None else None
        if nombre in {'Resultado', 'Resultado2'}:
            table, num, den = (ESTRATEGIAS, 'valor', 'Peso') if nombre == 'Resultado' else (MATRIZ, 'VALOR', 'PESO2')
            return self.tabla(table, filtros).select(_divide(_sum(pl.col(num)), _sum(pl.col(den)))).collect(engine='streaming').item()
        raise ErrorDatos(f'Medida no inventariada: {nombre}')

    def medidas(self, filtros=None):
        return {**self._planes(filtros), **{name: self.medida(name, filtros)
            for name in ('Resultado', 'Resultado2', 'Hora Actualización')}}

    def agrupar(self, tabla, columnas, filtros=None):
        frame = self.tabla(tabla, filtros)
        columnas = [columnas] if isinstance(columnas, str) else list(columnas)
        if not columnas or set(columnas) - set(frame.collect_schema()):
            raise ErrorDatos('Indique columnas existentes para agrupar.')
        if tabla == PLAN:
            meta = pl.when(pl.col('Trimestre').n_unique() == 1).then(
                pl.col('Trimestre').first().str.to_lowercase().replace_strict(
                    {k.lower(): v for k, v in METAS.items()}, default=None, return_dtype=pl.Float64)).otherwise(None)
            return _group(frame, columnas, [pl.col('CALIFICACION').mean().alias('Calificación'),
                _count(pl.col('TAREAS')).alias('Tareas'), _count(pl.col('CALIFICACION')).alias('Calificadas'),
                pl.col('CALIFICACION').is_null().sum().alias('Pendientes'),
                pl.col('ACTIVID').str.to_lowercase().n_unique().alias('Actividades'), meta.alias('Meta Trim'),
                (pl.col('TAREAS').count().cast(pl.Int64) - 2).alias('Tareas 2024')]).with_columns(
                    _divide(pl.col('Calificación'), pl.col('Meta Trim'), 0.).alias('% Cumplimiento'))
        if tabla in {ESTRATEGIAS, MATRIZ}:
            num, den, result = ('valor', 'Peso', 'Resultado') if tabla == ESTRATEGIAS else ('VALOR', 'PESO2', 'Resultado2')
            return _group(frame, columnas, [pl.len().alias('Registros'),
                _divide(_sum(pl.col(num)), _sum(pl.col(den))).alias(result)])
        raise ErrorDatos('Los agregados corresponden a Planes Operativos, Estrategias o Matriz Objetivos.')
