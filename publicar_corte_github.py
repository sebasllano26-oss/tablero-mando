"""Publicar solo las 15 tablas y el puntero en un commit de un repo privado."""
import base64
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, build_opener
from cliente_actualizacion import SinRedireccion


class PublicadorGitHub:
    def __init__(self, repo, branch, token):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or not branch or not token:
            raise ValueError('Configure repositorio, rama y token de publicación.')
        self.base, self.branch, self.token = 'https://api.github.com/repos/' + repo, branch, token

    def api(self, method, path, payload=None):
        request = Request(self.base + path, method=method,
            data=json.dumps(payload).encode('utf-8') if payload is not None else None,
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                     'Content-Type': 'application/json', 'User-Agent': 'Comfamiliar-Actualizacion',
                     'X-GitHub-Api-Version': '2022-11-28'})
        try:
            with build_opener(SinRedireccion).open(request, timeout=30) as response:
                return json.load(response)
        except Exception:
            raise RuntimeError('No se completó la publicación de datos en GitHub.') from None

    def publicar(self, paquete):
        package = Path(paquete).resolve()
        if self.api('GET', '').get('private') is not True:
            raise ValueError('El servicio solo publica datos en repositorios privados.')
        pointer = package / 'modelo_powerbi/actual.json'
        original = pointer.read_bytes()
        manifest = json.loads(original)
        if len(manifest.get('tablas', {})) != 15:
            raise ValueError('Se requieren las 15 tablas de un corte completo.')
        paths = ['modelo_powerbi/actual.json']
        for relative in manifest['tablas'].values():
            path = (package / 'modelo_powerbi' / relative).resolve()
            if not path.is_relative_to(package / 'modelo_powerbi') or path.suffix != '.parquet' or not path.is_file():
                raise ValueError('Ruta de tabla inválida.')
            paths.append(path.relative_to(package).as_posix())
        head = self.api('GET', '/git/ref/heads/' + quote(self.branch, safe=''))['object']['sha']
        old_tree = self.api('GET', '/git/commits/' + head)['tree']['sha']
        existing = self.api('GET', '/git/trees/' + old_tree + '?recursive=1')
        if existing.get('truncated'):
            raise ValueError('Árbol del repositorio incompleto.')
        hashes = {entry['path']: entry['sha'] for entry in existing['tree']}
        entries = []
        for name in paths:
            body = (package / name).read_bytes()
            digest = hashlib.sha1(b'blob ' + str(len(body)).encode('ascii') + b'\0' + body).hexdigest()
            if hashes.get(name) == digest:
                continue
            blob = self.api('POST', '/git/blobs', {'encoding': 'base64', 'content': base64.b64encode(body).decode('ascii')})
            entries.append({'path': name, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
        if not entries:
            return head
        tree = self.api('POST', '/git/trees', {'base_tree': old_tree, 'tree': entries})['sha']
        commit = self.api('POST', '/git/commits', {'message': 'Actualizar corte ' + manifest['version'],
                                               'tree': tree, 'parents': [head]})['sha']
        if pointer.read_bytes() != original:
            raise ValueError('El corte cambió; no se movió la rama.')
        self.api('PATCH', '/git/refs/heads/' + quote(self.branch, safe=''), {'sha': commit, 'force': False})
        return commit
