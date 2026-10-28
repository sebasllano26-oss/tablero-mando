"""Comparaciones de dirección. Recibe agregados; no consulta ni transforma el modelo."""
from html import escape
import math
import textwrap

import plotly.graph_objects as go

COLORES = {'Cumple': '#247563', 'Alto': '#247563', 'En seguimiento': '#9C741E',
           'Medio': '#9C741E', 'Bajo': '#AF5264', 'Sin dato': '#627785'}
SERIES = ('#145D72', '#658C77', '#8A6C35')


def texto_numero(value, percent=False):
    if value is None or not math.isfinite(value):
        return '—'
    if percent:
        return f'{value * 100:.2f}'.replace('.', ',') + ' %'
    return f'{int(value):,}'.replace(',', '.') if float(value).is_integer() else f'{value:.2f}'.replace('.', ',')


def construir_comparacion(result, meta=None, metrica=None, limite=12, orden='Mayor resultado', tipo='barras'):
    values = [field for field in result.valores if metrica is None or field['alias'] == metrica]
    if not values or not result.grupos:
        raise ValueError('La comparación requiere una categoría y una medida.')
    data = result.datos
    first = values[0]
    if orden != 'Orden del informe':
        data = data.sort(first['alias'], descending=orden == 'Mayor resultado', nulls_last=True, maintain_order=True)
    data = data.head(limite)
    group = result.grupos[0]
    labels = [str(value) if value is not None else '(En blanco)' for value in data[group['alias']]]
    ticks = []
    for label in labels:
        lines = textwrap.wrap(label, 31) or ['(En blanco)']
        ticks.append('<br>'.join(escape(line) for line in lines[:2]) + ('…' if len(lines) > 2 else ''))
    fig = go.Figure(layout={'template': 'none'})
    for index, field in enumerate(values):
        alias = field['alias']
        state = 'estado_' + alias
        colors = [COLORES.get(value, SERIES[index % len(SERIES)]) for value in data[state]] if state in data.columns and len(values) == 1 else SERIES[index % len(SERIES)]
        pattern = '.2%' if field.get('percent') else ',.0f' if field.get('function') in {2, 5} else '.2f'
        common = {'x': data[alias].to_list(), 'y': labels, 'name': field['label'],
                  'text': [texto_numero(v, field.get('percent')) for v in data[alias]],
                  'textfont': {'size': 12, 'color': '#183C47'}, 'cliponaxis': False,
                  'customdata': [[value] for value in data[group['alias']]],
                  'hovertemplate': '%{y}<br>%{x:' + pattern + '}<extra>' + escape(field['label']) + '</extra>'}
        if tipo == 'puntos' and len(values) == 1:
            for label, value in zip(labels, data[alias]):
                if value is not None and math.isfinite(value):
                    fig.add_shape(type='line', x0=0, x1=value, y0=label, y1=label,
                        line={'width': 4, 'color': '#DDE9E4'}, layer='below')
            fig.add_trace(go.Scatter(**common, mode='markers+text', textposition='middle right',
                marker={'color': colors, 'size': 13, 'line': {'color': '#FFFFFF', 'width': 1.5}}))
        else:
            fig.add_trace(go.Bar(**common, orientation='h', marker={'color': colors, 'cornerradius': 5},
                                width=.48 if len(values) == 1 else None, textposition='outside'))
    percent = bool(first.get('percent'))
    maximum = max([float(v) for field in values for v in data[field['alias']] if v is not None and math.isfinite(v)] + [0.0])
    minimum = min([float(v) for field in values for v in data[field['alias']] if v is not None and math.isfinite(v)] + [0.0])
    if meta is not None and math.isfinite(meta) and len(values) == 1:
        fig.add_vline(x=meta, line_width=1.5, line_dash='dot', line_color='#385864',
            annotation_text='Referencia ' + texto_numero(meta, percent), annotation_position='top right',
            annotation_font={'size': 11, 'color': '#385864'})
        maximum = max(maximum, meta)
    coverage = f'{data.height} de {result.total} elementos'
    fig.update_layout(height=max(290, min(1100, data.height * (53 if len(values) > 1 else 48) + 70)),
        margin={'l': 0, 'r': 72, 't': 37, 'b': 22}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Segoe UI, Arial, sans-serif', 'size': 12, 'color': '#254653'},
        showlegend=len(values) > 1, legend={'orientation': 'h', 'y': 1.15, 'x': 0},
        barmode='group', bargap=.46, hoverlabel={'bgcolor': '#FFFFFF', 'font_color': '#183C47'},
        dragmode=False, clickmode='event+select', transition_duration=0, meta={'cobertura': coverage})
    fig.update_yaxes(autorange='reversed', tickvals=labels, ticktext=ticks, showgrid=False, ticks='', automargin=True)
    fig.update_xaxes(tickformat='.0%' if percent else ',d' if first.get('function') in {2, 5} else '.2f',
        range=[minimum * 1.15, maximum * 1.23 if maximum else 1], gridcolor='#E8EFEC',
        zeroline=False, showline=False, fixedrange=True, title_text=first['label'] if len(values) == 1 else 'Cantidad')
    return fig
