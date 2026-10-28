"""Tablero ejecutivo del reporte original. Abrir: python -m streamlit run app.py"""
from datetime import date, datetime
from dataclasses import replace
from functools import partial
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import textwrap

os.environ.setdefault('POLARS_MAX_THREADS', '2')
import pandas as pd
import plotly.graph_objects as go
import polars as pl
import streamlit as st

import modelo_consulta as fuente
import ui_tablero as ui
from estructura_tablero import ESPACIOS, MODOS, espacio_de
from graficos_ejecutivos import construir_comparacion
from matriz_jerarquica import construir_matriz, id_nodo, HTML as MATRIZ_HTML, CSS as MATRIZ_CSS, JS as MATRIZ_JS
from acceso_tablero import exigir_acceso, mostrar_sesion
from cliente_actualizacion import puede_administrar, panel_administrativo
from consultas_tablero import (ROOT, ErrorDatos, MotorReporte, Vista, cargar_definicion, clave_selector,
    condicion_in, condiciones_pagina, leer_corte, modelo_corte, valores_guardados)

MATRIZ_PROCESOS = st.components.v2.component('matriz_resultados_powerbi', html=MATRIZ_HTML, css=MATRIZ_CSS, js=MATRIZ_JS)

AZUL, DORADO = '#07529A', '#997512'
TINTA, SECUNDARIO, BORDE = '#172D47', '#52647A', '#E2E8F0'
COLORES = {'Cumple': '#147565', 'Alto': '#147565', 'En seguimiento': '#986600',
           'Medio': '#986600', 'Bajo': '#B53C50', 'Sin dato': '#52647A'}
ETIQUETAS = {'ANO': 'Año del reporte', 'Año': 'Año de inicio', 'AREA': 'Área',
    'PROCESO': 'Proceso de origen', 'Proceso Final': 'Proceso', 'PROBOPR': 'Problema',
    'ESTRATEG': 'Estrategia', 'ACTIVID': 'Actividad', 'META': 'Meta', 'TAREAS': 'Tarea',
    'FECINICIAL': 'Fecha inicial', 'FECFINAL': 'Fecha final', 'RESPONSABLE': 'Responsable',
    'RECURSOS': 'Recursos', 'INDICADOR': 'Indicador', 'RESREAL': 'Resultado real',
    'EJECUCION': 'Ejecución', 'CRONOGRAMA': 'Cronograma', 'LOGMETA': 'Logro de meta',
    'FACTLIM': 'Factor limitante', 'PERIODO': 'Período', 'CALIFICACION': 'Calificación',
    'ESTADO': 'Estado', 'OBSESTADO': 'Observaciones del estado', 'Filtro': 'Aplicabilidad',
    'Trimestre Incial': 'Trimestre inicial', 'llave': 'Clave'}
VISTAS = {
    'Menu': ('Inicio', 'inicio', 'space_dashboard', 'El punto de partida para consultar los resultados institucionales.'),
    'Área': ('Resultados por área', 'areas', 'domain', 'Compara la calificación de las áreas y consulta el detalle de sus resultados.'),
    'Proceso': ('Resultados por proceso', 'procesos', 'account_tree', 'Revisa el desempeño de los procesos y profundiza en sus actividades.'),
    'Proceso y Tareas': ('Seguimiento de tareas', 'seguimiento-tareas', 'checklist', 'Consulta actividades, metas y tareas con sus resultados de cumplimiento.'),
    'Factores Limitantes': ('Factores limitantes', 'factores-limitantes', 'report', 'Identifica las situaciones que afectan el desarrollo de las actividades.'),
    'Plan Operativo': ('Plan operativo', 'plan-operativo', 'assignment', 'Explora la planeación, las responsabilidades y los recursos de cada actividad.'),
    'Procesos Pendientes': ('Procesos pendientes', 'procesos-pendientes', 'pending_actions', 'Ubica los procesos y las tareas que requieren seguimiento.'),
    'Actividades/Tareas': ('Actividades y tareas', 'actividades-tareas', 'format_list_bulleted', 'Consulta la distribución de actividades y tareas por proceso y por área.'),
    'Tareas Pendientes': ('Tareas pendientes', 'tareas-pendientes', 'task', 'Revisa el detalle de las actividades y tareas pendientes.'),
    'Estrategias por Áreas': ('Estrategias por área', 'estrategias-areas', 'hub', 'Relaciona los resultados de las áreas con los objetivos y las estrategias.'),
    'Objetivos': ('Objetivos institucionales', 'objetivos', 'flag', 'Consulta el avance de los objetivos y sus estrategias asociadas.'),
    'Estrategias': ('Estrategias', 'estrategias', 'route', 'Profundiza en los resultados de las estrategias institucionales.'),
    'Est No Relacionadas': ('Estrategias no relacionadas', 'estrategias-no-relacionadas', 'link_off', 'Consulta las estrategias y áreas de esta vista complementaria.'),
}


@st.cache_resource(max_entries=3)
def motor(carpeta, corte):
    return MotorReporte(modelo_corte(carpeta, corte))


@st.cache_data(ttl=300, max_entries=100)
def consulta(carpeta, corte, visual, conditions, depth=None, limit=100, offset=0):
    return motor(carpeta, corte).consultar(visual, conditions, depth, limit, offset)


@st.cache_data(ttl=300, max_entries=100)
def opciones(carpeta, corte, tabla, columna, conditions):
    return motor(carpeta, corte).opciones(tabla, columna, conditions)


@st.cache_data(ttl=300, max_entries=32)
def detalle(carpeta, corte, tabla, columnas, texto, limit, offset):
    return motor(carpeta, corte).explorar(tabla, columnas, texto, limit, offset)


