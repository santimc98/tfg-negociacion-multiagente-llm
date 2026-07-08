# Prototipo de negociación automática entre agentes LLM

Prototipo en Python para un TFG sobre negociación automática entre dos agentes (comprador y vendedor) en un entorno controlado de cadena de suministro. Un motor determinista y un validador son la autoridad sobre la validez; los proveedores de acciones (baseline determinista, LLM local vía Ollama o LLM en la nube vía OpenRouter) solo proponen acciones candidatas. Incluye un agente juez/mediador y una interfaz web para observar la negociación en vivo.

## Puesta en marcha rápida

```bash
# Tests
python -m pytest -q

# Demo con LLM en la nube (requiere .env con OPENROUTER_API_KEY)
python src/run_openrouter_demo.py --buyer-model z-ai/glm-5.2 --seller-model z-ai/glm-5.2

# Interfaz web (http://127.0.0.1:8000)
python src/run_web.py

# Comparación experimental completa (mock + LLMs, con y sin mediador)
python src/run_full_experiment.py --scenario-count 5 --seed 42 --reasoning off
```

La clave de OpenRouter se lee de un archivo `.env` en la raíz (`OPENROUTER_API_KEY=...`), que no se versiona.

El prototipo se centra en tres variables:

- `unit_price`
- `quantity`
- `delivery_deadline`

## Estructura

```text
src/
  negotiation/
    models.py
    validator.py
    engine.py
    metrics.py
    exporter.py
  scenarios/
    generator.py
    batch.py
  experiments/
    compare_providers.py
    runner.py
  llm/
    action_parser.py
    factory.py
    ollama_provider.py
    provider.py
  main.py
  run_ollama_demo.py
  run_provider_comparison.py
tests/
  test_validator.py
  test_engine.py
  test_metrics.py
examples/
  basic_scenario.json
```

## Ejecución

Requiere Python 3.10 o superior.

```bash
python src/main.py
```

## Tests

```bash
python -m unittest discover -s tests
```

## Diseño actual

El motor ejecuta una negociación por turnos entre `buyer` y `seller`, con un máximo de rondas. El escenario separa restricciones públicas de preferencias privadas de cada agente.

Además de los targets de utilidad, cada agente tiene guardrails privados de aceptación:

- comprador: precio máximo aceptable, cantidad mínima aceptable y fecha límite máxima aceptable;
- vendedor: precio mínimo aceptable, cantidad mínima aceptable y fecha más temprana aceptable para entregar.

La negociación se modela mediante acciones explícitas:

- `PROPOSE`
- `COUNTER`
- `ACCEPT`
- `REJECT`
- `WALK_AWAY`

Cada propuesta o contraoferta válida recibe un identificador. `PROPOSE` inicia una propuesta sin referencia previa; `COUNTER`, `ACCEPT` y `REJECT` deben referenciar una propuesta válida de la contraparte. `WALK_AWAY` representa una salida terminal genérica.

`REJECT` significa rechazo específico de una propuesta concreta. Una propuesta rechazada no puede aceptarse más adelante; si se quiere plantear algo igual o parecido debe emitirse como una nueva propuesta con nuevo `proposal_id`.

Un acuerdo solo se crea cuando un agente acepta explícitamente la última propuesta válida, no rechazada, de la contraparte y esos términos respetan también sus guardrails privados. El acuerdo conserva exactamente los términos aceptados.

Las métricas incluyen utilidad de comprador y vendedor, utilidad conjunta, viabilidad privada por agente y diferencia absoluta entre utilidades (`agreement_balance_gap`).

Cada turno guarda un snapshot del estado posterior: última propuesta válida por agente, propuestas activas, propuestas rechazadas, propuestas aceptadas, propuesta activa principal y motivo del último cambio de estado. Esto permite reconstruir la evolución de la negociación sin inferirla desde texto libre.

El módulo `negotiation.exporter` exporta resultados completos a JSON con escenario, historial, acuerdo, métricas y motivo de parada. El módulo `scenarios.batch` ejecuta lotes de escenarios simulados y devuelve métricas agregadas para evaluación experimental.

