"""Presentación HTML5/CSS3 del tablero; sin consultas ni lógica de negocio."""
from html import escape
import base64
from pathlib import Path
import math
import polars as pl

import streamlit as st

ROOT = Path(__file__).resolve().parent

ICONOS = {
    'registros': '<path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-3"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="m7 13 3 3 7-7"/>',
    'areas': '<path d="M3 21h18M5 21V7h6v14M11 21V3h8v18M8 10v1m0 3v1m6-8v1m3-1v1m-3 3v1m3-1v1m-3 3v1m3-1v1"/>',
    'procesos': '<rect x="8" y="2" width="8" height="5" rx="1.5"/><rect x="2" y="17" width="7" height="5" rx="1.5"/><rect x="15" y="17" width="7" height="5" rx="1.5"/><path d="M12 7v5M5.5 17v-5h13v5"/>',
    'anos': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18m-12 5h6"/>',
    'calendario': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18m-11 5 2 2 4-4"/>',
    'flecha': '<path d="M5 12h14m-6-6 6 6-6 6"/>',
}


def icono(nombre):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#07529a" stroke-width="1.7" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            + ICONOS[nombre] + '</svg>')
    return '<img src="data:image/svg+xml;base64,' + base64.b64encode(svg.encode('utf-8')).decode('ascii') + '" alt="" aria-hidden="true">'


def aplicar_estilos():
    st.html('<style>' + (ROOT / 'assets/tablero.css').read_text(encoding='utf-8') + '</style>')


def marca(logo):
    st.html('<div class="brand-lockup"><img src="' + escape(logo, quote=True) +
            '" alt="Comfamiliar Risaralda" width="220" height="55">'
            '<div class="brand-caption">PLANEACIÓN INSTITUCIONAL</div></div>')


def marca_acceso():
    logo = 'data:image/jpeg;base64,' + base64.b64encode((ROOT / 'assets/comfamiliar.jpg').read_bytes()).decode('ascii')
    st.html('<div class="access-brand"><img src="' + logo + '" alt="Comfamiliar Risaralda">'
            '<span class="mini-label">PLANEACIÓN INSTITUCIONAL</span></div>')


def pie_navegacion():
    st.html('<div class="navigation-note"><span class="mini-label">DEL RESULTADO A LA ACCIÓN</span>'
            '<p>Selecciona un espacio y profundiza en sus modos de análisis.</p></div>')


def contexto_filtros(items):
    chips = ''.join('<span class="context-chip" title="' + escape(label + ': ' + value, quote=True) + '">'
                    '<strong>' + escape(label) + '</strong> ' + escape(value) + '</span>' for label, value in items)
    st.html('<div class="context-summary" aria-label="Filtros propios del informe">' + chips + '</div>')


def indicadores_informe(items):
    cards = ''.join('<article><span>' + escape(label) + '</span><strong>' + escape(value)
                    + '</strong><small>' + escape(note) + '</small></article>' for label, value, note in items)
    st.html('<section class="report-indicators" aria-label="Indicadores del contexto">' + cards + '</section>')


def lectura_comparacion(result, metric, formato):
    alias = metric['alias']
    rows = result.datos.filter(pl.col(alias).is_not_null()).sort(alias, descending=True)
    overall = formato(result.totales.get(alias), metric.get('percent'))
    blocks = '<div class="reading-total"><span>Resultado del contexto comparado</span><strong>' + escape(overall) + '</strong></div>'
    if rows.height:
        for title, index in (('Mayor resultado', 0), ('Menor resultado', rows.height - 1)):
            row = rows.row(index, named=True)
            blocks += ('<div class="reading-entry"><span>' + title + '</span><strong>'
                       + escape(str(row[result.grupos[0]['alias']] or '(En blanco)')) + '</strong><b>'
                       + escape(formato(row[alias], metric.get('percent'))) + '</b></div>')
    state = 'estado_' + alias
    if state in result.datos.columns:
        counts = {}
        for value in result.datos[state]:
            counts[value] = counts.get(value, 0) + 1
        blocks += '<div class="reading-states">' + ''.join('<span>' + escape(str(key)) + '<b>'
                    + str(value) + '</b></span>' for key, value in counts.items()) + '</div>'
    st.html('<aside class="chart-reading"><span class="mini-label">LECTURA DEL ANÁLISIS</span>'
            + blocks + '<p>' + str(result.total) + ' elementos en la selección. Los estados conservan las reglas del informe.</p></aside>')


def ficha_registro(fields):
    items = ''.join('<div class="record-field"><dt>' + escape(str(label)) + '</dt><dd>'
                    + escape(str(value)) + '</dd></div>' for label, value in fields)
    st.html('<article class="record-card"><span class="mini-label">DETALLE DE LA SELECCIÓN</span>'
            '<h3>Información completa del registro</h3><dl>' + items + '</dl></article>')


def barra_superior(vista, fecha):
    st.html('<header class="workspace-topbar"><nav aria-label="Ubicación actual">'
            '<span>Desarrollo estratégico</span><span class="breadcrumb-separator" aria-hidden="true">/</span>'
            '<strong>' + escape(vista) + '</strong></nav><div class="publication-state">'
            '<span class="publication-dot" aria-hidden="true"></span><span>Datos publicados</span>'
            '<span class="publication-date">' + icono('calendario') + escape(fecha) + '</span></div></header>')


def etiqueta_hero(texto):
    st.html('<div class="hero-eyebrow"><span aria-hidden="true"></span>' + escape(texto) + '</div>')