@st.cache_data(max_entries=8, show_spinner=False)
def exportar_csv(carpeta, corte, visual, condiciones, nivel):
    """Solo se invoca al solicitar la exportación; conserva el corte y contexto."""
    chunks, offset = [], 0
    while True:
        result = motor(carpeta, corte).consultar(visual, condiciones, nivel, 5000, offset)
        chunks.append(result.datos)
        offset += result.datos.height
        if offset >= result.total:
            break
        if result.datos.is_empty():
            raise ErrorDatos('No se pudo completar la exportación de este corte.')
    data = pl.concat(chunks)
    for column, dtype in data.schema.items():
        if dtype == pl.String:
            # Evitar que una hoja de cálculo ejecute texto como fórmula.
            data = data.with_columns(pl.when(pl.col(column).str.contains(r'^[=+\-@\t\r]'))
                .then(pl.concat_str([pl.lit("'"), pl.col(column)])).otherwise(pl.col(column)).alias(column))
    labels = {f['alias']: f['label'] for f in result.grupos + result.valores}
    labels.update({name: 'Estado · ' + name.removeprefix('estado_') for name in result.estados})
    return data.rename(labels).write_csv(separator=';', include_bom=True).encode('utf-8')


@st.cache_data(max_entries=48, show_spinner=False)
def figura_comparacion(datos, total, grupos, valores, estados, meta, metrica, limite, orden, tipo):
    result = Vista(datos, total, {}, grupos, valores, estados)
    return construir_comparacion(result, meta=meta, metrica=metrica, limite=limite, orden=orden, tipo=tipo)


def nombre_medida(field):
    return {'CALIFICACION': 'Calificación promedio', '% Cumplimiento': 'Avance frente a la meta',
            'Resultado2': 'Resultado ponderado', 'Resultado': 'Resultado ponderado'}.get(field['column'], field['label'])


def rotulo(label):
    return {'Recusros': 'Recursos', 'Indiacdor': 'Indicador', 'CUMP': 'Calificación',
            'Cump': 'Calificación', 'Calif': 'Calificación', '% Ponderado Cump': 'Avance frente a la meta'}.get(label, label)


@st.cache_data(max_entries=3)
def cobertura(carpeta, corte):
    """Conteos descriptivos del corte completo; no sustituyen las medidas del informe."""
    planes = motor(carpeta, corte).modelo.tabla(fuente.PLAN)
    counts = planes.select(pl.len().alias('registros'),
        pl.col('AREA').str.to_lowercase().drop_nulls().n_unique().alias('areas'),
        pl.col('Proceso Final').str.to_lowercase().drop_nulls().n_unique().alias('procesos')).collect().row(0, named=True)
    years = planes.filter(pl.col('ANO').is_not_null()).group_by('ANO').len().sort('ANO').collect()
    return counts, years


@st.cache_data(max_entries=32, show_spinner=False)
def resumen_ejecutivo(carpeta, corte, pagina, ano, trimestre):
    """La portada consulta las mismas medidas y reglas del informe por área."""
    selecciones = {clave_selector(pagina, v): [ano if v['groups'][0]['column'] == 'ANO' else trimestre]
                  for v in pagina['visuals'] if v['type'] == 'slicer'}
    base = condiciones_pagina(pagina, selecciones)
    engine = motor(carpeta, corte)
    cards = [v for v in pagina['visuals'] if v['type'] == 'card']
    values = {v['values'][0]['column']: engine.consultar(v, base).datos.item(0, 'v0') for v in cards}
    table = next(v for v in pagina['visuals'] if v['type'] == 'pivotTable')
    areas = engine.consultar(table, base, limite=100).datos.sort('v0', descending=True, nulls_last=True)
    model, context = engine.contexto(base)
    weighted = model.medida('% Cumplimiento', context)
    records = model.tabla(fuente.PLAN, context).select(pl.len()).collect().item()
    return values['CALIFICACION'], values['Meta Trim'], weighted, areas, records


def datos_vista(pagina):
    return VISTAS.get(pagina['name'], (pagina['name'], pagina['id'], 'analytics', 'Consulta los resultados del informe.'))


@st.cache_data(show_spinner=False)
def logo_empresa():
    # Mantener el archivo original y evitar una petición adicional al servidor de medios.
    return 'data:image/jpeg;base64,' + base64.b64encode((ROOT / 'assets/comfamiliar.jpg').read_bytes()).decode('ascii')


def numero(value):
    return f'{value:,}'.replace(',', '.')


def formato(value, percentage=False):
    if value is None or isinstance(value, float) and not math.isfinite(value):
        return '—'
    if isinstance(value, (date, datetime)):
        return value.strftime('%d/%m/%Y %H:%M')
    if percentage:
        return f'{value:.2%}'.replace('.', ',')
    if isinstance(value, (int, float)):
        return numero(int(value)) if float(value).is_integer() else f'{value:.2f}'.replace('.', ',')
    return str(value)


def ir(pagina, hidden=False):
    st.session_state.pagina = pagina
    st.query_params['vista'] = st.session_state.get('rutas', {}).get(pagina, pagina)
    if hidden:
        st.session_state.mostrar_adicionales = True
    st.session_state.cruces = {}
    st.session_state.epoca_seleccion += 1
    name = st.session_state.get('nombres_paginas', {}).get(pagina)
    if name:
        group = espacio_de(name)
        st.session_state['ultimo_' + group['slug']] = pagina
        st.session_state['modo_' + group['slug']] = pagina


def abrir_espacio(slug):
    group = next(g for g in ESPACIOS if g['slug'] == slug)
    names = st.session_state.nombres_paginas
    default = next(key for key, name in names.items() if name == group['inicial'])
    ir(st.session_state.get('ultimo_' + slug, default))


def cambiar_modo(key):
    if st.session_state.get(key):
        ir(st.session_state[key])


def recargar_datos():
    limpiar_cruce(st.session_state.pagina)
    st.toast('Estás consultando el último corte disponible.', icon=':material/check_circle:')


