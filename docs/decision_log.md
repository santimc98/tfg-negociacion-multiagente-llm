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
