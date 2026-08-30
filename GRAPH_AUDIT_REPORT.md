# Quant-Math-Public — Auditoría del Ecosistema v1.4.0

> Generado con Graphify v0.9.52 + NetworkX analysis — 2026-08-30

---

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Nodos totales** | 2,810 |
| **Edges totales** | 5,397 |
| **Archivos Python** | 155 |
| **Comunidades detectadas** | 57 |
| **Componentes débilmente conectados** | 11 |
| **Nodos huérfanos (grado ≤ 1)** | 1,271 (45%) |
| **Tests** | 137 (0 warnings) |

**Salud general: AMARILLA** — Núcleo sólido, pero deuda técnica significativa en módulos legacy y stubs vacíos.

---

## 1. GOD NODES — Nodos Más Centrales

Los nodos con mayor centralidad de grado son los pilares del sistema:

| Rank | Centralidad | Nodo | Archivo |
|------|-------------|------|---------|
| 1 | 0.0249 | `typing` | stdlib |
| 2 | 0.0246 | `numpy` | externa |
| 3 | **0.0231** | `DecisionEngine` | `quant_math/decision_engine/main.py` |
| 4 | 0.0217 | `routes` (WebUI mock) | `webui/backend/webui/api/routes.py` |
| 5 | **0.0214** | `run_full_e2e_test` | `test_full_system_e2e.py` |
| 6 | **0.0206** | `quant_math/__init__` | `quant_math/__init__.py` |
| 7 | 0.0185 | `cli/main` | `quant_math/cli/main.py` |
| 8 | **0.0182** | `QuantMathAdapter` | `quant_math/autonomous_research/adapters/quant_math_adapter.py` |
| 9 | 0.0178 | `OrchestratorConfig` | `quant_math/orchestrator.py` |
| 10 | 0.0139 | `AQDERunner` | `aqde_runner.py` |

**Hallazgo:** Los 3 nodos más centrales del core son `DecisionEngine`, `OrchestratorConfig` y `QuantMathAdapter`. Son los puntos de acoplamiento más críticos.

---

## 2. BRIDGE NODES — Nodos Puente (Betweenness)

Estos nodos conectan comunidades distintas:

| Centralidad | Nodo | Rol |
|-------------|------|-----|
| 0.0012 | `DecisionEngine` | Puente entre generación y ejecución |
| 0.0009 | `AQDERunner` | Puente entre discovery y orquestación |
| 0.0006 | `QuantMathAdapter` | Puente entre AQDE y core |
| 0.0006 | `Orchestrator` | Puente central del sistema |
| 0.0005 | `KBPersistence` | Puente entre memoria y ejecución |

---

## 3. COMUNIDADES DETECTADAS (Top 10)

| Comunidad | Nodos | Paquetes Principales |
|-----------|-------|---------------------|
| 0 | 465 | aqde_runner, model_based_generator, quant_math, tests, tools |
| 1 | 445 | algo_trading, backtesting, data_acquisition, expectation (LEGACY) |
| 2 | 409 | quant_math (core package) |
| 3 | 184 | aqde_runner, quant_math |
| 4 | 125 | model_based_generator, regime_detection, spectral_analysis |
| 5 | 117 | webui (FRONTEND) |
| 6 | 93 | quant_math (ML/risk internals) |
| 7 | 85 | risk_management |
| 8 | 70 | signal_processing |
| 9 | 52 | quant_math (monte carlo) |

**Hallazgo crítico:** La comunidad 1 (445 nodos) es el **ecosistema legacy** que coexiste con el núcleo nuevo en comunidad 2. Hay overlap significativo.

---

## 4. ANÁLISIS DE DUPLICACIONES

### Módulos con funcionalidad solapada

| Funcionalidad | Paquete Legacy | Paquete Nuevo | Nodos (Legacy) | Nodos (Nuevo) |
|---------------|----------------|---------------|----------------|---------------|
| Expectation | `expectation/` | `quant_math/expectation/` | 164 | 96 |
| Risk | `risk/` | `quant_math/risk/` | 154 | 122 |
| Monte Carlo | `monte_carlo/` | `quant_math/monte_carlo/` | 37 | 36 |

**Recomendación:** Los paquetes legacy en raíz están siendo importados por `root/__init__.py` y algunos tests. Consolidar en `quant_math/` y deprecar los legacy.

---

## 5. DEPENDENCIAS ENTRE PAQUETES

```
tests ──(43)──> quant_math
root ──(24)──> quant_math
root ──(15)──> backtesting
root ──(11)──> execution
root ──(11)──> order_management
root ──(10)──> algo_trading
quant_math ──(4)──> backtesting
quant_math ──(3)──> optimization
quant_math ──(2)──> data_acquisition
algo_trading ──(6)──> order_management
backtesting ──(2)──> order_management
```

**Hallazgo:** `root/__init__.py` importa masivamente de los paquetes legacy (61 imports), creando un acoplamiento innecesario.

---