def navegacion(definition):
    actual = st.session_state.pagina
    ui.marca(logo_empresa())
    name = st.session_state.nombres_paginas.get(actual)
    active = espacio_de(name)['slug'] if name else None
    st.caption('ESPACIOS DE GESTIÓN')
    for index, group in enumerate(ESPACIOS):
        st.button(group['nombre'], icon=f":material/{group['icono']}:", key='espacio_' + group['slug'],
            width='stretch', type='primary' if active == group['slug'] else 'tertiary',
            on_click=abrir_espacio, args=(group['slug'],))
    ui.pie_navegacion()
    st.caption('HERRAMIENTAS')
    st.button('Explorar datos', icon=':material/table_view:', key='nav_explorar', width='stretch',
        type='primary' if actual == 'explorar' else 'tertiary', on_click=ir, args=('explorar',))
    st.button('Recargar datos', icon=':material/refresh:', width='stretch', on_click=recargar_datos,
        help='Abre el último corte publicado. Los filtros se conservan.')


def encabezado(carpeta, corte, vista):
    stamp = motor(carpeta, corte).modelo.medida('Hora Actualización')
    ui.barra_superior(vista, formato(stamp))
    origin = json.loads(corte).get('origen', '')
    if origin.startswith('Referencia PBIX'):
        st.info('Conciliación: datos almacenados en el PBIX original. Este corte de referencia no representa la base actual.', icon=':material/compare:')


def titulo_pagina(pagina):
    _, _, _, description = datos_vista(pagina)
    group = espacio_de(pagina['name'])
    ui.etiqueta_hero('GESTIÓN INSTITUCIONAL / ' + group['nombre'].upper())
    st.title(group['titulo'])
    st.write(description)


def modos_analisis(pagina, definition):
    group = espacio_de(pagina['name'])
    if len(group['vistas']) < 2:
        return
    pages = {page['name']: page for page in definition['pages']}
    ids = [pages[name]['id'] for name in group['vistas']]
    key = 'modo_' + group['slug']
    st.session_state[key] = pagina['id']
    labels = {page['id']: MODOS[page['name']] for page in pages.values()}
    st.segmented_control('Modo de análisis', ids, format_func=labels.get, key=key, label_visibility='collapsed',
        on_change=cambiar_modo, args=(key,), width='stretch')


def encabezado_seccion(title, description=None, icon='analytics'):
    st.header(f':material/{icon}: {title}', anchor=False)
    if description:
        st.caption(description)


def guardar_seleccion(key, widget):
    st.session_state.selecciones[key] = list(st.session_state[widget])
    st.session_state.cruces = {}
    st.session_state.epoca_seleccion += 1


def restaurar(pagina, limpiar=False):
    for visual in pagina['visuals']:
        if visual['type'] == 'slicer':
            st.session_state.selecciones[clave_selector(pagina, visual)] = [] if limpiar else valores_guardados(visual)
    for index, condition in enumerate(pagina['filters']):
        expr = condition['expression'] if condition['operator'] == 'Not' else condition
        if expr['operator'] == 'In' and len(expr['fields']) == 1:
            st.session_state.selecciones[pagina['id'] + ':base:' + str(index)] = [] if limpiar else [row[0] for row in expr['values']]
    for key in list(st.session_state):
        if str(key).startswith(('filtro_' + pagina['id'], 'base_' + pagina['id'])):
            del st.session_state[key]
    st.session_state.cruces = {}
    st.session_state.epoca_seleccion += 1


def guardar_fila(pagina, visual, widget, grupos, registros):
    selected = st.session_state[widget]['selection']['rows']
    if not selected or not 0 <= selected[0] < len(registros):
        if st.session_state.cruces.get(pagina, {}).get('source') == visual:
            st.session_state.cruces.pop(pagina, None)
        return
    row = registros[selected[0]]
    conditions = [condicion_in(field, [row[field['alias']]]) for field in grupos]
    st.session_state.cruces[pagina] = {'source': visual, 'conditions': conditions,
        'label': ' / '.join(str(row[f['alias']]) if row[f['alias']] is not None else '(En blanco)' for f in grupos)}


def guardar_barra(pagina, visual, widget, campo):
    points = st.session_state[widget]['selection']['points']
    if points:
        value = points[0]['customdata'][0]
        st.session_state.cruces[pagina] = {'source': visual, 'conditions': [condicion_in(campo, [value])],
            'label': str(value) if value is not None else '(En blanco)'}
    elif st.session_state.cruces.get(pagina, {}).get('source') == visual:
        st.session_state.cruces.pop(pagina, None)


def condiciones_visual(pagina, visual, base):
    cross = st.session_state.cruces.get(pagina['id'])
    return base + (cross['conditions'] if cross and cross['source'] != visual['id'] else [])


def limpiar_cruce(pagina):
    st.session_state.cruces.pop(pagina, None)
    st.session_state.epoca_seleccion += 1


def selector(carpeta, corte, pagina, visual):
    field = visual['groups'][0]
    key = clave_selector(pagina, visual)
    saved = st.session_state.selecciones.get(key, valores_guardados(visual))
    own_conditions = condiciones_pagina(pagina, st.session_state.selecciones, omitir=visual['id']) + visual['filters']
    available = opciones(carpeta, corte, field['table'], field['column'], own_conditions)
    # Mantener una selección guardada aunque la nueva carga no tenga registros.
    for value in saved:
        if value not in available:
            available.append(value)
    if field['column'] in {'ANO', 'Año'}:
        available = sorted([v for v in available if v is not None], reverse=True) + ([None] if None in available else [])
    widget = 'filtro_' + pagina['id'] + visual['id']
    st.session_state.setdefault(widget, saved)
    label = field['label']
    st.multiselect(label, available, key=widget, placeholder='Todos',
        format_func=lambda value: '(En blanco)' if value is None else str(value),
        on_change=guardar_seleccion, args=(key, widget))


