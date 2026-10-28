"""Matriz expandible con consultas diferidas por rama y valores del motor original."""
import hashlib
import json
import math

from consultas_tablero import condicion_in


def id_nodo(path):
    return hashlib.sha256(json.dumps(path, ensure_ascii=False, default=str, separators=(',', ':')).encode('utf-8')).hexdigest()


def construir_matriz(consultar, visual, condiciones, abiertos=(), pagina=1, paginas_hijo=None, limite=100):
    """Conservar padres y consultar exclusivamente las ramas abiertas visibles."""
    pages = paginas_hijo or {}
    root = consultar(visual, condiciones, 1, limite, (pagina - 1) * limite)
    rows = []
    allowed = {}
    def visit(result, depth):
        for row in result.datos.to_dicts():
            path = [row[group['alias']] for group in result.grupos]
            identifier = id_nodo(path)
            allowed[identifier] = path
            rows.append({'tipo': 'dato', 'id': identifier, 'ruta': path, 'profundidad': depth,
                         'etiqueta': '(En blanco)' if path[-1] is None else str(path[-1]),
                         'desplegable': depth < len(visual['groups']), 'abierto': identifier in abiertos,
                         'valores': {f['alias']: row[f['alias']] for f in result.valores},
                         'estados': {name: row[name] for name in result.estados}})
            if depth >= len(visual['groups']) or identifier not in abiertos:
                continue
            own = list(condiciones) + [condicion_in(group, [value]) for group, value in zip(visual['groups'], path)]
            child_page = max(1, int(pages.get(identifier, 1)))
            children = consultar(visual, own, depth + 1, limite, (child_page - 1) * limite)
            child_pages = max(1, math.ceil(children.total / limite))
            if child_page > child_pages:
                child_page = child_pages
                children = consultar(visual, own, depth + 1, limite, (child_page - 1) * limite)
            visit(children, depth + 1)
            if children.total == 0:
                rows.append({'tipo': 'vacio', 'profundidad': depth + 1, 'etiqueta': 'Sin componentes con estos filtros.'})
            if child_pages > 1:
                rows.append({'tipo': 'paginacion', 'id': identifier, 'profundidad': depth + 1,
                             'pagina': child_page, 'paginas': child_pages, 'total': children.total})
    visit(root, 1)
    return {'filas': rows, 'nodos': allowed, 'totales': root.totales,
            'estados_totales': root.estados_totales, 'columnas': visual['values'],
            'pagina': pagina, 'paginas': max(1, math.ceil(root.total / limite)), 'total': root.total,
            'nivel_raiz': visual['groups'][0]['label']}


