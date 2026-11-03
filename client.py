"""Cliente interactivo: envía textos para analizar y muestra los resultados."""
import argparse
import unicodedata
import uuid
from common import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    print('Escribí un texto para analizar. Salir: éxito, exito o salir.')
    try:
        while True:
            text = input('> ')
            if unicodedata.normalize('NFC', text.strip()).casefold() in {'éxito', 'exito', 'salir'}:
                break
            if not text.strip():
                continue
            if len(text) > 4000:
                print('El máximo es de 4000 caracteres.')
                continue
            task = {'id': str(uuid.uuid4()), 'operation': 'analyze', 'text': text}
            try:
                response = request(args.host, args.port, task)
                if response.get('ok'):
                    if response.get('id') != task['id']:
                        raise ValueError('Identificador de respuesta incorrecto.')
                    print(f"Tarea: {response['id']} | Atendida por: {response['worker']}")
                    print(response['result'])
                else:
                    print('Error:', response.get('error', 'Respuesta no válida.'))
            except (OSError, ValueError, UnicodeError) as error:
                print(f'No se pudo obtener el resultado: {error}')
    except (KeyboardInterrupt, EOFError):
        print()
    print('Cliente finalizado.')


if __name__ == '__main__':
    main()