def filtros_pagina(carpeta, corte, pagina):
    slicers = [v for v in pagina['visuals'] if v['type'] == 'slicer']
    if not slicers and not pagina['filters']:
        return []
    priority = {'ANO': 0, 'Trimestre': 1, 'AREA': 2, 'Area': 2, 'Proceso Final': 3, 'PROCESO': 3}
    slicers = sorted(slicers, key=lambda v: priority.get(v['groups'][0]['column'], 4))
    common = slicers[:4]
    columns = st.columns([1] * len(common) + [.65], gap='medium', vertical_alignment='bottom')
    for column, visual in zip(columns, common):
        with column:
            selector(carpeta, corte, pagina, visual)
    with columns[-1]:
        settings = st.popover('Ajustes', icon=':material/tune:')
    with settings:
        for visual in slicers[4:]:
            selector(carpeta, corte, pagina, visual)
        for index, condition in enumerate(pagina['filters']):
            negative = condition['operator'] == 'Not'
            expr = condition['expression'] if negative else condition
            if expr['operator'] != 'In' or len(expr['fields']) != 1:
                continue
            field = expr['fields'][0]
            key = pagina['id'] + ':base:' + str(index)
            saved = st.session_state.selecciones.get(key, [row[0] for row in expr['values']])
            other = condiciones_pagina(pagina, st.session_state.selecciones, omitir_base=index)
            available = opciones(carpeta, corte, field['table'], field['column'], other)
            for value in saved:
                if value not in available:
                    available.append(value)
            widget = 'base_' + pagina['id'] + str(index)
            st.session_state.setdefault(widget, saved)
            label = ('Excluir · ' if negative else '') + {'ANO': 'Año de la página', 'CALIFICACION': 'Calificación'}.get(field['column'], field['column'])
            st.multiselect(label, available, key=widget, placeholder='Todos',
                format_func=lambda value: '(En blanco)' if value is None else str(value),
                help=f"Campo original: {field['table']}[{field['column']}]",
                on_change=guardar_seleccion, args=(key, widget))
        st.button('Restablecer', icon=':material/restart_alt:', on_click=restaurar, args=(pagina,))
        st.button('Limpiar filtros', icon=':material/filter_alt_off:', on_click=restaurar, args=(pagina, True))
    conditions = condiciones_pagina(pagina, st.session_state.selecciones)
    items = []
    for condition in conditions:
        negative = condition['operator'] == 'Not'
        expr = condition['expression'] if negative else condition
        if expr['operator'] == 'In' and len(expr['fields']) == 1:
            name = expr['fields'][0]['column']
            label = ('Excluir ' if negative else '') + ETIQUETAS.get(name, name)
            values = ', '.join('(En blanco)' if row[0] is None else str(row[0]) for row in expr['values'])
            items.append((label, values))
    ui.contexto_filtros(items)
    return conditions


def configuracion_columnas(fields, estados=()):
    configs = {}
    labels = {'Recusros': 'Recursos', 'Indiacdor': 'Indicador', 'CUMP': 'Cumplimiento',
              'Cump': 'Cumplimiento', 'Calif': 'Calificación', '% Ponderado Cump': 'Cumplimiento ponderado'}
    for field in fields:
        alias, label = field['alias'], field['label']
        label = labels.get(label, label)
        if field.get('percent'):
            if field['column'] == 'CALIFICACION':
                configs[alias] = st.column_config.ProgressColumn(label, min_value=0, max_value=1, format='percent', width='medium')
            else:
                configs[alias] = st.column_config.NumberColumn(label, format='percent')
        elif field['column'] in {'FECINICIAL', 'FECFINAL'}:
            configs[alias] = st.column_config.DatetimeColumn(label, format='DD/MM/YYYY')
        elif field['kind'] == 'Aggregation' and field['function'] in {2, 5}:
            configs[alias] = st.column_config.NumberColumn(label, format='localized')
        else:
            configs[alias] = st.column_config.Column(label, width='medium' if field['kind'] == 'Column' else 'small')
    for state in estados:
        configs[state] = st.column_config.TextColumn('Estado' if len(estados) == 1 else 'Estado · ' + state.removeprefix('estado_'))
    return configs


def grafico(result, pagina, visual, key, horizontal=False, meta=None, metrica=None, limite=12, orden='Mayor resultado'):
    if not result.grupos or not result.valores or result.total == 0:
        st.info('No hay datos para mostrar con estos filtros.')
        return
    group = result.grupos[0]
    tipo = 'puntos' if pagina['name'] == 'Proceso' or espacio_de(pagina['name'])['slug'] == 'estrategia' else 'barras'
    fig = figura_comparacion(result.datos, result.total, result.grupos, result.valores, result.estados,
                            meta, metrica, limite, orden, tipo)
    st.plotly_chart(fig, width='stretch', key=key, selection_mode='points',
        on_select=partial(guardar_barra, pagina['id'], visual['id'], key, group),
        config={'displayModeBar': False, 'scrollZoom': False})


def accion_matriz(widget, context_key, pagina, visual, tree):
    action = st.session_state.get(widget, {}).get('accion')
    if not isinstance(action, dict):
        return
    state = st.session_state[context_key]
    kind, identifier = action.get('tipo'), action.get('id')
    if kind == 'cerrar_todo':
        state['abiertos'] = {}
    elif kind == 'pagina_raiz':
        value = action.get('pagina')
        if type(value) is int and 1 <= value <= tree['paginas']:
            state['pagina'] = value
    elif identifier in tree['nodos']:
        path = tree['nodos'][identifier]
        if kind == 'alternar' and len(path) < len(visual['groups']):
            if identifier in state['abiertos']:
                state['abiertos'] = {key: value for key, value in state['abiertos'].items() if value[:len(path)] != path}
            else:
                state['abiertos'][identifier] = path
        elif kind == 'seleccionar':
            st.session_state.cruces[pagina['id']] = {'source': visual['id'],
                'conditions': [condicion_in(group, [value]) for group, value in zip(visual['groups'], path)],
                'label': ' / '.join('(En blanco)' if value is None else str(value) for value in path)}
            state['seleccion'] = identifier
        elif kind == 'pagina_hijo':
            value = action.get('pagina')
            pager = next((r for r in tree['filas'] if r['tipo'] == 'paginacion' and r['id'] == identifier), None)
            if pager and type(value) is int and 1 <= value <= pager['paginas']:
                state['paginas_hijo'][identifier] = value
    st.session_state[context_key] = state