El módulo `scenarios.generator` incluye `generate_simulated_scenarios(...)` para crear escenarios reproducibles con variaciones controladas en precios, cantidades y plazos. El módulo `experiments.runner` combina generación, batch simulation y exportación JSON para ejecuciones experimentales simples del TFG.

La implementación usa un `MockNegotiationProvider` para simular acciones. También existe un proveedor local basado en Ollama que mantiene la misma interfaz.

## Proveedores de acciones

El motor acepta cualquier proveedor que implemente la interfaz `ActionProvider`. Actualmente hay dos opciones:

- `mock`: baseline determinista para pruebas y comparaciones reproducibles.
- `ollama`: proveedor LLM local basado en Ollama.

La seleccion se hace con `llm.factory.create_provider(...)` o desde los runners experimentales.

## Ollama

El proveedor Ollama vive en `src/llm/ollama_provider.py`. Usa la API local `/api/chat` y solicita salida estructurada JSON con los campos:

- `action_type`
- `target_offer_id`
- `offer_terms`
- `rationale`

El LLM no valida el protocolo ni decide si una accion es aceptable. Solo propone una accion estructurada. El motor y `negotiation.validator` siguen siendo la autoridad: validan referencias, restricciones publicas, guardrails privados, propuestas rechazadas y cierre de acuerdos.

El modelo principal de pruebas locales pasa a ser `gemma4:26b`. En este entorno `qwen3.5:27b` ha mostrado timeouts tempranos, por lo que no se toma por ahora como modelo principal de experimentacion.

Para mejorar robustez y latencia, el proveedor Ollama:

- usa prompts mas cortos y auditables;
- envia solo historial reciente relevante;
- expone `history_limit` en configuracion;
- pide `rationale` nulo o una frase muy corta;
- instruye al modelo a devolver `WALK_AWAY` si no puede emitir una accion limpia.

Ejemplo de ejecucion con Ollama:

```bash
python src/run_ollama_demo.py --model gemma4:26b --base-url http://localhost:11434
```

Si tu modelo local usa otro nombre, cambialo con `--model`. La demo no requiere interfaz grafica.

Los experimentos reproducibles tambien pueden usar Ollama mediante `experiments.runner.run_reproducible_experiment(provider_kind="ollama", ...)`. Para comparaciones academicas, `provider_kind="mock"` se mantiene como baseline.

## Comparacion experimental

El modulo `experiments.compare_providers` ejecuta el baseline mock y Ollama sobre exactamente los mismos escenarios simulados, usando la misma semilla, numero de escenarios y limite de rondas.

```bash
python src/run_provider_comparison.py --seed 42 --scenario-count 10 --max-rounds 5 --model gemma4:26b
```

La salida de consola muestra una tabla compacta. Tambien se generan:

- `experiment_outputs/comparison/comparison_summary.json`
- `experiment_outputs/comparison/comparison_runs.json`

El resumen comparativo incluye tasa de acuerdos, viabilidad publica y privada, salidas invalidas, abandonos, finalizaciones por limite de rondas, utilidades, equilibrio y latencia media del proveedor.

Estas metricas permiten valorar si un LLM negocia bien dentro del entorno controlado: debe producir pocas salidas invalidas, alcanzar acuerdos viables, evitar rondas innecesarias y mantener utilidades razonablemente equilibradas. La comparacion no pretende identificar un modelo universalmente mejor, sino medir la utilidad real de cada proveedor bajo las mismas condiciones experimentales.

Limitaciones actuales del proveedor local:

- no reintenta automaticamente salidas malformadas;
- no corrige acciones invalidas generadas por el modelo;
- si Ollama falla o devuelve JSON invalido, el proveedor emite una accion invalida controlada y el motor termina con `invalid_provider_output`;
- la calidad depende del modelo local, temperatura, `history_limit` y prompt;
- la reduccion de prompt e historial mejora robustez practica, pero no garantiza ausencia total de acciones invalidas.
