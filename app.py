"""Tablero ejecutivo del reporte original. Abrir: python -m streamlit run app.py"""
from datetime import date, datetime
from functools import partial
import base64
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
from consultas_tablero import (ROOT, ErrorDatos, MotorReporte, cargar_definicion, clave_selector,
    condicion_in, condiciones_pagina, leer_corte, modelo_corte, valores_guardados)

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


@st.cache_data(max_entries=3)
def cobertura(carpeta, corte):
    """Conteos descriptivos del corte completo; no sustituyen las medidas del informe."""
    planes = motor(carpeta, corte).modelo.tabla(fuente.PLAN)
    counts = planes.select(pl.len().alias('registros'),
        pl.col('AREA').str.to_lowercase().drop_nulls().n_unique().alias('areas'),
        pl.col('Proceso Final').str.to_lowercase().drop_nulls().n_unique().alias('procesos')).collect().row(0, named=True)
    years = planes.filter(pl.col('ANO').is_not_null()).group_by('ANO').len().sort('ANO').collect()
    return counts, years


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


def recargar_datos():
    limpiar_cruce(st.session_state.pagina)
    st.toast('Estás consultando el último corte disponible.', icon=':material/check_circle:')


def navegacion(definition):
    actual = st.session_state.pagina
    ui.marca(logo_empresa())
    home, *pages = definition['pages']
    def acceso(page):
        title, _, icon, _ = datos_vista(page)
        st.button(title, icon=f':material/{icon}:', key='nav_' + page['id'], width='stretch',
            type='primary' if actual == page['id'] else 'tertiary',
            on_click=ir, args=(page['id'], page['hidden']))
    acceso(home)
    st.caption('SEGUIMIENTO OPERATIVO')
    for page in pages:
        if not page['hidden']:
            acceso(page)
    st.toggle('Mostrar vistas adicionales', key='mostrar_adicionales',
        help='Incluye objetivos, estrategias y otros informes complementarios.')
    if st.session_state.mostrar_adicionales:
        with st.expander('Análisis complementario', expanded=True, icon=':material/insights:'):
            for page in pages:
                if page['hidden']:
                    acceso(page)
    st.caption('CONSULTA DE DATOS')
    st.button('Explorar datos', icon=':material/table_view:', key='nav_explorar', width='stretch',
        type='primary' if actual == 'explorar' else 'tertiary', on_click=ir, args=('explorar',))
    st.button('Recargar datos', icon=':material/refresh:', width='stretch', on_click=recargar_datos,
        help='Abre el último corte publicado. Los filtros se conservan.')


def encabezado(carpeta, corte, vista):
    stamp = motor(carpeta, corte).modelo.medida('Hora Actualización')
    ui.barra_superior(vista, formato(stamp))


def titulo_pagina(pagina):
    title, _, _, description = datos_vista(pagina)
    st.title(title)
    st.write(description)


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
    st.caption('Ajusta el contexto del informe. Las selecciones se conservan al navegar.')
    for start in range(0, len(slicers), 4):
        columns = st.columns(min(4, len(slicers) - start), gap='medium')
        for column, visual in zip(columns, slicers[start:start + 4]):
            with column:
                selector(carpeta, corte, pagina, visual)
    if pagina['filters']:
        with st.expander('Filtros de página', icon=':material/tune:'):
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
    with st.container(horizontal=True):
        st.button('Restablecer', icon=':material/restart_alt:', on_click=restaurar, args=(pagina,),
            help='Recuperar los filtros iniciales de este informe.')
        st.button('Limpiar filtros', icon=':material/filter_alt_off:', on_click=restaurar, args=(pagina, True),
            help='Quitar las selecciones y los filtros de página de esta vista.')
    return condiciones_pagina(pagina, st.session_state.selecciones)