def render_matriz_procesos(carpeta, corte, pagina, visual, conditions):
    fingerprint = hashlib.sha256(repr((corte, visual['id'], conditions)).encode('utf-8')).hexdigest()
    context_key = 'estado_matriz_' + fingerprint
    # Conservar el estado de la vista vigente, sin acumular contextos de filtros.
    previous = st.session_state.get('contexto_matriz_actual')
    if previous and previous != context_key:
        st.session_state.pop(previous, None)
    st.session_state.contexto_matriz_actual = context_key
    state = st.session_state.setdefault(context_key, {'abiertos': {}, 'paginas_hijo': {}, 'pagina': 1})
    tree = construir_matriz(partial(consulta, carpeta, corte), visual, conditions,
        abiertos=state['abiertos'], pagina=state['pagina'], paginas_hijo=state['paginas_hijo'])
    if not tree['total']:
        st.info('No hay procesos con resultados para estos filtros.')
        return
    selected = st.session_state.cruces.get(pagina['id'], {})
    tree['seleccion'] = state.get('seleccion') if selected.get('source') == visual['id'] else None
    widget = 'matriz_procesos_' + fingerprint
    MATRIZ_PROCESOS(data=tree, key=widget, on_accion_change=partial(accion_matriz, widget, context_key, pagina, visual, tree))
    st.caption('Abre «+» para consultar las actividades de cada proceso. Selecciona una fila para relacionar sus resultados. '
               'El total se recalcula sobre todos los registros; la clasificación utiliza el avance frente a la meta.')
    if st.button('Preparar CSV con procesos y actividades', icon=':material/file_download:', key='csv_matriz_' + fingerprint):
        st.session_state.exportacion_lista = {'firma': fingerprint,
            'datos': exportar_csv(carpeta, corte, visual, conditions, len(visual['groups']))}
    prepared = st.session_state.get('exportacion_lista', {})
    if prepared.get('firma') == fingerprint:
        st.download_button('Descargar procesos y actividades', prepared['datos'], file_name='procesos_actividades.csv',
            mime='text/csv', key='descargar_matriz_' + fingerprint)


