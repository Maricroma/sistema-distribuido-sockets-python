# Procesamiento distribuido de tareas con sockets

Trabajo práctico de **Programación Sobre Redes**. Se propone una arquitectura distribuida y se implementa un prototipo Python que recibe tareas, las distribuye entre servidores workers y devuelve resultados al cliente.

## Interpretación de la consigna

El punto 1 pide **diseñar** una arquitectura con clientes móviles/web, balanceador, workers con pools de hilos, RabbitMQ y almacenamiento. El punto 2 pide **implementar en Python** un servidor y un cliente que intercambien tareas y resultados mediante sockets.

Esta entrega distingue ambos alcances. El diseño completo está en [DIAGRAMA.md](DIAGRAMA.md); el prototipo usa sockets directos y no requiere servicios externos. Si la cátedra exige que todos los componentes del diagrama estén desplegados, este prototipo debe ampliarse: esa exigencia no aparece explícita en el punto 2.

## Contexto y teoría

Un sistema distribuido tiene procesos independientes que cooperan mediante una red. Pueden ejecutarse en distintas computadoras; durante el desarrollo se pueden iniciar todos en una sola computadora utilizando diferentes puertos.

| Concepto | Función |
| --- | --- |
| Cliente | Solicita una tarea y utiliza el resultado. |
| Socket | Extremo de una comunicación de red. Se identifica mediante una dirección y un puerto. |
| Coordinador | Recibe solicitudes y decide a qué worker enviarlas. |
| Worker | Proceso servidor que realiza el trabajo asignado. |
| Pool de hilos | Grupo de hilos reutilizados para atender varias tareas concurrentes dentro de un proceso. |
| Balanceador | Reparte conexiones o solicitudes entre servidores. |
| Cola de mensajes | Intermediario que desacopla productores y consumidores de tareas. |
| Almacenamiento compartido | Conserva datos accesibles por distintos servidores; su disponibilidad depende del despliegue. |

**Un hilo no equivale a un servidor distribuido.** En este proyecto cada worker es un proceso independiente, tiene su propio socket y utiliza internamente un pool de hilos. El coordinador también tiene un pool para atender varios clientes.

Los hilos permiten concurrencia de operaciones de red. No debe asumirse que acelerarán cálculos intensivos de CPU en una instalación convencional de CPython; para ese caso pueden convenir procesos o servicios especializados.

## Tarea elegida

Como continuación del chat básico, se procesan textos: se cuentan caracteres y palabras y se obtiene una versión en mayúsculas. La consigna no define qué tarea ejecutar; esta operación permite observar claramente la distribución sin dependencias adicionales.

El conteo de palabras usa `str.split()`: separa por espacios en blanco, sin análisis lingüístico. El conteo de caracteres usa `len()` de Python y no pretende contar grafemas visuales.

## Archivos

```text
.
├── README.md
├── DIAGRAMA.md
├── common.py       # Protocolo y atención con pool de hilos
├── server.py       # Coordinador que distribuye tareas
├── worker.py       # Servidor que ejecuta tareas
├── client.py       # Cliente interactivo
├── test_system.py  # Pruebas de integración locales
└── .gitignore
```

## Requisitos

Python 3.9 o posterior. Solo se utilizan módulos de la biblioteca estándar; no hace falta instalar paquetes con pip, Docker ni servicios externos.

## Ejecución local

Abrir cuatro terminales en la carpeta del proyecto y ejecutar en este orden. Si el sistema utiliza `py` o `python3`, reemplazar `python` por ese comando.

**Terminal 1: worker 1**

```bash
python worker.py --port 6001 --name worker-1 --threads 4
```

**Terminal 2: worker 2**

```bash
python worker.py --port 6002 --name worker-2 --threads 4
```

**Terminal 3: coordinador**

```bash
python server.py --port 5000 --workers 127.0.0.1:6001 127.0.0.1:6002
```

**Terminal 4: cliente**

```bash
python client.py
```

Enviar `Hola mundo`, luego otro texto. Cada respuesta muestra el ID, el worker que atendió la tarea y el resultado. Sin otros clientes, los destinos alternan entre worker-1 y worker-2. Se pueden abrir más clientes para enviar tareas concurrentes.