def configuracion_columnas(fields, estados=()):
    configs = {}
    labels = {'Recusros': 'Recursos', 'Indiacdor': 'Indicador', 'CUMP': 'Cumplimiento',
              'Cump': 'Cumplimiento', 'Calif': 'Calificación', '% Ponderado Cump': 'Cumplimiento ponderado'}
    for field in fields:
        alias, label = field['alias'], field['label']
        label = labels.get(label, label)
        if field.get('percent'):
            configs[alias] = st.column_config.NumberColumn(label, format='percent')
        elif field['column'] in {'FECINICIAL', 'FECFINAL'}:
            configs[alias] = st.column_config.DatetimeColumn(label, format='DD/MM/YYYY')
        elif field['kind'] == 'Aggregation' and field['function'] in {2, 5}:
            configs[alias] = st.column_config.NumberColumn(label, format='localized')
        else:
            configs[alias] = st.column_config.Column(label, width='large' if field['kind'] == 'Column' else None)
    for state in estados:
        configs[state] = st.column_config.TextColumn('Estado' if len(estados) == 1 else 'Estado · ' + state.removeprefix('estado_'))
    return configs


def grafico(result, pagina, visual, key, horizontal=False):
    if not result.grupos or not result.valores or result.total == 0:
        st.info('No hay datos para mostrar con estos filtros.')
        return
    group = result.grupos[0]
    data = result.datos
    labels = [str(value) if value is not None else '(En blanco)' for value in data[group['alias']].to_list()]
    ticks = ['<br>'.join(textwrap.wrap(label, 30 if horizontal else 22)) for label in labels]
    fig = go.Figure()
    for index, value in enumerate(result.valores):
        score = value['alias']
        states = 'estado_' + score
        colors = [COLORES.get(v, AZUL) for v in data[states].to_list()] if states in data.columns else [AZUL if index == 0 else DORADO] * len(labels)
        coords = {'x': data[score].to_list(), 'y': labels} if horizontal else {'x': labels, 'y': data[score].to_list()}
        decimals = '.2%' if value.get('percent') else ',.0f' if value.get('function') in {2, 5} else '.2f'
        tooltip = ('%{y}<br>%{x:' + decimals + '}<extra></extra>' if horizontal
                   else '%{x}<br>%{y:' + decimals + '}<extra></extra>')
        fig.add_trace(go.Bar(**coords, name=value['label'], orientation='h' if horizontal else 'v',
            marker_color=colors, marker_line_width=0,
            customdata=[[v] for v in data[group['alias']].to_list()],
            hovertemplate=tooltip))
    fig.update_layout(height=min(760, max(350, len(labels) * 46)) if horizontal else 410,
        margin=dict(l=8, r=30, t=20, b=24), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Segoe UI, Arial, sans-serif', size=14, color=TINTA),
        barmode='group', legend=dict(orientation='h', y=1.12), bargap=.42,
        showlegend=len(result.valores) > 1, dragmode=False,
        hoverlabel=dict(bgcolor='white', font_color=TINTA, font_size=14),
        transition_duration=0)
    axis_format = '.0%' if result.valores[0].get('percent') else ',d' if result.valores[0].get('function') in {2, 5} else '.2f'
    if horizontal:
        fig.update_yaxes(autorange='reversed', tickvals=labels, ticktext=ticks, showgrid=False, automargin=True)
        fig.update_xaxes(tickformat=axis_format, gridcolor=BORDE, zeroline=False,
                         title_text=result.valores[0]['label'] if len(result.valores) == 1 else None)
    else:
        fig.update_xaxes(tickvals=labels, ticktext=ticks, showgrid=False, automargin=True)
        fig.update_yaxes(tickformat=axis_format, gridcolor=BORDE, zeroline=False)
    st.plotly_chart(fig, width='stretch', key=key, selection_mode='points',
        on_select=partial(guardar_barra, pagina['id'], visual['id'], key, group),
        config={'displayModeBar': False, 'scrollZoom': False})


