"""Consultas del tablero: mismas expresiones y filtros recuperados del PBIX.

Lee Parquet de una versión fija. Solo materializa agregados o una página del
detalle. La actualización y las fórmulas del modelo siguen en actualizar_planes.
"""
from dataclasses import dataclass, field
import json
from pathlib import Path

import polars as pl

from modelo_consulta import ErrorDatos, ModeloPowerBI, METAS, _group, _sum, _divide

ROOT = Path(__file__).resolve().parent
MARCA = '__filtro_tablero__'


def cargar_definicion():
    return json.loads((ROOT / 'reporte_powerbi.json').read_text(encoding='utf-8'))


def clave_selector(pagina, visual):
    sync = visual.get('sync') or {}
    return 'sync:' + sync['groupName'] if sync.get('filterChanges') and sync.get('groupName') else pagina['id'] + ':' + visual['id']


def valores_guardados(visual):
    conditions = visual.get('defaults', [])
    return [row[0] for item in conditions if item['operator'] == 'In' and len(item['fields']) == 1 for row in item['values']]


def condicion_in(campo, valores):
    return {'operator': 'In', 'fields': [{k: campo[k] for k in ('kind', 'table', 'column')}],
            'values': [[value] for value in valores]}


def condiciones_pagina(pagina, selecciones=None, omitir=None, omitir_base=None):
    result = []
    for index, condition in enumerate(pagina['filters']):
        if index == omitir_base:
            continue
        key = pagina['id'] + ':base:' + str(index)
        expression = condition['expression'] if condition['operator'] == 'Not' else condition
        if selecciones is not None and key in selecciones and expression['operator'] == 'In' and len(expression['fields']) == 1:
            if selecciones[key]:
                replacement = condicion_in(expression['fields'][0], selecciones[key])
                result.append({'operator': 'Not', 'expression': replacement} if condition['operator'] == 'Not' else replacement)
        else:
            result.append(condition)
    for visual in pagina['visuals']:
        if visual['type'] != 'slicer' or visual['id'] == omitir:
            continue
        key = clave_selector(pagina, visual)
        values = (selecciones or {}).get(key, valores_guardados(visual))
        if values:
            result.append(condicion_in(visual['groups'][0], values))
    return result


def leer_corte(carpeta):
    root = Path(carpeta).expanduser().resolve()
    pointer = root / 'actual.json'
    if not pointer.is_file():
        raise ErrorDatos('El corte de datos no está disponible. Contacta al administrador del tablero.')
    manifest = json.loads(pointer.read_text(encoding='utf-8'))
    # Conservar la versión y las rutas en la clave de caché evita mezclar cargas.
    return json.dumps({'version': manifest['version'], 'tablas': manifest['tablas'],
                       'actualizado_utc': manifest.get('actualizado_utc'),
                       'origen': manifest.get('origen', 'IBM i + Excel')}, ensure_ascii=False, sort_keys=True)


def modelo_corte(carpeta, corte):
    root = Path(carpeta).expanduser().resolve()
    tables = {}
    for name, relative in json.loads(corte)['tablas'].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ErrorDatos('La carga cambió o contiene una ruta inválida. Pulsa Recargar datos.')
        tables[name] = pl.scan_parquet(path)
    return ModeloPowerBI(tables)


def _campos_condicion(condition):
    if condition['operator'] == 'Not':
        return _campos_condicion(condition['expression'])
    if condition['operator'] != 'In':
        raise ErrorDatos('Se encontró una condición del reporte que no está implementada.')
    return condition['fields']


def _expresion_filtro(condition, schema):
    if condition['operator'] == 'Not':
        return ~_expresion_filtro(condition['expression'], schema)
    fields = condition['fields']
    clauses = []
    for row in condition['values']:
        parts = []
        if len(row) != len(fields):
            raise ErrorDatos('El filtro contiene una combinación incompleta.')
        for field, value in zip(fields, row):
            column = field['column']
            expr = pl.col(column)
            if value is None:
                parts.append(expr.is_null())
                continue
            if schema[column] == pl.String:
                expr, value = expr.str.to_lowercase(), str(value).lower()
            parts.append((expr == value).fill_null(False))
        clauses.append(pl.all_horizontal(parts))
    return pl.any_horizontal(clauses) if clauses else pl.lit(False)


def _identidad(field):
    return field['kind'], field.get('table'), field.get('column'), field.get('function')


def _meta():
    return pl.when(pl.col('Trimestre').n_unique() == 1).then(
        pl.col('Trimestre').first().str.to_lowercase().replace_strict(
            {k.lower(): v for k, v in METAS.items()}, default=None, return_dtype=pl.Float64)).otherwise(None)


def _promedio_tabular(value):
    """Acumulación secuencial contrastada con AVERAGE en Analysis Services.

    La media compensada de Polars puede cruzar 90/95 % por una ULP y cambiar
    el icono de un registro cuyo DAX original queda justo bajo el umbral.
    """
    valid = value.drop_nulls().cast(pl.Float64)
    return valid.cum_sum().last() / valid.count()