Salir del cliente con `éxito`, `exito` o `salir`. Detener los servidores con `Ctrl+C`; pueden tardar mientras terminan o vencen las operaciones en curso.

El chat anterior también utiliza el puerto 5000: detenerlo antes de iniciar este coordinador.

## Protocolo y recorrido de una tarea

1. El cliente genera un UUID para identificar la tarea.
2. Abre una conexión TCP con el coordinador y envía un objeto JSON terminado en `\n`.
3. El coordinador elige un worker por turnos (**round-robin**), protegiendo el turno con un bloqueo entre hilos.
4. Abre una conexión TCP al worker y reenvía la tarea.
5. Un hilo del pool del worker valida y procesa el texto.
6. El resultado regresa al coordinador y luego al cliente; las conexiones se cierran.

Solicitud:

```json
{"id":"ejemplo-1","operation":"analyze","text":"Hola mundo"}
```

Respuesta:

```json
{"id":"ejemplo-1","ok":true,"worker":"worker-1","result":{"characters":10,"words":2,"uppercase":"HOLA MUNDO"}}
```

Los mensajes se codifican en UTF-8. El lector acumula una línea completa antes de decodificarla, porque TCP puede dividir un mensaje o agrupar bytes de distintos envíos. El protocolo limita cada mensaje a 65536 bytes y cada texto a 4000 caracteres.

Cada operación de socket tiene un tiempo de espera de 10 segundos; no es un plazo global garantizado para toda la tarea. Cada servidor limita las conexiones admitidas al doble del tamaño de su pool, contando trabajo activo y pendiente. Si se alcanza el límite, devuelve un error de servidor ocupado.

## Errores y limitaciones

- Se controlan JSON inválido, mensajes incompletos, textos vacíos o excesivos y operaciones desconocidas.
- Un worker inaccesible produce una respuesta de error. El coordinador sigue vivo y continúa con el siguiente destino en solicitudes posteriores.
- No se reintenta automáticamente una tarea fallida: si se pierde la respuesta, podría haberse ejecutado. El sistema no garantiza ejecución exactamente una vez.
- Round-robin reparte por turnos, sin medir carga ni retirar automáticamente workers caídos.
- El prototipo no persiste tareas ni resultados. No utiliza la base SQLite del trabajo anterior.
- El coordinador es un punto único de fallo en esta versión local.
- No se implementan autenticación ni TLS. La configuración predeterminada escucha solo en localhost y está destinada a pruebas educativas locales.
- La arquitectura completa propone servicios separados y redundancia; desplegarla requiere configuración adicional, no solo cambiar los puertos del prototipo.

## Pruebas

```bash
python -m unittest -v test_system.py
```

Las pruebas levantan dos workers y un coordinador en procesos independientes con puertos locales temporales, verifican distribución, concurrencia, Unicode, validación y respuesta ante la caída de un worker. También prueban la fragmentación de un mensaje TCP. No requieren que los servidores de la demostración estén ejecutándose.

Para una demostración manual, iniciar las cuatro terminales, enviar varios textos, observar qué worker responde, detener uno de los workers y comprobar que las tareas asignadas a ese worker muestran un error mientras las del otro siguen funcionando.

## Relación con la arquitectura propuesta

| Elemento de la consigna | Diagrama completo | Prototipo ejecutable |
| --- | --- | --- |
| Clientes móviles y web | Incluidos mediante HTTPS | Cliente de consola Python |
| Nginx / HAProxy | Balancea entre APIs | No desplegado; el coordinador reparte tareas |
| Workers con pool | Incluidos | Dos procesos worker, cada uno con su pool |
| RabbitMQ | Tareas y respuestas entre servidores | Sustituido por sockets directos |
| PostgreSQL y S3 | Registros y objetos, respectivamente | No implementados |
| Tareas y resultados | Recorrido completo | Implementado con TCP y JSON |

## Referencias

- [Sockets en Python](https://docs.python.org/3/howto/sockets.html).
- [ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html).
- [RabbitMQ: colas de trabajo](https://www.rabbitmq.com/tutorials/tutorial-two-python).
- [Nginx: grupos de servidores y balanceo TCP](https://nginx.org/en/docs/stream/ngx_stream_upstream_module.html).