def render_tabla(carpeta, corte, pagina, visual, base):
    conditions = condiciones_visual(pagina, visual, base)
    fields = visual['groups']
    depth = None
    with st.container(border=False, key='resultado_' + pagina['id'] + visual['id']):
        heading = ' / '.join(f['label'] for f in fields[:1]) or 'Detalle'
        encabezado_seccion('Detalle por ' + heading.lower() if fields else heading,
            'Selecciona una fila para relacionar sus resultados con los demás visuales.', 'table_chart')
        if visual['type'] == 'pivotTable' and len(fields) > 1:
            default = max(1, sum(f['active'] for f in fields))
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
            chart = st.toggle('Mostrar gráfico del resumen', value=False, key='graf_' + key)
            if chart:
                chart_visual = {**visual, 'id': visual['id'] + '_resumen'}
                chart_conditions = condiciones_visual(pagina, chart_visual, base)
                summary = consulta(carpeta, corte, visual, chart_conditions, 1, 100, 0)
                if summary.total <= 60:
                    grafico(summary, pagina, chart_visual, 'chart_' + key + str(st.session_state.epoca_seleccion), horizontal=True)
                else:
                    st.caption('Selecciona un área o proceso para obtener un gráfico legible. La tabla conserva todos los resultados.')
        shown = result.datos.to_pandas()
        if result.estados:
            def tint(value):
                color = COLORES.get(value)
                return f'color: {color}; font-weight: 600' if color else ''
            shown = shown.style.map(tint, subset=result.estados)
        widget = 'tabla_' + key + str(st.session_state.epoca_seleccion)
        st.caption(f'{numero(result.total)} resultados · página {page} de {pages}')
        event = st.dataframe(shown, hide_index=True, width='stretch', height=min(590, max(180, result.datos.height * 35 + 45)),
            column_config=configuracion_columnas(result.grupos + result.valores, result.estados), key=widget,
            selection_mode='single-row', on_select=partial(guardar_fila, pagina['id'], visual['id'], widget, result.grupos, result.datos.to_dicts()))
        if result.totales:
            st.markdown('**Total de la selección** · ' + '  ·  '.join(f"{f['label']}: **{formato(result.totales[f['alias']], f.get('percent'))}**" for f in result.valores))
        if pages > 1:
            st.number_input('Página de resultados', min_value=1, max_value=pages, value=page, step=1, key=page_key)
            st.caption(f'Página {page} de {pages} · hasta {limit} resultados por página')
        if event.selection.rows and 0 <= event.selection.rows[0] < result.datos.height:
            selected = result.datos.row(event.selection.rows[0], named=True)
            with st.expander('Texto completo de la fila seleccionada', icon=':material/visibility:'):
                for field in result.grupos + result.valores:
                    st.markdown('**' + field['label'] + '**')
                    st.write(formato(selected[field['alias']], field.get('percent')))


