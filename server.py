"""Coordinador TCP: recibe tareas y las reparte entre workers remotos."""
import argparse
import itertools
import threading
from common import positive_int, request, serve


def make_dispatcher(workers):
    # Round-robin: alternar destinos. El lock protege el turno entre hilos.
    turns = itertools.cycle(workers)
    lock = threading.Lock()

    def dispatch(task):
        with lock:
            host, port = next(turns)
        try:
            response = request(host, port, task)
            if response.get('ok') and response.get('id') != task.get('id'):
                raise ValueError('El resultado no corresponde a la tarea.')
            return response
        except (OSError, ValueError, UnicodeError) as error:
            # No reintentar automáticamente: un timeout no prueba que la tarea
            # no se ejecutó. Un reintento podría duplicar efectos en otras tareas.
            return {'id': task.get('id'), 'ok': False,
                    'error': f'Worker {host}:{port} no disponible o respuesta inválida: {error}'}
    return dispatch


def endpoint(value):
    try:
        host, port = value.rsplit(':', 1)
        port = int(port)
        if not host or not 1 <= port <= 65535:
            raise ValueError
        return host, port
    except ValueError as error:
        raise argparse.ArgumentTypeError('Usar host:puerto con un puerto válido.') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--threads', type=positive_int, default=8)
    parser.add_argument('--workers', nargs='+', type=endpoint,
                        default=[('127.0.0.1', 6001), ('127.0.0.1', 6002)])
    args = parser.parse_args()
    try:
        serve(args.host, args.port, args.threads, make_dispatcher(args.workers))
    except OSError as error:
        print(f'No se pudo ejecutar el servidor: {error}')


if __name__ == '__main__':
    main()
