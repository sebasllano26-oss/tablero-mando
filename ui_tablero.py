"""Presentación HTML5/CSS3 del tablero; sin consultas ni lógica de negocio."""
from html import escape
import base64
from pathlib import Path

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
