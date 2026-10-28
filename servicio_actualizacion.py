"""Servicio local para un proxy HTTPS corporativo. No exponer este puerto directamente."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import getpass
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading

ROOT = Path(__file__).resolve().parent


class Trabajos:
    def __init__(self, ejecutar, administradores):
        self.ejecutar = ejecutar
        self.administradores = {a.strip().casefold() for a in administradores}
        self.jobs, self.lock = {}, threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='actualizar')

    def iniciar(self, identifier, actor):
        if not isinstance(identifier, str) or not re.fullmatch('[0-9a-f]{32}', identifier):
            return 400, {'error': 'Solicitud inválida.'}
        if not isinstance(actor, str) or actor.casefold() not in self.administradores:
            return 403, {'error': 'Administrador no autorizado.'}
        with self.lock:
            if identifier in self.jobs:
                return 200, dict(self.jobs[identifier])
            if any(job['estado'] == 'ejecutando' for job in self.jobs.values()):
                return 409, {'error': 'Ya existe una actualización en curso.'}
            if len(self.jobs) >= 100:
                self.jobs.pop(next(iter(self.jobs)))
            self.jobs[identifier] = {'id': identifier, 'estado': 'ejecutando'}
            self.executor.submit(self._trabajar, identifier)
            return 202, dict(self.jobs[identifier])

    def _trabajar(self, identifier):
        try:
            result = self.ejecutar()
            public = {key: result[key] for key in ('estado', 'version', 'metricas', 'commit') if key in result}
        except Exception:
            public = {'estado': 'fallido'}
        with self.lock:
            self.jobs[identifier].update(public)

    def consultar(self, identifier):
        with self.lock:
            return dict(self.jobs[identifier]) if identifier in self.jobs else None


def pipeline(publicador=None):
    from actualizar_planes import actualizar_modelo, credenciales_locales, _validar_base
    from preparar_repo_streamlit import crear_paquete
    root = ROOT / 'modelo_powerbi'
    previous = json.loads((root / 'actual.json').read_text(encoding='utf-8'))
    _validar_base(root, previous)  # Nunca iniciar una carga completa desde este endpoint.
    usuario, password = credenciales_locales()
    try:
        actualizar_modelo(usuario=usuario, contrasena=password, salida=root)
    finally:
        usuario = password = None
    package = crear_paquete()
    manifest = json.loads((package / 'modelo_powerbi/actual.json').read_text(encoding='utf-8'))
    keys = ('modo', 'ano_desde', 'filas_descargadas', 'filas_historicas_conservadas',
            'filas_totales_publicadas', 'conexion_s', 'consulta_s', 'descarga_s', 'procesamiento_local_s', 'total_s')
    result = {'estado': 'preparado', 'version': manifest['version'],
              'metricas': {key: value for key, value in manifest.get('actualizacion', {}).items() if key in keys}}
    if publicador:
        result['commit'] = publicador.publicar(package)
        result['estado'] = 'publicado'
    return result


def servidor(trabajos, token, port=8765):
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError('La clave debe tener al menos 32 caracteres.')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respuesta(self, status, payload):
            body = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def autorizado(self):
            return hmac.compare_digest(self.headers.get('Authorization', '').encode('utf-8'), ('Bearer ' + token).encode('utf-8'))

        def do_GET(self):
            if not self.autorizado():
                return self.respuesta(401, {'error': 'No autorizado.'})
            match = re.fullmatch('/actualizaciones/([0-9a-f]{32})', self.path)
            if match:
                job = trabajos.consultar(match.group(1))
                return self.respuesta(200 if job else 404, job or {'error': 'Solicitud no encontrada.'})
            self.respuesta(404, {'error': 'Ruta no encontrada.'})

        def do_POST(self):
            if not self.autorizado():
                return self.respuesta(401, {'error': 'No autorizado.'})
            if self.path != '/actualizaciones':
                return self.respuesta(404, {'error': 'Ruta no encontrada.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError()
                self.connection.settimeout(5)
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or set(body) != {'id', 'actor'}:
                    raise ValueError()
            except (ValueError, OSError):
                return self.respuesta(400, {'error': 'Solicitud inválida.'})
            status, response = trabajos.iniciar(body['id'], body['actor'])
            self.respuesta(status, response)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--administrador', action='append', required=True)
    parser.add_argument('--repo', help='Repositorio privado; activa publicación al finalizar.')
    parser.add_argument('--rama', default='main')
    args = parser.parse_args()
    token = getpass.getpass('Clave del servicio (mínimo 32 caracteres; no se guardará): ')
    publicador = None
    if args.repo:
        from publicar_corte_github import PublicadorGitHub
        github_token = getpass.getpass('Token de GitHub del repositorio privado (no se guardará): ')
        publicador = PublicadorGitHub(args.repo, args.rama, github_token)
        github_token = None
    jobs = Trabajos(lambda: pipeline(publicador), args.administrador)
    server = servidor(jobs, token)
    token = None
    print('Servicio local: 127.0.0.1:8765. Requiere un proxy HTTPS corporativo para recibir solicitudes de nube.')
    try:
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        jobs.executor.shutdown(wait=True)


if __name__ == '__main__':
    main()
