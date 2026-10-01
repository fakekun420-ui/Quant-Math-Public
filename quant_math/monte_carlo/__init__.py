"""
Monte Carlo Module Exports
"""

# RETIRADO el 2026-10-01: `simulator.py` (424 lineas) era un duplicado de
# `quant_math.adapter.simulate_distribution`, que es el puerto realmente en
# uso. Medido: `MonteCarloSimulator` no se instanciaba en NINGUN sitio fuera
# de su propio fichero.
#
# No era un duplicado equivalente: el motor retirado suma PnL en USD y el
# vivo devuelve FRACCION de capital. Esa diferencia es la que hace que uno
# sea comparable con el pondero 0,3 del score cientificado
# (`research_manager.score_hypothesis`) y el otro no. Con el duplicado vivo
# el score habria mezclado dos unidades en la misma suma.
#
# El paquete queda vacio a proposito: se conserva porque el directorio es un
# punto de extension con nombre, y porque el modulo vive ahora en
# `quant_math.adapter`, no en un sitio que su nombre prometiera.
__all__: list = []