def _agregado(field, schema):
    column = field['column']
    if field['kind'] == 'Measure':
        if column == 'prueba':
            raise ErrorDatos('La medida prueba no tiene fórmula en el PBIX y permanece bloqueada.')
        if column == 'Meta Trim':
            return _meta()
        if column == '% Cumplimiento':
            return _divide(_promedio_tabular(pl.col('CALIFICACION')), _meta(), 0.)
        if column == 'Tareas 2024':
            return pl.col('TAREAS').count().cast(pl.Int64) - 2
        if column in {'Resultado', 'Resultado2'}:
            num, den = ('valor', 'Peso') if column == 'Resultado' else ('VALOR', 'PESO2')
            return _divide(_sum(pl.col(num)), _sum(pl.col(den)))
        if column == 'Hora Actualización':
            return pl.col('Fecha Actualización').max() - pl.duration(hours=5)
        raise ErrorDatos(f'Medida no inventariada: {column}')
    value = pl.col(column)
    function = field['function']
    if function == 0:
        return _sum(value)
    if function == 1:
        return _promedio_tabular(value)
    if function == 2:
        value = value.str.to_lowercase() if schema[column] == pl.String else value
        return pl.when(pl.len() > 0).then(value.n_unique().cast(pl.Int64)).otherwise(None)
    if function == 5:
        return pl.when(value.count() > 0).then(value.count().cast(pl.Int64)).otherwise(None)
    if function in {3, 4, 6}:
        return {3: value.min, 4: value.max, 6: value.median}[function]()
    raise ErrorDatos(f'Agregación no implementada: {function}')


def _referencias_regla(condition):
    refs = []
    if isinstance(condition, dict):
        if condition.get('kind') in {'Measure', 'Aggregation'}:
            refs.append(condition)
        for child in condition.values():
            if isinstance(child, dict):
                refs.extend(_referencias_regla(child))
    return refs


def _valor_regla(node, aliases, current, limites=None):
    if node.get('kind') == 'Literal':
        return pl.lit(node['value'])
    if node.get('kind') == 'RangePercent':
        if limites is not None:
            low, high = limites[current]
            return pl.lit(None if low is None or high is None else low + (high - low) * node['percent'])
        value = pl.col(current)
        return value.min() + (value.max() - value.min()) * node['percent']
    return pl.col(aliases[_identidad(node)]).fill_null(0.)


def _regla(condition, aliases, current, limites=None):
    op = condition['operator']
    if op in {'And', 'Or'}:
        a, b = _regla(condition['left'], aliases, current, limites), _regla(condition['right'], aliases, current, limites)
        return a & b if op == 'And' else a | b
    a, b = _valor_regla(condition['left'], aliases, current, limites), _valor_regla(condition['right'], aliases, current, limites)
    return {'>=': a >= b, '>': a > b, '<': a < b, '<=': a <= b, '=': a == b, '<>': a != b}[op]


def _estado_regla(rule, aliases, limites=None):
    relative = 'RangePercent' in json.dumps(rule)
    labels = {'CircleHigh': 'Alto' if relative else 'Cumple', 'SignMedium': 'Medio' if relative else 'En seguimiento', 'SignLow': 'Bajo'}
    expression = None
    for case in rule['cases']:
        clause = _regla(case['condition'], aliases, rule['target'], limites)
        label = labels.get(case['value'].get('value'), str(case['value'].get('value')))
        expression = pl.when(clause).then(pl.lit(label)) if expression is None else expression.when(clause).then(pl.lit(label))
    return expression.otherwise(pl.lit('Sin dato')) if expression is not None else pl.lit('Sin dato')


@dataclass
class Vista:
    datos: pl.DataFrame
    total: int
    totales: dict
    grupos: list
    valores: list
    estados: list
    estados_totales: dict = field(default_factory=dict)


