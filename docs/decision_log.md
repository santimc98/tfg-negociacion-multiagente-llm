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

## 2026-04-29 - Robustecimiento práctico del proveedor Ollama

- `gemma4:26b` pasa a ser el modelo principal de pruebas locales. En este entorno `qwen3.5:27b` mostró timeouts tempranos, así que no se toma por ahora como modelo principal de evaluación.
- Se redujo el prompt del proveedor Ollama para disminuir latencia y ambigüedad. El prompt ahora incluye solo rangos públicos, contexto privado del rol, reglas operativas de acción e historial reciente resumido.
- Se añadió `history_limit` a la configuración del proveedor. El valor por defecto es pequeño para reducir contexto enviado y estabilizar la generación.
- El proveedor instruye explícitamente al modelo a responder `WALK_AWAY` si no puede proponer una acción limpia y a no incluir pensamiento interno, borradores ni texto fuera del JSON.
- `rationale` se mantiene opcional y breve. El esquema JSON fija longitud máxima y el parser rechaza racionales excesivamente largas.
- Se endureció el esquema de salida para reducir ambigüedad en `target_offer_id` y `rationale`, manteniendo el contrato mínimo de acción.
- Se añadieron metadatos de trazabilidad por turno y en la exportación: tipo de proveedor, modelo y latencia aproximada de llamada. Esta información sirve para comparar baseline mock frente a Ollama en análisis experimental.
- El motor y el validador siguen siendo la autoridad final. Ninguna decisión de validez, guardrails o protocolo se movió al proveedor LLM.

## 2026-06-04 - Evaluación comparativa para la tercera entrega

- Se añadió `experiments.compare_providers` para ejecutar distintos proveedores sobre el mismo conjunto materializado de escenarios. Esto garantiza que mock y Ollama reciben exactamente los mismos casos, no solo escenarios generados con parámetros similares.
- La configuración compartida registra semilla, número de escenarios y máximo de rondas. Cada proveedor registra además tipo, modelo, temperatura, límite de historial y timeout.
- La comparación añade métricas orientadas al comportamiento del proveedor: `invalid_output_rate`, `walk_away_rate`, `max_rounds_rate` y latencia media, además de acuerdos, viabilidad, rondas, utilidades y equilibrio.
- La tasa de salidas inválidas mide ejecuciones terminadas con `invalid_provider_output`; no intenta reinterpretar ni reparar las acciones del LLM.
- La latencia media se calcula desde las llamadas registradas por turno. Se presenta como indicador operativo complementario, no como medida de calidad negociadora.
- Se exportan dos archivos: un resumen comparativo ligero y resultados individuales completos para auditoría posterior.
- La salida de consola usa una tabla simple para facilitar la incorporación de resultados preliminares en la memoria del TFG.
- El objetivo de la comparación no es encontrar el mejor modelo universal. Se busca evaluar la utilidad real del sistema bajo un entorno controlado, reproducible y común a todos los proveedores.

## 2026-06-30 - Proveedor en la nube, agente juez/mediador e interfaz web

- Se añadió `OpenRouterNegotiationProvider` (`src/llm/openrouter_provider.py`), un proveedor que usa la API de OpenRouter (compatible con OpenAI) para que los agentes sean modelos en la nube (DeepSeek, Kimi K2, GLM…). Motivación: el proveedor local Ollama no alcanzaba acuerdos y presentaba latencias muy altas; los modelos en la nube permiten resultados reales y una demostración interactiva fluida. La clave se lee de la variable `OPENROUTER_API_KEY` (archivo `.env` no versionado), nunca del código.
- Se extrajo la construcción del prompt a `src/llm/negotiation_prompt.py`, compartida por los proveedores Ollama y OpenRouter. Así existe una única fuente de verdad para el contexto enviado al modelo (rangos públicos, contexto privado del rol, reglas de acción e historial reciente), lo que facilita documentar y diagramar el flujo de información.
- Se añadió un agente **juez/mediador** (`src/negotiation/mediator.py`). El `RuleBasedMediator` es un tercero neutral que, como mediador de confianza, conoce los valores de reserva privados de ambas partes y calcula un compromiso situado en el solape de sus límites de aceptación (precio, cantidad y plazo). Si algún solape es vacío (no existe zona de posible acuerdo) declara un impasse. Esto responde a la sugerencia del director de incorporar un juez/mediador para ayudar a finalizar la negociación y ataca el problema observado de negociaciones que no cierran.
- Decisión de diseño del mediador: la propuesta de compromiso se **tabula como una opción adicional** en nombre de la contraparte, sin sustituir su última oferta propia. El agente que tiene el turno puede aceptarla (ACCEPT) bajo sus propios guardrails o seguir negociando. Así se preserva la autonomía de los agentes y la invariante de que un acuerdo solo existe cuando un agente acepta explícitamente. Por construcción, un compromiso aceptado es privadamente viable para ambas partes. Se añadió el motivo de parada `mediator_impasse` y la marca `mediated` en el acuerdo.
- El motor (`engine.run`) acepta ahora un `mediator` opcional y un `mediation_start_round`; por defecto el comportamiento es idéntico al anterior (sin mediador). Se añadió un callback `on_turn` que permite transmitir cada turno en tiempo real sin alterar el resultado.
- Se desarrolló una **interfaz web** (`src/web`, FastAPI + SSE) con un frontend de página única. Permite configurar el escenario y los modelos de cada agente, activar el mediador, lanzar la negociación y observar en vivo, turno a turno, las propuestas, contraofertas, el razonamiento de cada agente, la intervención del mediador y las métricas finales. Esto materializa el objetivo de visualizar el proceso de negociación.
- Se añadió `experiments.full_comparison`, que ejecuta la matriz completa (baseline mock y cada modelo LLM, cada uno con y sin mediador) sobre los mismos escenarios y semilla, y exporta una tabla **solo numérica** (CSV) además del JSON, para facilitar la comparativa pedida por el director. Se incorporó `mediated_agreement_rate` a las métricas agregadas.