def portada(definition, carpeta, corte):
    counts, years = cobertura(carpeta, corte)
    with st.container(key='inicio_hero'):
        main, period = st.columns([1.8, 1], vertical_alignment='center', gap='large')
        with main:
            ui.etiqueta_hero('COMFAMILIAR RISARALDA · GESTIÓN INSTITUCIONAL')
            st.title('Planeación institucional')
            st.write('Los planes, sus resultados y el seguimiento de la gestión, en un solo lugar.')
        with period:
            ui.resumen_cobertura(years['ANO'].min(), years['ANO'].max(), years.height)
    ui.tarjetas_cobertura(counts, years.height)
    reports, history = st.columns([1.6, 1], gap='large')
    with reports:
        encabezado_seccion('Informes destacados', 'Elige el punto de vista para comenzar tu análisis.', 'dashboard')
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
            encabezado_seccion('Cobertura histórica', 'Registros operativos disponibles por año.', 'bar_chart')
            if years.height:
                fig = go.Figure(go.Bar(x=years['len'].to_list(), y=years['ANO'].cast(pl.String).to_list(),
                    orientation='h', marker_color=AZUL, marker_line_width=0,
                    text=[numero(value) for value in years['len']], textposition='outside', cliponaxis=False,
                    hovertemplate='Año %{y}<br>%{x:,.0f} registros<extra></extra>'))
                fig.update_layout(height=310, margin=dict(l=0, r=55, t=8, b=16),
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
    st.caption('Para ver cumplimiento y metas, abre un informe y selecciona el año y el trimestre. '
               'Los conteos de esta portada describen toda la carga disponible.')


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
    cross = st.session_state.cruces.get(pagina['id'])
    if cross:
        with st.container(horizontal=True, vertical_alignment='center'):
            st.badge('Selección · ' + cross['label'], icon=':material/filter_alt:', color='blue')
            st.button('Quitar selección', icon=':material/close:', on_click=limpiar_cruce, args=(pagina['id'],))
    cards = sorted([v for v in pagina['visuals'] if v['type'] == 'card'], key=lambda v: v['position']['x'])
    if cards:
        st.caption('RESULTADOS DE LA SELECCIÓN')
        columns = st.columns(min(len(cards), 4), gap='medium')
        for column, visual in zip(columns, cards):
            with column:
                result = consulta(carpeta, corte, visual, condiciones_visual(pagina, visual, base))
                field = visual['values'][0]
                value = result.datos[field['alias']][0]
                own_quarter = next((row[0] for c in visual['filters'] if c['operator'] == 'In' and c['fields'][0]['column'] == 'Trimestre' for row in c['values']), None)
                help_text = 'Promedio de calificación, como en la tarjeta original.' if field.get('function') == 1 else None
                if own_quarter:
                    help_text = 'Esta tarjeta usa ' + own_quarter + ', según el Power BI original.'
                st.metric(field['label'], formato(value, field.get('percent')), border=True, help=help_text)
                if own_quarter:
                    st.caption('Filtro de esta tarjeta: ' + own_quarter)
                elif field.get('function') == 1:
                    st.caption('Promedio de calificación')
        st.space('small')
    body = sorted([v for v in pagina['visuals'] if v['type'] in {'pivotTable', 'tableEx', 'clusteredColumnChart'}], key=lambda v: (v['position']['y'], v['position']['x']))
    for visual in body:
        if visual['type'] == 'clusteredColumnChart':
            with st.container(border=False, key='grafico_' + pagina['id'] + visual['id']):
                encabezado_seccion('Cumplimiento por área', 'Selecciona una barra para consultar su detalle.', 'bar_chart')
                result = consulta(carpeta, corte, visual, condiciones_visual(pagina, visual, base), limit=100)
                grafico(result, pagina, visual, 'barra_' + pagina['id'] + visual['id'] + str(st.session_state.epoca_seleccion), horizontal=True)
        else:
            render_tabla(carpeta, corte, pagina, visual, base)
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
    definition = cargar_definicion()
    pages = {p['id']: p for p in definition['pages']}
    st.session_state.setdefault('pagina', definition['active_page'])
    st.session_state.setdefault('mostrar_adicionales', False)
    st.session_state.setdefault('selecciones', {})
    st.session_state.setdefault('cruces', {})
    st.session_state.setdefault('epoca_seleccion', 0)
    st.session_state.rutas = {p['id']: datos_vista(p)[1] for p in definition['pages']} | {'explorar': 'datos'}
    routes = {slug: page_id for page_id, slug in st.session_state.rutas.items()}
    requested = st.query_params.get('vista')
    if requested in routes and routes[requested] != st.session_state.pagina:
        target = routes[requested]
        ir(target, target in pages and pages[target]['hidden'])
    carpeta = str(Path(os.environ.get('PLANES_MODELO', ROOT / 'modelo_powerbi')).expanduser().resolve())
    with st.sidebar:
        navegacion(definition)
    choices = [p['id'] for p in definition['pages'] if not p['hidden'] or st.session_state.mostrar_adicionales] + ['explorar']
    if st.session_state.pagina not in choices:
        ir(definition['active_page'])
        st.rerun()
    try:
        corte = leer_corte(carpeta)
        page_id = st.session_state.pagina
        encabezado(carpeta, corte, 'Explorar datos' if page_id == 'explorar' else datos_vista(pages[page_id])[0])
        if page_id == 'explorar':
            explorar(carpeta, corte)
        else:
            pagina = pages[page_id]
            if pagina['name'] == 'Menu':
                portada(definition, carpeta, corte)
            else:
                titulo_pagina(pagina)
                with st.expander('Filtros del informe', expanded=True, icon=':material/tune:'):
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