class MotorReporte:
    def __init__(self, modelo):
        self.modelo = modelo

    def contexto(self, condiciones=()):
        if not condiciones:
            return self.modelo, {}
        tables = dict(self.modelo._tablas)
        context = {}
        for condition in condiciones:
            fields = _campos_condicion(condition)
            entities = {f['table'] for f in fields}
            if len(entities) != 1:
                raise ErrorDatos('Un filtro combina tablas sin una relación definida.')
            entity = next(iter(entities))
            if entity not in tables:
                raise ErrorDatos(f'No se encontró la tabla {entity}.')
            schema = tables[entity].collect_schema()
            if any(f['column'] not in schema for f in fields):
                raise ErrorDatos(f'El filtro contiene columnas desconocidas de {entity}.')
            tables[entity] = tables[entity].filter(_expresion_filtro(condition, schema)).with_columns(pl.lit(True).alias(MARCA))
            # La marca activa la propagación original uno->muchos, también en
            # filtros NOT o BLANK. No crea relaciones ni retropropaga filtros.
            context[entity] = {MARCA: [True]}
        return ModeloPowerBI(tables), context

    def opciones(self, tabla, columna, condiciones=()):
        model, context = self.contexto(condiciones)
        frame = model.tabla(tabla, context)
        schema = frame.collect_schema()
        value = pl.col(columna)
        result = (_group(frame, [columna], []) if schema[columna] == pl.String else frame.select(columna).unique())
        return result.select(value).sort(columna, nulls_last=True).collect(engine='streaming')[columna].to_list()

    def consultar(self, visual, condiciones=(), nivel=None, limite=100, offset=0):
        if limite < 1 or limite > 5000 or offset < 0:
            raise ErrorDatos('La paginación debe usar de 1 a 5000 filas y un desplazamiento positivo.')
        groups = list(visual['groups'])
        if visual['type'] == 'pivotTable':
            default = max(1, sum(bool(g['active']) for g in groups))
            depth = default if nivel is None else nivel
            if not 1 <= depth <= len(groups):
                raise ErrorDatos('Nivel de desglose inválido.')
            groups = groups[:depth]
        values = visual['values']
        entities = {f['table'] for f in groups + values}
        if len(entities) != 1:
            raise ErrorDatos('El visual debe usar los campos de la tabla original.')
        entity = next(iter(entities))
        model, context = self.contexto(list(condiciones) + visual['filters'])
        frame = model.tabla(entity, context)
        schema = frame.collect_schema()
        expressions = [_agregado(f, schema).alias(f['alias']) for f in values]
        aliases = {_identidad(f): f['alias'] for f in groups + values}
        for index, rule in enumerate(visual['rules']):
            for case in rule['cases']:
                for field in _referencias_regla(case['condition']):
                    key = _identidad(field)
                    if key not in aliases:
                        alias = f'__regla_{len(aliases)}'
                        expressions.append(_agregado(field, schema).alias(alias))
                        aliases[key] = alias
        if groups:
            output = _group(frame, [g['column'] for g in groups], expressions).rename({g['column']: g['alias'] for g in groups})
            if values:
                output = output.filter(pl.any_horizontal([pl.col(v['alias']).is_not_null() for v in values]))
        else:
            output = frame.select(expressions)
        states = []
        for rule in visual['rules']:
            current = rule['target']
            alias = 'estado_' + current
            if alias in states:
                continue
            output = output.with_columns(_estado_regla(rule, aliases).alias(alias))
            states.append(alias)
        sorting, descending = [], []
        for sort in visual['sort']:
            alias = aliases.get(_identidad(sort['field']))
            if alias and alias not in sorting:
                sorting.append(alias)
                descending.append(sort['descending'])
        if not sorting:
            sorting = [g['alias'] for g in groups]
            descending = [False] * len(sorting)
        if sorting:
            output = output.sort(sorting, descending=descending, nulls_last=False, maintain_order=True)
        count = output.select(pl.len()).collect(engine='streaming').item()
        public = [f['alias'] for f in groups + values] + states
        data = output.select(public).slice(offset, limite).collect(engine='streaming')
        totals, total_states = {}, {}
        if values:
            total_output = frame.select(expressions)
            seen = set()
            for rule in visual['rules']:
                alias = 'estado_' + rule['target']
                if alias in seen:
                    continue
                seen.add(alias)
                limits = None
                if 'RangePercent' in json.dumps(rule):
                    target = rule['target']
                    bounds = output.select(pl.col(target).min().alias('min'), pl.col(target).max().alias('max')).collect().row(0)
                    limits = {target: bounds}
                total_output = total_output.with_columns(_estado_regla(rule, aliases, limits).alias(alias))
            total_row = total_output.collect(engine='streaming').row(0, named=True)
            totals = {value['alias']: total_row[value['alias']] for value in values}
            total_states = {name: total_row[name] for name in seen}
        return Vista(data, count, totals, groups, values, states, total_states)

    def explorar(self, tabla, columnas, buscar='', limite=100, offset=0):
        if not 1 <= limite <= 500 or offset < 0:
            raise ErrorDatos('Paginación de detalle inválida.')
        frame = self.modelo.tabla(tabla)
        schema = frame.collect_schema()
        if not columnas or set(columnas) - set(schema):
            raise ErrorDatos('Selecciona columnas existentes.')
        if buscar.strip():
            text = [pl.col(c).str.to_lowercase().str.contains(buscar.strip().lower(), literal=True).fill_null(False)
                    for c, dtype in schema.items() if dtype == pl.String]
            frame = frame.filter(pl.any_horizontal(text) if text else pl.lit(False))
        total = frame.select(pl.len()).collect(engine='streaming').item()
        return frame.select(columnas).slice(offset, limite).collect(engine='streaming'), total
