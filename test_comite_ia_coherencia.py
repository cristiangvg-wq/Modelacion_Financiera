"""Regresiones para coherencia entre el motor cuantitativo y el comité IA."""
import modelacion_logic as L


def test_veto_de_calidad_rechaza_recomendacion_positiva():
    salida = """
## 1. DELIBERACIÓN DEL COMITÉ INTERDISCIPLINARIO
Análisis preliminar.
## 2. ANÁLISIS DE BRECHA
N/D.
## 3. DECISIÓN FINAL DE INVERSIÓN
RECOMENDACIÓN FINAL: INVERTIR CONDICIONALMENTE
PUNTAJE DE VIABILIDAD: 7/10
## 4. FACTORES CRÍTICOS Y PUNTOS DE MONITOREO
Recalibrar el modelo.
"""
    audit = L.auditar_respuesta_comite_ia(
        salida,
        {
            "decision_modelo": "RECALIBRAR MODELO · VETO DE CALIDAD",
            "control_calidad_modelo": True,
            "vetos_calidad": ["Equity value base <= 0"],
        },
    )
    assert not audit["ok"]
    assert any("veto de calidad activo" in e.lower() for e in audit["errors"])


def test_veto_exige_mencionar_recalibracion():
    salida = """
## 1. DELIBERACIÓN DEL COMITÉ INTERDISCIPLINARIO
Análisis preliminar.
## 2. ANÁLISIS DE BRECHA
N/D.
## 3. DECISIÓN FINAL DE INVERSIÓN
RECOMENDACIÓN FINAL: NO INVERTIR
PUNTAJE DE VIABILIDAD: 4/10
## 4. FACTORES CRÍTICOS Y PUNTOS DE MONITOREO
Revisar los supuestos.
"""
    audit = L.auditar_respuesta_comite_ia(
        salida,
        {
            "decision_modelo": "RECALIBRAR MODELO · VETO DE CALIDAD",
            "control_calidad_modelo": True,
            "vetos_calidad": ["Equity value base <= 0"],
        },
    )
    assert not audit["ok"]
    assert any("omite el veto de calidad" in e.lower() for e in audit["errors"])


def test_divergencia_de_motor_exige_justificacion_explicita():
    salida = """
## 1. DELIBERACIÓN DEL COMITÉ INTERDISCIPLINARIO
Análisis preliminar.
## 2. ANÁLISIS DE BRECHA
N/D.
## 3. DECISIÓN FINAL DE INVERSIÓN
RECOMENDACIÓN FINAL: INVERTIR
PUNTAJE DE VIABILIDAD: 7/10
## 4. FACTORES CRÍTICOS Y PUNTOS DE MONITOREO
Revisar los supuestos.
"""
    audit = L.auditar_respuesta_comite_ia(
        salida,
        {"decision_modelo": "NEUTRAL / MONITOREAR", "control_calidad_modelo": False},
    )
    assert not audit["ok"]
    assert any("DIVERGENCIA FRENTE AL MOTOR CUANTITATIVO" in e for e in audit["errors"])


def test_divergencia_de_motor_se_acepta_si_se_declara():
    salida = """
## 1. DELIBERACIÓN DEL COMITÉ INTERDISCIPLINARIO
Análisis preliminar.
## 2. ANÁLISIS DE BRECHA
N/D.
## 3. DECISIÓN FINAL DE INVERSIÓN
DIVERGENCIA FRENTE AL MOTOR CUANTITATIVO: la evidencia adicional justifica cautela.
RECOMENDACIÓN FINAL: INVERTIR
PUNTAJE DE VIABILIDAD: 7/10
## 4. FACTORES CRÍTICOS Y PUNTOS DE MONITOREO
Revisar los supuestos.
"""
    audit = L.auditar_respuesta_comite_ia(
        salida,
        {"decision_modelo": "NEUTRAL / MONITOREAR", "control_calidad_modelo": False},
    )
    assert audit["ok"]
