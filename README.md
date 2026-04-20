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
  scenarios/
    generator.py
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

## Diseño inicial

El motor ejecuta una negociación por turnos entre `buyer` y `seller`, con un máximo de rondas. Cada oferta se valida contra las restricciones del escenario y se registra en un log estructurado.

La implementación usa un `MockNegotiationProvider` para simular propuestas. Más adelante puede sustituirse por un proveedor conectado a un LLM local open-source manteniendo la misma interfaz.
