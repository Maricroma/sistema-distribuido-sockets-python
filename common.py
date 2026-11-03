"""Protocolo compartido: un objeto JSON UTF-8 terminado en salto de línea."""
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

MAX_BYTES = 65536
TIMEOUT = 10


def send_message(sock, message):
    data = (json.dumps(message, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    if len(data) > MAX_BYTES:
        raise ValueError('Mensaje demasiado grande.')
    sock.sendall(data)


def receive_message(reader):
    # Acumular una línea completa antes de decodificar evita cortar caracteres.
    data = reader.readline(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES or not data.endswith(b'\n'):
        raise ValueError('Mensaje incompleto o demasiado grande.')
    message = json.loads(data.decode('utf-8'))
    if not isinstance(message, dict):
        raise ValueError('Se esperaba un objeto JSON.')
    return message


def request(host, port, message):
    # Una conexión por tarea; los tiempos de espera evitan bloqueos indefinidos.
    with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
        with sock.makefile('rb') as reader:
            send_message(sock, message)
            return receive_message(reader)


def serve(host, port, threads, handler):
    """Atender sockets con un pool fijo y limitar el trabajo pendiente."""
    slots = BoundedSemaphore(threads * 2)

    def handle(connection):
        try:
            with connection:
                connection.settimeout(TIMEOUT)
                with connection.makefile('rb') as reader:
                    try:
                        message = receive_message(reader)
                        response = handler(message)
                    except (ValueError, UnicodeError) as error:
                        response = {'ok': False, 'error': str(error)}
                    send_message(connection, response)
        except OSError as error:
            print(f'Error de conexión: {error}', flush=True)
        finally:
            slots.release()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((host, port))
        listener.listen(32)
        print(f'Escuchando en {host}:{port}; pool de {threads} hilos.', flush=True)
        with ThreadPoolExecutor(max_workers=threads) as pool:
            try:
                while True:
                    connection, _ = listener.accept()
                    if slots.acquire(blocking=False):
                        pool.submit(handle, connection)
                    else:
                        with connection:
                            connection.settimeout(1)
                            try:
                                send_message(connection, {'ok': False, 'error': 'Servidor ocupado.'})
                            except OSError:
                                pass
            except KeyboardInterrupt:
                print('\nCerrando; esperando las tareas en curso.', flush=True)


def positive_int(value):
    number = int(value)
    if number < 1:
        raise ValueError('El valor debe ser positivo.')
    return number