def render_tabla(carpeta, corte, pagina, visual, base, meta=None):
    conditions = condiciones_visual(pagina, visual, base)
    fields = visual['groups']
    depth = None
    with st.container(border=False, key='resultado_' + pagina['id'] + visual['id']):
        heading = ' / '.join(f['label'] for f in fields[:1]) or 'Detalle'
        title = {'Plan Operativo': 'Plan de trabajo y responsables', 'Proceso y Tareas': 'Actividades, metas y tareas',
                 'Factores Limitantes': 'Factores que afectan la ejecución', 'Tareas Pendientes': 'Registros por calificar',
                 'Est No Relacionadas': 'Revisión de relaciones estratégicas'}.get(pagina['name'], 'Resultados por ' + heading.lower())
        encabezado_seccion(title, 'Compara los resultados y selecciona una fila para consultar su información completa.', 'table_chart')
        if pagina['name'] == 'Proceso' and visual['type'] == 'pivotTable':
            presentation = st.segmented_control('Presentación de procesos', ['Matriz expandible', 'Gráfico y tabla'],
                default='Matriz expandible', key='presentacion_' + pagina['id'], width='stretch')
            if presentation != 'Gráfico y tabla':
                render_matriz_procesos(carpeta, corte, pagina, visual, conditions)
                return
        if visual['type'] == 'pivotTable' and len(fields) > 1:
            default = max(1, sum(f['active'] for f in fields))
            with st.popover('Desglose del detalle', icon=':material/account_tree:'):
                depth = st.selectbox('Nivel de desglose', range(1, len(fields) + 1), index=default - 1,
                    format_func=lambda n: ' › '.join(f['label'] for f in fields[:n]), key='nivel_' + pagina['id'] + visual['id'])
        key = pagina['id'] + visual['id'] + str(depth)
        limit = 100
        page_key = 'pag_' + key
        page = max(1, int(st.session_state.get(page_key, 1)))
        result = consulta(carpeta, corte, visual, conditions, depth, limit, (page - 1) * limit)
        pages = max(1, math.ceil(result.total / limit))
        if page > pages:
            page = pages
            st.session_state[page_key] = page
            result = consulta(carpeta, corte, visual, conditions, depth, limit, (page - 1) * limit)
        if result.total == 0:
            st.info('No encontramos resultados con esta selección. Ajusta el año, el período o los demás filtros del informe.',
                icon=':material/filter_alt_off:')
            return
        if result.valores and visual['type'] == 'pivotTable':
            chart_visual = {**visual, 'id': visual['id'] + '_comparacion'}
            chart_conditions = condiciones_visual(pagina, chart_visual, base)
            summary = (result if len(result.grupos) == 1 and result.total == result.datos.height and conditions == chart_conditions
                       else consulta(carpeta, corte, visual, chart_conditions, 1, 1000, 0))
            summary = replace(summary, valores=[{**f, 'label': nombre_medida(f)} for f in summary.valores])
            if summary.total:
                metric = None
                with st.popover('Opciones de la comparación', icon=':material/tune:'):
                    if len(summary.valores) > 1 and any(f.get('percent') for f in summary.valores):
                        metric = st.segmented_control('Indicador de la comparación', [f['alias'] for f in summary.valores],
                            default=summary.valores[0]['alias'], format_func={f['alias']: f['label'] for f in summary.valores}.get,
                            key='medida_' + key)
                        metric = metric or summary.valores[0]['alias']
                    order = st.selectbox('Orden de comparación', ['Mayor resultado', 'Menor resultado', 'Orden del informe'], key='orden_' + key)
                    chart_limit = st.selectbox('Elementos visibles', [8, 12, 20], index=1, key='limite_' + key)
                primary = next((f for f in summary.valores if f['alias'] == metric), summary.valores[0])
                chart_meta = (1.0 if primary['column'] == '% Cumplimiento' else meta) if meta is not None and primary.get('percent') and primary['column'] in {'CALIFICACION', '% Cumplimiento'} else None
                graph, reading = st.columns([3, 1.15], gap='large')
                with graph:
                    grafico(summary, pagina, chart_visual, 'chart_' + key + str(st.session_state.epoca_seleccion),
                            horizontal=True, meta=chart_meta, metrica=metric, limite=chart_limit, orden=order)
                    st.caption(f'Mostrando {min(summary.datos.height, chart_limit)} de {summary.total} elementos. Selecciona una barra para relacionar el detalle.')
                with reading:
                    ui.lectura_comparacion(summary, primary, formato)
                st.divider()
        shown = result.datos.to_pandas()
        if result.estados:
            def tint(value):
                color = COLORES.get(value)
                background = {'Cumple': '#EAF5EF', 'Alto': '#EAF5EF', 'En seguimiento': '#FBF4E6',
                              'Medio': '#FBF4E6', 'Bajo': '#F9ECEF', 'Sin dato': '#EFF3F5'}.get(value, '#FFFFFF')
                return f'color: {color}; background-color: {background}; font-weight: 600' if color else ''
            shown = shown.style.map(tint, subset=result.estados)
        widget = 'tabla_' + key + str(st.session_state.epoca_seleccion)
        st.caption(f'{numero(result.total)} resultados · página {page} de {pages} · selecciona una fila para ver el detalle')
        column_order = [f['alias'] for f in result.grupos + result.valores] + result.estados
        if len(result.grupos) > 3:
            preferred = {'ACTIVID', 'TAREAS', 'RESPONSABLE', 'FECFINAL'}
            defaults = [f['alias'] for f in result.grupos if f['column'] in preferred]
            if pagina['name'] == 'Factores Limitantes':
                defaults = [f['alias'] for name in ('FACTLIM', 'TAREAS', 'ACTIVID') for f in result.grupos if f['column'] == name]
            defaults = defaults or [f['alias'] for f in result.grupos[:4]]
            labels = {f['alias']: rotulo(f['label']) for f in result.grupos + result.valores}
            with st.popover('Columnas del detalle', icon=':material/view_column:'):
                visible = st.multiselect('Columnas visibles', [f['alias'] for f in result.grupos], default=defaults,
                    format_func=labels.get, key='columnas_detalle_' + key)
            if not visible:
                st.info('Selecciona al menos una columna en «Columnas del detalle».')
                return
            column_order = visible + [f['alias'] for f in result.valores] + result.estados
        event = st.dataframe(shown, hide_index=True, width='stretch', row_height=42, height=min(590, max(180, result.datos.height * 42 + 45)),
            column_config=configuracion_columnas(result.grupos + result.valores, result.estados), column_order=column_order, key=widget,
            selection_mode='single-row', on_select=partial(guardar_fila, pagina['id'], visual['id'], widget, result.grupos, result.datos.to_dicts()))
        if result.totales:
            st.markdown('**Total de la selección** · ' + '  ·  '.join(f"{f['label']}: **{formato(result.totales[f['alias']], f.get('percent'))}**" for f in result.valores))
        if pages > 1:
            st.number_input('Página de resultados', min_value=1, max_value=pages, value=page, step=1, key=page_key)
            st.caption(f'Página {page} de {pages} · hasta {limit} resultados por página')
        signature = hashlib.sha256(repr((corte, visual['id'], conditions, depth)).encode('utf-8')).hexdigest()
        if st.button('Preparar CSV de la selección completa', icon=':material/file_download:', key='preparar_csv_' + key):
            with st.spinner('Preparando los resultados filtrados…'):
                st.session_state.exportacion_lista = {'firma': signature, 'datos': exportar_csv(carpeta, corte, visual, conditions, depth)}
        prepared = st.session_state.get('exportacion_lista', {})
        if prepared.get('firma') == signature:
            st.download_button('Descargar CSV', prepared['datos'], file_name='resultados_planeacion.csv', mime='text/csv',
                key='descargar_csv_' + key, help='Incluye todos los resultados filtrados y sus columnas. Los porcentajes conservan su valor numérico de origen.')
        if event.selection.rows and 0 <= event.selection.rows[0] < result.datos.height:
            selected = result.datos.row(event.selection.rows[0], named=True)
            ui.ficha_registro([(rotulo(field['label']), formato(selected[field['alias']], field.get('percent')))
                              for field in result.grupos + result.valores])