def resumen_cobertura(desde, hasta, cantidad):
    periodo = f'{desde} — {hasta}' if cantidad else 'Sin períodos'
    st.html('<aside class="hero-coverage" aria-label="Cobertura de los datos">'
            '<span class="hero-coverage-label">HISTÓRICO DISPONIBLE</span>'
            '<strong>' + escape(periodo) + '</strong><span>' + escape(str(cantidad)) +
            ' años de información institucional</span></aside>')


def tarjetas_cobertura(conteos, anos):
    items = (
        ('registros', 'Registros operativos', conteos['registros'], 'En todos los años publicados'),
        ('areas', 'Áreas', conteos['areas'], 'Con información en el corte'),
        ('procesos', 'Procesos', conteos['procesos'], 'Con información en el corte'),
        ('anos', 'Años de seguimiento', anos, 'Cobertura histórica disponible'),
    )
    cards = []
    for icon, label, value, description in items:
        formatted = f'{value:,}'.replace(',', '.')
        cards.append('<article class="kpi-card"><div class="kpi-heading"><span class="kpi-icon">'
            + icono(icon) + '</span><span>' + escape(label) + '</span></div><dl><dt class="sr-only">'
            + escape(label) + '</dt><dd>' + escape(formatted) + '</dd></dl><p>' + escape(description) + '</p></article>')
    st.html('<section class="kpi-grid" aria-label="Cobertura del corte completo">' + ''.join(cards) + '</section>')


def titulo_acceso(icon, titulo):
    st.html('<div class="report-card-heading"><span class="report-icon">' + icono(icon) +
            '</span><h3>' + escape(titulo) + '</h3></div>')


def contexto_periodo():
    st.html('<div class="period-label"><span class="mini-label">CONTEXTO DEL ANÁLISIS</span>'
            '<strong>Elige tu perspectiva temporal</strong></div>')


def seccion_editorial(numero, titulo, descripcion):
    st.html('<div class="editorial-heading"><span>' + escape(numero) + '</span><div><h2>'
            + escape(titulo) + '</h2><p>' + escape(descripcion) + '</p></div></div>')


def porcentaje(value):
    return f'{value:.2%}'.replace('.', ',') if value is not None and math.isfinite(value) else '—'


def panel_ejecutivo(ano, trimestre, average, target, weighted, areas, records):
    """Solo presentación: los estados llegan calculados por las reglas originales."""
    valid = weighted is not None and math.isfinite(weighted) and records > 0
    progress = min(100, max(0, weighted * 100)) if valid else 0
    achieved = sum(row.get('estado_v0') == 'Cumple' for row in areas)
    rows = []
    for index, row in enumerate(areas):
        value = row.get('v0')
        width = min(100, max(0, value * 100)) if value is not None and math.isfinite(value) else 0
        state = row.get('estado_v0', 'Sin dato')
        state_class = {'Cumple': 'good', 'En seguimiento': 'watch', 'Bajo': 'low'}.get(state, 'neutral')
        rows.append('<li class="area-row ' + state_class + '"><span class="area-index">'
                    + f'{index + 1:02d}' + '</span><div class="area-detail"><div class="area-title">'
                    '<strong>' + escape(str(row.get('g0') or '(En blanco)')) + '</strong><span>'
                    + porcentaje(value) + '</span></div><div class="area-track"><span style="width:'
                    + f'{width:.4f}' + '%"></span></div><span class="area-state">'
                    + escape(state) + '</span></div></li>')
    if not rows:
        rows.append('<li class="executive-empty">No hay áreas con calificación para este período.</li>')
    period = f'{ano} · {trimestre}'
    result_text = porcentaje(weighted) if valid else '—'
    st.html('<section class="executive-grid" aria-label="Resumen ejecutivo del período">'
        '<article class="performance-card"><div class="performance-top"><span class="mini-label">'
        'PULSO INSTITUCIONAL</span><span class="period-chip">' + escape(period) + '</span></div>'
        '<h2>Los objetivos,<br>en perspectiva.</h2><p class="performance-intro">Avance frente a la meta trimestral</p>'
        '<div class="performance-center"><div class="performance-ring" style="--progress:' + f'{progress:.4f}'
        + '%" role="img" aria-label="Avance frente a la meta: ' + escape(result_text) + '">'
        '<div><strong>' + result_text + '</strong><span>de la meta trimestral</span></div></div></div>'
        '<div class="performance-bottom"><div><span>Calificación promedio</span><strong>'
        + (porcentaje(average) if records else '—') + '</strong></div><div><span>Meta del trimestre</span><strong>'
        + (porcentaje(target) if records else '—') + '</strong></div></div>'
        '<p class="formula-note">Promedio de calificación ÷ meta trimestral. El arco se limita al 100 %; el valor conserva el resultado completo.</p>'
        '</article><article class="areas-card"><div class="areas-heading"><div><span class="mini-label">'
        'DESEMPEÑO POR ÁREA</span><h2>Una institución.<br>Múltiples resultados.</h2></div><span class="area-total">'
        + str(len(areas)) + '<small>áreas</small></span></div><p class="areas-description">Calificación promedio · registros Aplica</p>'
        '<ol class="area-ranking">' + ''.join(rows) + '</ol>'
        '<div class="areas-footer"><span><strong>' + str(achieved) + ' de ' + str(len(areas))
        + '</strong> áreas en estado Cumple</span><span>' + f'{records:,}'.replace(',', '.')
        + ' registros del período</span></div><p class="ranking-note">Cumple: ≥ 95 % de la meta · En seguimiento: 90–95 % · Bajo: &lt; 90 %. Las barras muestran la calificación, no el avance frente a la meta.</p>'
        '</article></section>')
