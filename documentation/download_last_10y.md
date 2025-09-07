# `download_last_10y.sh` — Documentación

Script de línea de comandos para **disparar descargas** desde tu API FastAPI (endpoint `/download/bulk`) en **bloques anuales** que cubren **los últimos 10 años**.  
Incluye modo **daemon** para ejecutar **solo al minuto 1 de cada hora**, limpieza opcional de CSV y *lock* anti-ejecuciones simultáneas.

> **Nota:** Este script **no consulta Open-Meteo directamente**. Llama a **tu API**, que es la que descarga y guarda los CSV.

---

## Requisitos

- `bash`, `curl`, `date` (GNU o BSD/macOS; el script detecta ambos).
- Tu API corriendo y exponiendo:
  - `POST /download/bulk`
  - `GET /files`
- La API debe guardar CSV en el `DATA_DIR` configurado (p. ej. `data/raw`).

---

## Instalación

1. Guarda el archivo como `download_last_10y.sh` en la raíz del proyecto.
2. Dale permisos de ejecución:
   ~~~bash
   chmod +x download_last_10y.sh
   ~~~

---

## Uso rápido

### Ejecutar una vez (10 años hacia atrás)
~~~bash
./download_last_10y.sh http://localhost:8000 --start-hour 0 --end-hour 23
~~~

### Limpiar CSV **antes** de descargar (una vez)
~~~bash
./download_last_10y.sh http://localhost:8000 --clean --yes --data-dir data/raw --start-hour 0 --end-hour 23
~~~

---

## Modo daemon: **minuto 1 de cada hora**

Ejecuta y déjalo corriendo; el script dormirá hasta el **HH:01** de cada hora y lanzará la descarga.

~~~bash
# sin limpieza
./download_last_10y.sh http://localhost:8000 --daemon-min1 --start-hour 0 --end-hour 23

# con limpieza en cada ciclo
./download_last_10y.sh http://localhost:8000 --daemon-min1 --clean-each --data-dir data/raw --yes
~~~

Con **log** persistente:
~~~bash
nohup ./download_last_10y.sh http://localhost:8000 --daemon-min1 --log logs/last10y.log &
tail -f logs/last10y.log
~~~

> El script usa un **lock** (`/tmp/download_last_10y.lock`) para evitar instancias simultáneas.

---

## Flags y variables

| Opción / Variable       | Descripción                                                                 | Por defecto                  |
|-------------------------|-----------------------------------------------------------------------------|------------------------------|
| `BASE_URL` (arg1)       | URL base de tu API (ej. `http://localhost:8000`).                           | `http://localhost:8000`      |
| `--start-hour N`        | Hora inicial (0–23) para filtrar.                                          | `0`                          |
| `--end-hour N`          | Hora final (0–23) para filtrar.                                            | `23`                         |
| `--wind-only`           | Si se incluye, la API solicita solo variables de viento.                   | `false`                      |
| `--sleep S`             | Pausa (seg.) entre bloques anuales.                                        | `0.5`                        |
| `--clean`               | Borra `*.csv` en `--data-dir` **una vez** antes de descargar.              | `false`                      |
| `--clean-each`          | Borra `*.csv` **antes de cada ciclo** (solo con `--daemon-min1`).          | `false`                      |
| `--data-dir PATH`       | Carpeta local a limpiar con `--clean/--clean-each`.                        | `data/raw`                   |
| `--daemon-min1`         | Modo daemon: ejecutar **solo al minuto 1** de cada hora.                   | `false`                      |
| `--log FILE`            | Ruta de archivo de log (si no se indica, imprime en stdout).               | (vacío)                      |
| `LOCK_DIR` (env)        | Directorio de lock para evitar instancias simultáneas.                     | `/tmp/download_last_10y.lock` |

**Notas:**
- `--clean`/`--clean-each` actúan **en tu filesystem local**. Si la API corre en Docker, monta un volumen que apunte al mismo directorio.
- El rango total es **ayer → hace 10 años** (mismo mes/día cuando es posible).  
- El script envía a tu API un `POST /download/bulk` por bloque anual.

---

## ¿Qué hace exactamente?

Por cada bloque, el script envía:

~~~http
POST /download/bulk
Content-Type: application/json

{
  "start_date": "YYYY-MM-DD",
  "end_date":   "YYYY-MM-DD",
  "start_hour": 0,
  "end_hour":   23,
  "wind_only":  false,
  "cities":     null
}
~~~

La API debe:
1) Descargar desde Open-Meteo,  
2) Filtrar por horas,  
3) **Mergear** con CSV existentes evitando duplicados,  
4) Guardar un archivo por municipio (ej. `data/raw/open_meteo_riohacha.csv`).  

Para listar lo guardado, el script consulta:
~~~http
GET /files
~~~

---

## Ejemplos

### Bootstrap completo sin filtro horario
~~~bash
./download_last_10y.sh http://localhost:8000 --start-hour 0 --end-hour 23
curl -s http://localhost:8000/files | jq .
~~~

Salida típica:
~~~json
{
  "files": [
    "data/raw/open_meteo_riohacha.csv",
    "data/raw/open_meteo_maicao.csv",
    "data/raw/open_meteo_uribia.csv"
  ]
}
~~~

### Solo viento, daemon al minuto 1, con log
~~~bash
nohup ./download_last_10y.sh http://localhost:8000 --daemon-min1 --wind-only --log logs/last10y.log &
tail -f logs/last10y.log
~~~

### Limpiar antes (una vez) y luego descargar
~~~bash
./download_last_10y.sh http://localhost:8000 --clean --yes --data-dir data/raw --start-hour 6 --end-hour 18
~~~

---

## Comprobaciones rápidas

1) ¿La API responde?
~~~bash
curl -s http://localhost:8000/health
~~~

2) ¿Se ven archivos después de un ciclo?
~~~bash
curl -s http://localhost:8000/files
ls -lh data/raw
~~~

3) ¿Rutas correctas si usas Docker?
~~~bash
docker run -p 8000:8000 -v $(pwd)/data/raw:/app/data/raw tu_imagen
~~~
Así `--data-dir data/raw` en el host limpia la **misma** ruta que usa la API en el contenedor.

---

## Problemas comunes y soluciones

- **No aparecen CSV**  
  - Asegura que el API está corriendo y responde `200` en `/health`.  
  - Revisa filtro horario: prueba `--start-hour 0 --end-hour 23`.  
  - Verifica que `DATA_DIR` de la API apunta al directorio esperado (volúmenes en Docker).

- **Errores 500 desde la API / NumPy/pandas**  
  - En el servidor de la API, usa versiones compatibles:
    ~~~text
    numpy==1.26.4
    pandas==2.2.2
    bottleneck==1.3.7
    ~~~
  - Reinicia la API y vuelve a ejecutar el script.

- **Daemon “no hace nada”**  
  - Está esperando hasta el próximo **HH:01**. Revisa el `--log` o ejecuta sin `--daemon-min1` para probar al instante.

---

## Buenas prácticas

- Usa este script para **bootstrap** o reprocesos masivos.  
- Para mantener los datos al día cada hora, usa un job con tu endpoint **`/update/hourly`** (más liviano que bajar 10 años cada hora).

---

**Autor:** Eder Arley León Gómez  
**Licencia:** MIT (o la que prefieras)
