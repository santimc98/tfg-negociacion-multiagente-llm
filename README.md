# Prototipo de negociación automática

Esqueleto inicial en Python para un TFG sobre negociación automática entre dos agentes en un entorno controlado de cadena de suministro.

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
  llm/
    provider.py
  main.py
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

Un acuerdo solo se crea cuando un agente acepta explícitamente la última propuesta válida de la contraparte y esos términos respetan también sus guardrails privados. El acuerdo conserva exactamente los términos aceptados.

Las métricas incluyen utilidad de comprador y vendedor, utilidad conjunta, viabilidad privada por agente y diferencia absoluta entre utilidades (`agreement_balance_gap`).

Cada turno guarda un snapshot del estado posterior: última propuesta válida por agente, propuestas rechazadas, propuesta activa y motivo del último cambio de estado. Esto permite reconstruir la evolución de la negociación sin inferirla desde texto libre.

El módulo `negotiation.exporter` exporta resultados completos a JSON con escenario, historial, acuerdo, métricas y motivo de parada. El módulo `scenarios.batch` ejecuta lotes de escenarios simulados y devuelve métricas agregadas para evaluación experimental.

La implementación usa un `MockNegotiationProvider` para simular acciones. Más adelante puede sustituirse por un proveedor conectado a un LLM local open-source manteniendo la misma interfaz.