HTML = '<div id="matriz-root"></div>'
CSS = """
:host {font-family:var(--st-font, 'Segoe UI', sans-serif); color:var(--st-text-color,#183C47)}
* {box-sizing:border-box}
.matrix-scroll {width:100%;max-height:590px;overflow:auto;border:1px solid #dce5e0;border-radius:12px;background:white}
table {width:100%;min-width:560px;border-collapse:separate;border-spacing:0;table-layout:fixed;font-size:13px}
thead th {position:sticky;top:0;background:#eaf2ed;color:#234a43;font-weight:600;text-align:right;z-index:2;border-bottom:1px solid #c7d8cd;padding:12px 14px}
thead th:first-child {width:56%;text-align:left}
td {padding:9px 14px;border-bottom:1px solid #e5ece8;vertical-align:middle;text-align:right}
td:first-child {text-align:left;overflow-wrap:anywhere}
tbody tr[data-kind="dato"] {cursor:pointer}
tbody tr[data-kind="dato"]:hover {background:#f2f7f4}
tbody tr.selected {background:#e4f0ea}
.node {display:flex;align-items:center;gap:8px;min-height:26px}
.toggle {width:26px;min-width:26px;height:28px;background:white;border:1px solid #a3b8ab;border-radius:5px;color:#245d51;font-size:19px;line-height:1;cursor:pointer}
.toggle:hover {background:#dceee4}
.spacer {width:26px;min-width:26px}
.leaf {color:#435d64;font-size:12px;line-height:1.6}
.parent {font-weight:550;line-height:1.5}
.metric {display:inline-flex;align-items:center;justify-content:flex-end;gap:9px;white-space:nowrap;font-variant-numeric:tabular-nums}
.signal {display:inline-block;flex-shrink:0;width:11px;height:11px}
.signal.high {border:1px solid #267045;background:#78ba91;border-radius:50%}
.signal.low {width:10px;height:10px;border:1px solid #b64037;background:#fa7866;transform:rotate(45deg)}
.signal.medium {width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:13px solid #c18b22}
.signal.unknown {border:1px solid #6c7f85;border-radius:50%;background:#d9e1e4}
tfoot td {position:sticky;bottom:0;background:#eef5f0;border-top:2px solid #7aa18c;font-weight:650;z-index:1;padding-top:13px;padding-bottom:13px}
.pager {display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:12px 3px;font-size:12px;color:#536875}
.pager button,.child-pager button {min-height:36px;padding:7px 12px;background:#f2f6f3;color:#245d51;border:1px solid #d0e0d5;border-radius:7px;cursor:pointer}
.pager button:disabled,.child-pager button:disabled {opacity:.45;cursor:default}
.child-pager {display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:12px;color:#536875}
.legend {display:flex;flex-wrap:wrap;gap:16px;font-size:11px;color:#48616a;padding:9px 2px}
.legend span {display:flex;gap:7px;align-items:center}
tr:focus-visible,button:focus-visible {outline:3px solid #07529a;outline-offset:2px}
@media(max-width:600px) {.toggle {width:32px;min-width:32px;height:36px}.pager button,.child-pager button {min-height:44px}td,thead th{padding:10px}table{font-size:12px}}
"""
JS = """
export default function(component) {
  const {parentElement, data, setTriggerValue} = component;
  const root = parentElement.querySelector('#matriz-root');
  if (!root || !data) return;
  const previousScroll = root.querySelector('.matrix-scroll')?.scrollTop || 0;
  root.replaceChildren();
  function node(tag, text, cls) {const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(cls)e.className=cls; return e;}
  function emit(tipo, id, extra={}) {setTriggerValue('accion', {tipo,id,...extra});}
  function signal(state) {
    const css=state==='Cumple'||state==='Alto'?'high':state==='En seguimiento'||state==='Medio'?'medium':state==='Bajo'?'low':'unknown';
    const s=node('span',undefined,'signal '+css);s.title=state||'Sin dato';s.setAttribute('role','img');s.setAttribute('aria-label',state||'Sin dato');return s;
  }
  function valueCell(field, value, state) {
    const td=node('td');const box=node('span',undefined,'metric');
    if(state) box.append(signal(state));
    const formatted=value===null||value===undefined?'—':new Intl.NumberFormat('es-CO',field.percent?{style:'percent',minimumFractionDigits:1,maximumFractionDigits:1}:{maximumFractionDigits:2}).format(value);
    box.append(node('span',formatted)); td.append(box);return td;
  }
  const scroll=node('div',undefined,'matrix-scroll');scroll.dataset.matriz='true';
  const table=node('table');table.setAttribute('role','treegrid');table.setAttribute('aria-label','Matriz jerárquica de resultados');
  const head=node('thead');const hr=node('tr');hr.append(node('th',data.nivel_raiz));
  for(const c of data.columnas)hr.append(node('th',c.label));head.append(hr);table.append(head);
  const body=node('tbody');
  for(const row of data.filas) {
    const tr=node('tr');tr.dataset.kind=row.tipo;
    if(row.tipo==='dato') {
      tr.dataset.nodeId=row.id;tr.setAttribute('aria-level',row.profundidad);tr.tabIndex=0;
      if(row.desplegable)tr.setAttribute('aria-expanded',String(row.abierto));
      if(data.seleccion===row.id){tr.classList.add('selected');tr.setAttribute('aria-selected','true');}
      const cell=node('td');const line=node('div',undefined,'node');line.style.paddingLeft=((row.profundidad-1)*22)+'px';
      if(row.desplegable) {
        const button=node('button',row.abierto?'−':'+','toggle');button.type='button';button.setAttribute('aria-label',(row.abierto?'Contraer ':'Expandir ')+row.etiqueta);button.setAttribute('aria-expanded',String(row.abierto));
        button.onclick=e=>{e.stopPropagation();emit('alternar',row.id)};line.append(button);
      } else {line.append(node('span','', 'spacer'));}
      line.append(node('span',row.etiqueta,row.profundidad===1?'parent':'leaf'));cell.append(line);tr.append(cell);
      for(const c of data.columnas)tr.append(valueCell(c,row.valores[c.alias],row.estados['estado_'+c.alias]));
      tr.onclick=()=>emit('seleccionar',row.id);
      tr.onkeydown=e=>{if(e.target!==tr)return;if(e.key==='Enter'){e.preventDefault();emit('seleccionar',row.id)}if(e.key==='ArrowRight'&&row.desplegable&&!row.abierto){e.preventDefault();emit('alternar',row.id)}if(e.key==='ArrowLeft'&&row.desplegable&&row.abierto){e.preventDefault();emit('alternar',row.id)}};
    } else {
      const td=node('td');td.colSpan=data.columnas.length+1;
      if(row.tipo==='paginacion') {
        const wrap=node('div',undefined,'child-pager');wrap.append(node('span',`Componentes: página ${row.pagina} de ${row.paginas} · ${row.total} resultados`));
        for(const [label,delta] of [['Anterior',-1],['Siguiente',1]]){const b=node('button',label);b.disabled=delta<0?row.pagina===1:row.pagina===row.paginas;b.onclick=()=>emit('pagina_hijo',row.id,{pagina:row.pagina+delta});wrap.append(b);}td.append(wrap);
      } else td.append(node('span',row.etiqueta));tr.append(td);
    }
    body.append(tr);
  }
  table.append(body);
  const foot=node('tfoot');const total=node('tr');total.append(node('td','Total'));
  for(const c of data.columnas)total.append(valueCell(c,data.totales[c.alias],data.estados_totales['estado_'+c.alias]));
  foot.append(total);table.append(foot);scroll.append(table);root.append(scroll);scroll.scrollTop=previousScroll;
  const pager=node('div',undefined,'pager');pager.append(node('span',`${data.total} procesos · página ${data.pagina} de ${data.paginas}`));
  const actions=node('div');
  if(data.paginas>1)for(const [label,delta] of [['Anterior',-1],['Siguiente',1]]){const b=node('button',label);b.disabled=delta<0?data.pagina===1:data.pagina===data.paginas;b.onclick=()=>emit('pagina_raiz','',{pagina:data.pagina+delta});actions.append(b);}
  const close=node('button','Contraer todo');close.onclick=()=>emit('cerrar_todo','');actions.append(close);pager.append(actions);root.append(pager);
  const legend=node('div',undefined,'legend');for(const s of ['Cumple','En seguimiento','Bajo']){const text=node('span');text.append(signal(s),document.createTextNode(s));legend.append(text);}root.append(legend);
}
"""
