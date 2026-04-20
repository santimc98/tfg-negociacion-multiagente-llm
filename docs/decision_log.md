# Decision Log

## 2026-04-20 - Guardrails privados y endurecimiento del protocolo

- Se mantienen separadas las restricciones públicas del escenario y las preferencias privadas de los agentes. Las restricciones públicas definen el espacio legal de negociación; las preferencias y guardrails privados definen utilidad y aceptabilidad interna.
- Se añadieron `BuyerGuardrails` y `SellerGuardrails` como modelos separados. Esto evita mezclar límites del comprador y del vendedor en una estructura ambigua y deja claro qué reglas aplica cada rol al aceptar.
- Para el comprador se modelan tres límites privados: `buyer_max_acceptable_unit_price`, `buyer_min_acceptable_quantity` y `buyer_latest_acceptable_deadline`.
- Para el vendedor se modelan `seller_min_acceptable_unit_price`, `seller_min_acceptable_quantity` y `seller_earliest_acceptable_deadline`. Se eligió una fecha mínima de entrega porque, en cadena de suministro, el vendedor puede necesitar una fecha no anterior a su capacidad operativa real.
- `PROPOSE` representa una propuesta inicial o nueva propuesta independiente y no puede incluir `target_offer_id`.
- `COUNTER` representa una respuesta directa, por lo que requiere `target_offer_id` y debe apuntar a una propuesta válida previa de la contraparte.
- `REJECT` se define como rechazo específico de una propuesta concreta, por lo que requiere `target_offer_id`. La salida genérica sin propuesta objetivo queda representada por `WALK_AWAY`.
- `ACCEPT` solo puede cerrar acuerdo si apunta a una propuesta válida de la contraparte, si esa propuesta es la última propuesta válida de esa contraparte y si sus términos cumplen los guardrails privados del agente que acepta.
- Un fallo de estructura de protocolo o de aceptabilidad privada se trata como `invalid_provider_output`. Esta decisión mantiene el motor determinista y evita reparar o reinterpretar acciones inválidas generadas por un proveedor mock o futuro LLM.
- Las métricas incorporan `private_feasibility_buyer`, `private_feasibility_seller` y `agreement_balance_gap` para evaluar no solo si hay acuerdo público válido, sino también su aceptabilidad privada y equilibrio relativo.

## 2026-04-20 - Trazabilidad y preparación para evaluación por lotes

- Se introdujo `NegotiationState` como snapshot operativo del estado tras cada turno. El objetivo es que el análisis posterior no tenga que reconstruir estado mediante inferencias frágiles desde el historial textual.
- El estado guarda última propuesta válida por agente, propuestas rechazadas, propuesta activa y motivo del último cambio. Esta información es suficiente para explicar la evolución básica de una negociación sin añadir una máquina de estados compleja.
- `TurnLog` conserva sus campos previos y añade `target_offer_id_resolved`, `result_summary` y `state_after`. Esta ampliación mantiene compatibilidad con el historial actual y mejora la trazabilidad para depuración y análisis experimental.
- Un `REJECT` válido no termina la negociación. Se registra la propuesta rechazada y la negociación puede continuar hasta acuerdo, `WALK_AWAY`, salida inválida o límite de rondas.
- Se añadió `negotiation.exporter` para producir JSON estructurado con escenario, historial, acuerdo, métricas y `stopped_reason`. La serialización convierte fechas y enums a valores JSON nativos.
- Se añadió `scenarios.batch` para ejecutar múltiples negociaciones sobre escenarios simulados. El batch crea proveedores nuevos por ejecución para evitar estado accidental entre negociaciones.
- El resumen agregado usa tasas y medias simples: total de ejecuciones, tasa de acuerdos, tasa de acuerdos públicos y privadamente viables, rondas medias, utilidades medias y balance medio.

## 2026-04-20 - Semántica cerrada de REJECT y runner experimental reproducible

- `REJECT` queda definido como rechazo específico e irreversible de una propuesta concreta. La propuesta permanece en el historial para trazabilidad, pero no puede aceptarse posteriormente.
- Si una parte quiere volver a plantear términos equivalentes a una propuesta rechazada, debe emitir una nueva acción `PROPOSE` o `COUNTER` con un nuevo `proposal_id`. Esto evita ambigüedad entre identidad de propuesta y equivalencia de términos.
- El motor y el validador bloquean `ACCEPT` sobre propuestas rechazadas. La comprobación se mantiene junto al resto de reglas de aceptación: propuesta válida, contraparte, última propuesta válida de esa contraparte y guardrails privados.
- `NegotiationState` ahora distingue propuestas activas, rechazadas y aceptadas mediante colecciones simples de identificadores. Se conserva `active_offer_id` como acceso rápido a la propuesta activa principal.
- Se añadió generación reproducible de múltiples escenarios simulados mediante `generate_simulated_scenarios(count, seed)`. Las variaciones afectan precios, cantidades y plazos manteniendo coherencia entre restricciones públicas, preferencias y guardrails.
- Se añadió `experiments.runner` como utilidad de evaluación académica: genera escenarios, ejecuta batch simulation y exporta resumen e individuales a JSON. No busca cubrir necesidades de producción.
- La exportación agregada se mantiene como JSON simple con `summary` y `runs`, para facilitar análisis posterior con herramientas externas.

## 2026-04-20 - Integración controlada de Ollama como proveedor LLM local

- Se añadió `OllamaNegotiationProvider` como proveedor opcional, manteniendo `MockNegotiationProvider` como baseline determinista. Esto permite comparar un comportamiento controlado contra un proveedor LLM local sin cambiar el motor.
- Se eligió Ollama porque ofrece ejecución local, reduce dependencia de servicios externos y facilita experimentos reproducibles en un entorno universitario. El nombre del modelo, URL, temperatura y timeout son configurables.
- El proveedor usa `/api/chat` y solicita salida estructurada JSON mediante un esquema. La acción esperada contiene `action_type`, `target_offer_id`, `offer_terms` y `rationale`.
- El motor sigue siendo la autoridad del sistema. El LLM no valida restricciones públicas, guardrails privados, referencias de propuestas, rechazos ni aceptación de acuerdos; solo emite una acción candidata.
- Se añadió `llm.action_parser` como frontera explícita entre texto/modelo y dominio. El parser convierte JSON a `NegotiationAction` y rechaza tipos básicos incorrectos antes de entregar la acción al motor.
- Si Ollama falla o devuelve JSON malformado, el proveedor genera una acción intencionalmente inválida. El motor la trata como `invalid_provider_output`, preservando trazabilidad y evitando que errores del LLM rompan el flujo.
- Se añadió `llm.factory.create_provider(...)` para seleccionar `mock` u `ollama` desde runners o demos sin acoplar el resto del sistema a una implementación concreta.
- Se añadió `src/run_ollama_demo.py` como utilidad mínima de ejecución local. No se añade interfaz gráfica en esta fase.
- Limitación actual: no hay reintentos ni reparación automática de respuestas LLM. Esta decisión favorece robustez y trazabilidad frente a sofisticación prematura.
