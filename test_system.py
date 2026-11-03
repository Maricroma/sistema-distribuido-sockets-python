"""Pruebas con procesos reales y puertos temporales de localhost."""
import concurrent.futures
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from common import receive_message, request

ROOT = Path(__file__).resolve().parent


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.processes = []
        cls.ports = []
        try:
            for index in range(2):
                port = free_port()
                cls.start('worker.py', port, '--name', f'worker-{index + 1}')
                cls.ports.append(port)
            cls.server_port = free_port()
            cls.start('server.py', cls.server_port, '--workers',
                      *[f'127.0.0.1:{port}' for port in cls.ports])
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def start(cls, script, port, *args):
        process = subprocess.Popen([sys.executable, str(ROOT / script), '--port', str(port), *args],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.processes.append(process)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'{script} terminó al iniciar.')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    return
            except OSError:
                time.sleep(.05)
        raise RuntimeError(f'{script} no inició.')

    @classmethod
    def tearDownClass(cls):
        for process in cls.processes:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    def task(self, identifier, text='Hola mundo'):
        return request('127.0.0.1', self.server_port,
                       {'id': str(identifier), 'operation': 'analyze', 'text': text})

    def test_01_distribution(self):
        results = [self.task(index) for index in range(4)]
        self.assertEqual([r['worker'] for r in results],
                         ['worker-1', 'worker-2', 'worker-1', 'worker-2'])
        self.assertEqual(results[0]['result']['words'], 2)

    def test_02_concurrent_unicode(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: self.task(i, 'programación café'), range(12)))
        for index, response in enumerate(results):
            self.assertTrue(response['ok'])
            self.assertEqual(response['id'], str(index))
            self.assertEqual(response['result']['uppercase'], 'PROGRAMACIÓN CAFÉ')

    def test_03_validation(self):
        self.assertFalse(self.task('empty', '')['ok'])
        self.assertFalse(self.task('large', 'a' * 4001)['ok'])
        response = request('127.0.0.1', self.server_port,
                           {'id': 'bad', 'operation': 'unknown', 'text': 'hola'})
        self.assertFalse(response['ok'])

    def test_04_fragmentation(self):
        with socket.create_connection(('127.0.0.1', self.server_port), timeout=5) as sock:
            data = '{"id":"fragment","operation":"analyze","text":"á"}\n'.encode('utf-8')
            cut = data.index('á'.encode('utf-8')) + 1
            sock.sendall(data[:cut])
            sock.sendall(data[cut:])
            with sock.makefile('rb') as reader:
                self.assertEqual(receive_message(reader)['result']['uppercase'], 'Á')

    def test_05_invalid_json(self):
        with socket.create_connection(('127.0.0.1', self.server_port), timeout=5) as sock:
            sock.sendall(b'not-json\n')
            with sock.makefile('rb') as reader:
                self.assertFalse(receive_message(reader)['ok'])

    def test_99_worker_failure(self):
        self.processes[0].terminate()
        self.processes[0].wait(timeout=5)
        responses = [self.task('failure-1'), self.task('failure-2')]
        self.assertEqual(sum(bool(r['ok']) for r in responses), 1)
        self.assertIn('no disponible', next(r['error'] for r in responses if not r['ok']))


if __name__ == '__main__':
    unittest.main()