def portada(definition, carpeta, corte):
    counts, years = cobertura(carpeta, corte)
    ui.etiqueta_hero('INTELIGENCIA PARA LA GESTIÓN')
    st.title('Visión ejecutiva')
    st.write('Una perspectiva clara para orientar las decisiones de la institución.')
    area = next(p for p in definition['pages'] if p['name'] == 'Área')
    slicers = {v['groups'][0]['column']: v for v in area['visuals'] if v['type'] == 'slicer'}
    available = years['ANO'].reverse().to_list()
    with st.container(key='contexto_ejecutivo'):
        label, year_column, quarter_column = st.columns([1.5, 1, 1.4], vertical_alignment='center')
        with label:
            ui.contexto_periodo()
        with year_column:
            default = next(iter(valores_guardados(slicers['ANO'])), available[0] if available else None)
            ano = st.selectbox('Año de análisis', available, index=available.index(default) if default in available else 0,
                              key='ejecutivo_ano')
        with quarter_column:
            quarters = list(fuente.TRIMESTRES)
            default_quarter = next(iter(valores_guardados(slicers['Trimestre'])), quarters[0])
            trimestre = st.selectbox('Trimestre de análisis', quarters, index=quarters.index(default_quarter),
                                    key='ejecutivo_trimestre')
    if ano is not None:
        average, target, weighted, areas, records = resumen_ejecutivo(carpeta, corte, area, ano, trimestre)
        ui.panel_ejecutivo(ano, trimestre, average, target, weighted, areas.to_dicts(), records)
    st.space('small')
    ui.seccion_editorial('01', 'Explora la gestión', 'Del panorama institucional al detalle de cada resultado.')
    reports, history = st.columns([1.6, 1], gap='large')
    with reports:
        featured = ('Área', 'Proceso', 'Plan Operativo', 'Proceso y Tareas')
        for start in (0, 2):
            columns = st.columns(2, gap='medium')
            for column, name in zip(columns, featured[start:start + 2]):
                page = next(p for p in definition['pages'] if p['name'] == name)
                title, slug, icon, description = datos_vista(page)
                with column.container(border=False, height='stretch', key='acceso_' + slug):
                    icon_name = {'Área': 'areas', 'Proceso': 'procesos', 'Plan Operativo': 'registros', 'Proceso y Tareas': 'registros'}[name]
                    ui.titulo_acceso(icon_name, title)
                    st.caption(description)
                    button_label = {'Área': 'Ver áreas', 'Proceso': 'Ver procesos',
                        'Plan Operativo': 'Ver plan operativo', 'Proceso y Tareas': 'Ver tareas'}[name]
                    st.button(button_label, icon=':material/arrow_forward:', icon_position='right',
                        key='portada_' + page['id'], on_click=ir, args=(page['id'],), width='stretch')
    with history:
        with st.container(border=False, key='cobertura_historica'):
            ui.titulo_acceso('anos', 'Memoria institucional')
            st.caption('Registros publicados por año. Cobertura completa del histórico.')
            if years.height:
                fig = go.Figure(go.Bar(x=years['len'].to_list(), y=years['ANO'].cast(pl.String).to_list(),
                    orientation='h', marker_color=AZUL, marker_line_width=0,
                    text=[numero(value) for value in years['len']], textposition='outside', cliponaxis=False,
                    hovertemplate='Año %{y}<br>%{x:,.0f} registros<extra></extra>'))
                fig.update_layout(height=250, margin=dict(l=0, r=55, t=8, b=16),
                    font=dict(family='Segoe UI, Arial, sans-serif', size=14, color=TINTA),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', bargap=.5,
                    showlegend=False, dragmode=False, transition_duration=0)
                fig.update_xaxes(visible=False, range=[0, max(years['len']) * 1.25])
                fig.update_yaxes(type='category', showgrid=False, ticks='', fixedrange=True)
                st.plotly_chart(fig, width='stretch', config={'displayModeBar': False, 'staticPlot': False})
            else:
                st.caption('El corte disponible no contiene registros con año informado.')
        st.button('Explorar los datos', icon=':material/table_view:', on_click=ir, args=('explorar',),
            width='stretch', key='portada_explorar')
    ui.tarjetas_cobertura(counts, years.height)
    st.caption('El resumen usa los registros «Aplica» del período seleccionado y las fórmulas del informe por área. '
               'Cada informe conserva sus filtros propios. La cobertura histórica describe todos los años publicados.')


def explorar(carpeta, corte):
    st.title('Explorar tablas')
    st.write('Consulta los registros del corte, elige las columnas y encuentra información específica.')
    model = motor(carpeta, corte).modelo
    names = [fuente.PLAN] + [n for n in model.tablas if n != fuente.PLAN]
    with st.container(border=False, key='explorador_tabla'):
        tabla = st.selectbox('Tabla de consulta', names, key='tabla_explorar')
    schema = model.tabla(tabla).collect_schema()
    defaults = [n for n in ('ID', 'ANO', 'Trimestre', 'AREA', 'Proceso Final', 'ACTIVID', 'TAREAS', 'CALIFICACION') if n in schema]
    with st.expander('Personalizar columnas', icon=':material/view_column:'):
        columns = st.multiselect('Columnas visibles', list(schema), default=defaults or list(schema), key='columnas_' + tabla,
            format_func=lambda name: ETIQUETAS.get(name, name))
    with st.form('buscar_tabla', border=False):
        search, action = st.columns([5, 1], vertical_alignment='bottom')
        with search:
            text = st.text_input('Buscar en todos los registros', placeholder='Escribe una tarea, un proceso o un responsable…')
        with action:
            st.form_submit_button('Buscar', icon=':material/search:', type='primary', width='stretch')
    if not columns:
        st.info('Selecciona al menos una columna.')
        return
    key = 'pagina_explorar'
    page = max(1, int(st.session_state.get(key, 1)))
    data, total = detalle(carpeta, corte, tabla, columns, text, 100, (page - 1) * 100)
    pages = max(1, math.ceil(total / 100))
    if page > pages:
        page = pages
        st.session_state[key] = page
        data, total = detalle(carpeta, corte, tabla, columns, text, 100, (page - 1) * 100)
    st.caption(f'{numero(total)} registros encontrados · página {page} de {pages} · hasta 100 filas por página')
    configs = {}
    for name in columns:
        label = ETIQUETAS.get(name, name)
        if name == 'CALIFICACION':
            configs[name] = st.column_config.NumberColumn(label, format='percent')
        elif name in {'FECINICIAL', 'FECFINAL'}:
            configs[name] = st.column_config.DatetimeColumn(label, format='DD/MM/YYYY')
        else:
            configs[name] = st.column_config.Column(label, width='large' if name in {'ACTIVID', 'TAREAS'} else None)
    st.dataframe(data, hide_index=True, width='stretch', height=580, column_config=configs)
    st.number_input('Página de datos', min_value=1, max_value=pages, value=page, step=1, key=key)


