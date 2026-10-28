"""Arquitectura de información: las 13 páginas conservan sus consultas y slugs."""
ESPACIOS = (
    {'slug': 'inicio', 'nombre': 'Visión ejecutiva', 'titulo': 'Visión ejecutiva', 'icono': 'space_dashboard',
     'vistas': ('Menu',), 'inicial': 'Menu'},
    {'slug': 'desempeno', 'nombre': 'Desempeño', 'titulo': 'Desempeño institucional', 'icono': 'monitoring',
     'vistas': ('Área', 'Proceso'), 'inicial': 'Área'},
    {'slug': 'operacion', 'nombre': 'Gestión operativa', 'titulo': 'Gestión operativa', 'icono': 'assignment',
     'vistas': ('Plan Operativo', 'Proceso y Tareas', 'Actividades/Tareas'), 'inicial': 'Plan Operativo'},
    {'slug': 'seguimiento', 'nombre': 'Seguimiento', 'titulo': 'Seguimiento de gestión', 'icono': 'fact_check',
     'vistas': ('Tareas Pendientes', 'Procesos Pendientes', 'Factores Limitantes'), 'inicial': 'Tareas Pendientes'},
    {'slug': 'estrategia', 'nombre': 'Estrategia', 'titulo': 'Estrategia institucional', 'icono': 'account_tree',
     'vistas': ('Objetivos', 'Estrategias', 'Estrategias por Áreas', 'Est No Relacionadas'), 'inicial': 'Objetivos'},
)
MODOS = {'Menu': 'Resumen', 'Área': 'Áreas', 'Proceso': 'Procesos', 'Plan Operativo': 'Plan de trabajo',
         'Proceso y Tareas': 'Ejecución de tareas', 'Actividades/Tareas': 'Volumen de gestión',
         'Tareas Pendientes': 'Por calificar', 'Procesos Pendientes': 'Procesos pendientes',
         'Factores Limitantes': 'Factores limitantes', 'Objetivos': 'Objetivos', 'Estrategias': 'Estrategias',
         'Estrategias por Áreas': 'Contribución por área', 'Est No Relacionadas': 'Sin relación'}


def espacio_de(nombre):
    return next(group for group in ESPACIOS if nombre in group['vistas'])