## 6. MÓDULOS ROTOS / STUBS VACÍOS

| Módulo | Estado | Nodos | Problema |
|--------|--------|-------|----------|
| `pca_analysis/` | **ROTO** | 26 | Importa `.pca` inexistente |
| `modeling/` | Stub vacío | 1 | Solo comentario "# Probabilistic Modeling" |
| `volatility/` | Stub vacío | 1 | Solo comentario "# Volatility Estimation" |
| `utils/` | Stub vacío | 1 | Solo comentario "# Utilities" |
| `monte_carlo/` (raíz) | Solo `__init__` | 37 | Duplicado con `quant_math/monte_carlo/` |

---

## 7. COBERTURA DE TESTS

### Paquetes CON tests
`algo_trading`, `backtesting`, `data_acquisition`, `data_processing`, `execution`, `optimization`, `order_management`, `portfolio_construction`, `quant_math`, `risk`, `risk_management`

### Paquetes SIN tests
`expectation`, `ml_quant`, `modeling`, `monte_carlo`, `pca_analysis`, `regime_detection`, `signal_processing`, `spectral_analysis`, `utils`, `volatility`, `webui`

**Cobertura: ~55%** de paquetes tienen tests. Los módulos sin tests son mayormente legacy o stubs.

---

## 8. ANÁLISIS DE CLUSTERS (Módulos Aislados)

**1,271 nodos huérfanos (45% del total)** distribuidos en:

| Paquete | Huérfanos | Causa |
|---------|-----------|-------|
| quant_math | 486 | Internos del package (normal) |
| regime_detection | 94 | Poco integrado al core |
| tests | 68 | Nodos de test aislados |
| spectral_analysis | 64 | Sin conexiones al core |
| webui | 61 | **NO CONECTADO** al backend real |
| signal_processing | 54 | Sin conexiones al core |
| risk_management | 42 | Parcialmente integrado |
| data_acquisition | 39 | bien integrado vía imports |
| data_processing | 34 | Orfe |

---

## 9. WEBUI — GAP DE INTEGRACIÓN

| Componente | Estado |
|------------|--------|
| Frontend (Vue 3) | Completo, 6 vistas |
| Backend (FastAPI) | **Mock data** — no conectado a quant_math |
| API routes | Sirven datos hardcoded |
| WebSocket | Implementado pero sin datos reales |

**Gap documentado en:** `ARCHITECTURE_REUSE_REPORT.md`

---

## 10. DEUDA TÉCNICA IDENTIFICADA

### Crítica
1. **`pca_analysis/` roto** — importa módulo inexistente
2. **WebUI sin integración** — backend con mock data
3. **Sin CI/CD** — testing manual únicamente

### Alta
4. **Duplicación expectation/risk/monte_carlo** — dos versiones de cada uno
5. **45% nodos huérfanos** — módulos sin conexiones al core
6. **`postgres_kb.py` naming engañoso** — implementa JSONL, no PostgreSQL

### Media
7. **3 stubs vacíos** — modeling, volatility, utils
8. **`root/__init__.py`** — importa de 5 paquetes legacy
9. **11 comunidades** — fragmentación del grafo

### Baja
10. **`Monitor` archivo vacío** — placeholder sin contenido
11. **`progreso_qwen.txt`** — archivo de progreso obsoleto

---

## 11. RECOMENDACIONES

### Inmediatas (v1.4.2)
- [ ] Eliminar `pca_analysis/` o implementarlo
- [ ] Renombrar `postgres_kb.py` → `jsonl_kb.py`
- [ ] Eliminar `Monitor` y `progreso_qwen.txt`

### Corto plazo (v1.5.0)
- [ ] Consolidar `expectation/`, `risk/`, `monte_carlo/` en `quant_math/`
- [ ] Conectar WebUI backend a módulos reales
- [ ] Agregar tests para `expectation`, `regime_detection`, `ml_quant`
- [ ] Configurar CI/CD básico (GitHub Actions)

### Mediano plazo (v2.0)
- [ ] Eliminar paquetes legacy de raíz
- [ ] Limpiar stubs vacíos o implementar
- [ ] Reducir nodos huérfanos integrando módulos aislados

---

## 12. ARCHIVOS GENERADOS

| Archivo | Descripción |
|---------|-------------|
| `graphify-out/graph.json` | Knowledge graph completo (2,810 nodos, 5,397 edges) |
| `graphify-out/cache/` | Cache de extrucción AST |
| `GRAPH_AUDIT_REPORT.md` | Este reporte |

### Para visualizar el grafo
```bash
# Consultar conexiones
graphify query "what connects orchestrator to decision engine?" --graph graphify-out/graph.json

# Encontrar caminos
graphify path "AQDERunner" "Orchestrator" --graph graphify-out/graph.json

# Explicar un nodo
graphify explain "DecisionEngine" --graph graphify-out/graph.json
```

---

*Generado por Graphify v0.9.52 + NetworkX analysis — Quant-Math-Public v1.4.0*