def informe(carpeta, corte, pagina, base, definition):
    meta = None
    cross = st.session_state.cruces.get(pagina['id'])
    if cross:
        with st.container(horizontal=True, vertical_alignment='center'):
            st.badge('Selección · ' + cross['label'], icon=':material/filter_alt:', color='blue')
            st.button('Quitar selección', icon=':material/close:', on_click=limpiar_cruce, args=(pagina['id'],))
    cards = sorted([v for v in pagina['visuals'] if v['type'] == 'card'], key=lambda v: v['position']['x'])
    if cards:
        indicators = []
        for visual in cards:
            result = consulta(carpeta, corte, visual, condiciones_visual(pagina, visual, base))
            field = visual['values'][0]
            value = result.datos[field['alias']][0]
            if field['column'] == 'Meta Trim':
                meta = value
            own_quarter = next((row[0] for c in visual['filters'] if c['operator'] == 'In' and c['fields'][0]['column'] == 'Trimestre' for row in c['values']), None)
            note = 'Filtro propio: ' + own_quarter if own_quarter else ('Meta del trimestre seleccionado' if field['column'] == 'Meta Trim' else 'Resultado del contexto seleccionado')
            displayed = formato(value, field.get('percent'))
            label = nombre_medida(field)
            if pagina['name'] == 'Proceso' and field.get('percent') and value is not None:
                displayed = f'{value:.1%}'.replace('.', ',')
                label = field['label']
            indicators.append((label, displayed, note))
        ui.indicadores_informe(indicators)
    body = sorted([v for v in pagina['visuals'] if v['type'] in {'pivotTable', 'tableEx', 'clusteredColumnChart'}], key=lambda v: (v['position']['y'], v['position']['x']))
    for visual in body:
        if visual['type'] == 'clusteredColumnChart':
            # La comparación usa los agregados y estados de la matriz equivalente.
            continue
        else:
            render_tabla(carpeta, corte, pagina, visual, base, meta=meta)
    links = [v for v in pagina['visuals'] if v['navigation'] and v['text'] and v['navigation'][0].get('navigationSection') != definition['pages'][0]['id']]
    if links:
        with st.container(horizontal=True):
            for visual in links:
                target = visual['navigation'][0].get('navigationSection')
                destination = next((p for p in definition['pages'] if p['id'] == target), None)
                if destination:
                    st.button(' '.join(visual['text']), key='enlace_' + pagina['id'] + visual['id'], icon=':material/arrow_forward:',
                        on_click=ir, args=(target, destination['hidden']))


def main():
    st.set_page_config(page_title='Planeación institucional · Comfamiliar', page_icon=':material/analytics:',
        layout='wide', initial_sidebar_state='auto',
        menu_items={'About': 'Planeación institucional · Comfamiliar Risaralda. Seguimiento de planes operativos y estrategias.'})
    ui.aplicar_estilos()
    autenticado = exigir_acceso(obligatorio=True, dominio_requerido='comfamiliar.com')
    administrador = autenticado and puede_administrar(dict(st.user), dict(st.secrets.get('acceso', {})))
    definition = cargar_definicion()
    pages = {p['id']: p for p in definition['pages']}
    st.session_state.nombres_paginas = {p['id']: p['name'] for p in definition['pages']}
    st.session_state.setdefault('pagina', definition['active_page'])
    st.session_state.setdefault('mostrar_adicionales', False)
    st.session_state.setdefault('selecciones', {})
    st.session_state.setdefault('cruces', {})
    st.session_state.setdefault('epoca_seleccion', 0)
    st.session_state.rutas = {p['id']: datos_vista(p)[1] for p in definition['pages']} | {'explorar': 'datos', 'administrar': 'administracion'}
    routes = {slug: page_id for page_id, slug in st.session_state.rutas.items()}
    requested = st.query_params.get('vista')
    if requested in routes and routes[requested] != st.session_state.pagina:
        target = routes[requested]
        ir(target, target in pages and pages[target]['hidden'])
    carpeta = str(Path(os.environ.get('PLANES_MODELO', ROOT / 'modelo_powerbi')).expanduser().resolve())
    with st.sidebar:
        navegacion(definition)
        if autenticado:
            mostrar_sesion()
        if administrador:
            st.button('Actualizar información', icon=':material/admin_panel_settings:', key='nav_administrar',
                width='stretch', on_click=ir, args=('administrar',))
    choices = list(pages) + ['explorar']
    if administrador:
        choices.append('administrar')
    if st.session_state.pagina not in choices:
        ir(definition['active_page'])
        st.rerun()
    try:
        corte = leer_corte(carpeta)
        page_id = st.session_state.pagina
        nombre = {'explorar': 'Explorar datos', 'administrar': 'Actualizar información'}.get(page_id)
        if nombre is None:
            name = pages[page_id]['name']
            nombre = espacio_de(name)['nombre'] + ' / ' + MODOS[name]
        encabezado(carpeta, corte, nombre)
        if page_id == 'administrar':
            panel_administrativo()
        elif page_id == 'explorar':
            explorar(carpeta, corte)
        else:
            pagina = pages[page_id]
            if pagina['name'] == 'Menu':
                portada(definition, carpeta, corte)
            else:
                titulo_pagina(pagina)
                modos_analisis(pagina, definition)
                with st.container(key='contexto_informe'):
                    base = filtros_pagina(carpeta, corte, pagina)
                informe(carpeta, corte, pagina, base, definition)
    except ErrorDatos as error:
        st.info(str(error), icon=':material/info:')
        st.caption('Contacta al administrador para revisar el corte publicado.')
    except Exception as error:
        st.error(f'No se pudo abrir esta vista ({type(error).__name__}). Revisa que los archivos del tablero estén juntos y pulsa Recargar datos.')
        # No mostrar cadenas ODBC, credenciales o excepciones privadas en pantalla.
        if os.environ.get('PLANES_DEPURAR') == '1':
            raise


if __name__ == '__main__':
    main()
