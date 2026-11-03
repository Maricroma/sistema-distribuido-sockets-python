"""Servidor worker: procesa tareas usando su propio pool de hilos."""
import argparse
from common import positive_int, serve


def process_task(task, worker_name):
    task_id = task.get('id')
    text = task.get('text')
    if not isinstance(task_id, str) or not task_id or len(task_id) > 100:
        raise ValueError('Identificador inválido.')
    if task.get('operation') != 'analyze':
        raise ValueError('Operación desconocida; usar analyze.')
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('El texto debe contener entre 1 y 4000 caracteres y no estar vacío.')
    return {
        'id': task_id, 'ok': True, 'worker': worker_name,
        'result': {'characters': len(text), 'words': len(text.split()), 'uppercase': text.upper()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=6001)
    parser.add_argument('--threads', type=positive_int, default=4)
    parser.add_argument('--name', default='worker-1')
    args = parser.parse_args()
    try:
        serve(args.host, args.port, args.threads, lambda task: process_task(task, args.name))
    except OSError as error:
        print(f'No se pudo ejecutar el worker: {error}')


if __name__ == '__main__':
    main()
