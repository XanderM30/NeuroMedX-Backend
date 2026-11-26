from app.ia.iasintomas.catalogo import construir_catalogo


def calcular_cobertura(
    sintomas_entrada: set[str],
    sintomas_enfermedad: set[str],
) -> float:
    """Calcula qué proporción de síntomas de entrada coincide."""
    if not sintomas_entrada:
        return 0.0

    coincidencias = sintomas_entrada & sintomas_enfermedad

    return len(coincidencias) / len(sintomas_entrada)


def calcular_jaccard(
    sintomas_entrada: set[str],
    sintomas_enfermedad: set[str],
) -> float:
    """Calcula el índice Jaccard entre dos conjuntos."""
    union = sintomas_entrada | sintomas_enfermedad

    if not union:
        return 0.0

    interseccion = sintomas_entrada & sintomas_enfermedad

    return len(interseccion) / len(union)


def evaluar_coincidencia_directa(
    sintomas_ids: list[str],
    catalogo: dict | None = None,
) -> dict:
    """
    Compara los síntomas de entrada con las manifestaciones
    registradas para cada enfermedad.
    """
    if catalogo is None:
        catalogo = construir_catalogo()

    entrada = set(sintomas_ids)

    if not entrada:
        raise ValueError(
            "Se necesita al menos un identificador de síntoma."
        )

    ids_validos = {
        item["id"]
        for item in catalogo["manifestaciones"]
    }

    ids_invalidos = entrada - ids_validos

    if ids_invalidos:
        raise ValueError(
            "Se recibieron identificadores inexistentes: "
            + ", ".join(sorted(ids_invalidos))
        )

    sintomas_por_enfermedad = {}

    for manifestacion in catalogo["manifestaciones"]:
        for enfermedad in manifestacion["enfermedades"]:
            sintomas_por_enfermedad.setdefault(
                enfermedad,
                set(),
            ).add(manifestacion["id"])

    resultados = []

    for enfermedad, sintomas_enfermedad in (
        sintomas_por_enfermedad.items()
    ):
        coincidencias = entrada & sintomas_enfermedad

        if not coincidencias:
            continue

        cobertura = calcular_cobertura(
            entrada,
            sintomas_enfermedad,
        )

        jaccard = calcular_jaccard(
            entrada,
            sintomas_enfermedad,
        )

        resultados.append({
            "enfermedad": enfermedad,
            "coincidencias": sorted(coincidencias),
            "total_coincidencias": len(coincidencias),
            "cobertura": round(cobertura, 4),
            "jaccard": round(jaccard, 4),
        })

    resultados.sort(
        key=lambda item: (
            -item["cobertura"],
            -item["jaccard"],
            item["enfermedad"].casefold(),
        )
    )

    return {
        "metodo": "coincidencia_directa",
        "sintomas_entrada": sorted(entrada),
        "total_sintomas_entrada": len(entrada),
        "total_enfermedades_encontradas": len(resultados),
        "resultados": resultados,
    }


def calcular_metricas_multietiqueta(
    etiquetas_reales: list[int],
    etiquetas_predichas: list[int],
) -> dict:
    """Calcula métricas básicas para una evaluación multietiqueta."""
    if len(etiquetas_reales) != len(etiquetas_predichas):
        raise ValueError(
            "Las etiquetas reales y predichas deben tener "
            "la misma longitud."
        )

    if not etiquetas_reales:
        raise ValueError("Las etiquetas no pueden estar vacías.")

    if any(
        etiqueta not in (0, 1)
        for etiqueta in etiquetas_reales + etiquetas_predichas
    ):
        raise ValueError("Las etiquetas deben ser binarias (0 o 1).")

    verdaderos_positivos = sum(
        real == 1 and predicha == 1
        for real, predicha in zip(
            etiquetas_reales,
            etiquetas_predichas,
        )
    )

    falsos_positivos = sum(
        real == 0 and predicha == 1
        for real, predicha in zip(
            etiquetas_reales,
            etiquetas_predichas,
        )
    )

    falsos_negativos = sum(
        real == 1 and predicha == 0
        for real, predicha in zip(
            etiquetas_reales,
            etiquetas_predichas,
        )
    )

    precision = (
        verdaderos_positivos
        / (verdaderos_positivos + falsos_positivos)
        if verdaderos_positivos + falsos_positivos
        else 0.0
    )

    recall = (
        verdaderos_positivos
        / (verdaderos_positivos + falsos_negativos)
        if verdaderos_positivos + falsos_negativos
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    exactitud_conjunto = int(
        etiquetas_reales == etiquetas_predichas
    )

    return {
        "verdaderos_positivos": verdaderos_positivos,
        "falsos_positivos": falsos_positivos,
        "falsos_negativos": falsos_negativos,
        "precision_micro": round(precision, 4),
        "recall_micro": round(recall, 4),
        "f1_micro": round(f1, 4),
        "exactitud_conjunto": exactitud_conjunto,
    }
from app.ia.iasintomas.dataset import construir_dataset


def evaluar_baseline_dataset(
    catalogo: dict | None = None,
    max_sintomas: int = 3,
) -> dict:
    """
    Evalúa la coincidencia directa sobre un dataset sintético.

    Se consideran predichas todas las enfermedades que coincidan
    con al menos un síntoma de entrada.
    """
    if catalogo is None:
        catalogo = construir_catalogo()

    dataset = construir_dataset(
        catalogo=catalogo,
        max_sintomas=max_sintomas,
    )

    nombres = dataset["enfermedades"]
    indice = {
        nombre: posicion
        for posicion, nombre in enumerate(nombres)
    }

    predicciones_por_enfermedad = {
        nombre: {
            "vp": 0,
            "fp": 0,
            "fn": 0,
            "soporte": 0,
        }
        for nombre in nombres
    }

    total_exactitud = 0
    total_muestras = 0

    vp_global = 0
    fp_global = 0
    fn_global = 0

    resultados_ambiguos = []

    for muestra in dataset["muestras"]:
        if len(muestra["sintomas_ids"]) != 3:
            continue

        reales = muestra["etiquetas"]

        resultado = evaluar_coincidencia_directa(
            muestra["sintomas_ids"],
            catalogo,
        )

        enfermedades_predichas = {
            item["enfermedad"]
            for item in resultado["resultados"]
        }

        predichas = [
            int(nombre in enfermedades_predichas)
            for nombre in nombres
        ]

        metricas = calcular_metricas_multietiqueta(
            reales,
            predichas,
        )

        total_muestras += 1
        total_exactitud += metricas["exactitud_conjunto"]

        vp_global += metricas["verdaderos_positivos"]
        fp_global += metricas["falsos_positivos"]
        fn_global += metricas["falsos_negativos"]

        for posicion, nombre in enumerate(nombres):
            real = reales[posicion]
            predicha = predichas[posicion]

            registro = predicciones_por_enfermedad[nombre]

            if real:
                registro["soporte"] += 1

            if real and predicha:
                registro["vp"] += 1
            elif not real and predicha:
                registro["fp"] += 1
            elif real and not predicha:
                registro["fn"] += 1

        if len(muestra["enfermedades_coincidentes"]) > 1:
            resultados_ambiguos.append({
                "sintomas_ids": muestra["sintomas_ids"],
                "esperadas": muestra["enfermedades_coincidentes"],
                "predichas": sorted(enfermedades_predichas),
                "exactitud_conjunto": metricas[
                    "exactitud_conjunto"
                ],
            })

    precision_micro = (
        vp_global / (vp_global + fp_global)
        if vp_global + fp_global else 0.0
    )

    recall_micro = (
        vp_global / (vp_global + fn_global)
        if vp_global + fn_global else 0.0
    )

    f1_micro = (
        2 * precision_micro * recall_micro
        / (precision_micro + recall_micro)
        if precision_micro + recall_micro else 0.0
    )

    resultados_enfermedades = []

    for nombre, registro in predicciones_por_enfermedad.items():
        vp = registro["vp"]
        fp = registro["fp"]
        fn = registro["fn"]

        precision = vp / (vp + fp) if vp + fp else 0.0
        recall = vp / (vp + fn) if vp + fn else 0.0

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )

        resultados_enfermedades.append({
            "enfermedad": nombre,
            "soporte": registro["soporte"],
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        })

    resultados_enfermedades.sort(
        key=lambda item: item["enfermedad"].casefold()
    )

    macro_precision = sum(
        item["precision"]
        for item in resultados_enfermedades
    ) / len(resultados_enfermedades)

    macro_recall = sum(
        item["recall"]
        for item in resultados_enfermedades
    ) / len(resultados_enfermedades)

    macro_f1 = sum(
        item["f1"]
        for item in resultados_enfermedades
    ) / len(resultados_enfermedades)

    return {
        "metodo": "coincidencia_directa",
        "criterio": "al_menos_un_sintoma",
        "tipo_dataset": dataset["tipo"],
        "total_muestras_evaluadas": total_muestras,
        "exactitud_conjunto": round(
            total_exactitud / total_muestras, 4
        ) if total_muestras else 0.0,
        "precision_micro": round(precision_micro, 4),
        "recall_micro": round(recall_micro, 4),
        "f1_micro": round(f1_micro, 4),
        "precision_macro": round(macro_precision, 4),
        "recall_macro": round(macro_recall, 4),
        "f1_macro": round(macro_f1, 4),
        "total_combinaciones_ambiguas": len(resultados_ambiguos),
        "combinaciones_ambiguas": resultados_ambiguos,
        "resultados_por_enfermedad": resultados_enfermedades,
    }
def comparar_criterios_baseline(
    catalogo: dict | None = None,
) -> dict:
    """
    Compara tres criterios de coincidencia directa:
    1. Al menos un síntoma.
    2. Al menos dos síntomas.
    3. Todos los síntomas de entrada.
    """
    if catalogo is None:
        catalogo = construir_catalogo()

    dataset = construir_dataset(
        catalogo=catalogo,
        max_sintomas=3,
    )

    nombres = dataset["enfermedades"]

    criterios = {
        "permisivo": 1,
        "intermedio": 2,
        "estricto": 3,
    }

    resultados = {}

    for nombre_criterio, minimo in criterios.items():
        vp_global = 0
        fp_global = 0
        fn_global = 0
        exactitud = 0
        total = 0

        for muestra in dataset["muestras"]:
            sintomas = muestra["sintomas_ids"]

            if len(sintomas) != 3:
                continue

            reales = muestra["etiquetas"]

            coincidencias_por_enfermedad = {}

            for manifestacion in catalogo["manifestaciones"]:
                if manifestacion["id"] not in sintomas:
                    continue

                for enfermedad in manifestacion["enfermedades"]:
                    coincidencias_por_enfermedad[
                        enfermedad
                    ] = coincidencias_por_enfermedad.get(
                        enfermedad, 0
                    ) + 1

            predichas = [
                int(
                    coincidencias_por_enfermedad.get(
                        enfermedad, 0
                    ) >= minimo
                )
                for enfermedad in nombres
            ]

            metricas = calcular_metricas_multietiqueta(
                reales,
                predichas,
            )

            vp_global += metricas["verdaderos_positivos"]
            fp_global += metricas["falsos_positivos"]
            fn_global += metricas["falsos_negativos"]

            exactitud += metricas["exactitud_conjunto"]
            total += 1

        precision = (
            vp_global / (vp_global + fp_global)
            if vp_global + fp_global else 0.0
        )

        recall = (
            vp_global / (vp_global + fn_global)
            if vp_global + fn_global else 0.0
        )

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )

        resultados[nombre_criterio] = {
            "minimo_sintomas": minimo,
            "muestras": total,
            "exactitud_conjunto": round(
                exactitud / total, 4
            ) if total else 0.0,
            "precision_micro": round(precision, 4),
            "recall_micro": round(recall, 4),
            "f1_micro": round(f1, 4),
        }

    return {
        "metodo": "comparacion_baseline",
        "resultados": resultados,
    }
def analizar_errores_baseline(
    catalogo: dict | None = None,
) -> dict:
    """
    Analiza falsos positivos y falsos negativos
    usando el criterio de al menos 2 de 3 síntomas.
    """
    if catalogo is None:
        catalogo = construir_catalogo()

    dataset = construir_dataset(
        catalogo=catalogo,
        max_sintomas=3,
    )

    nombres = dataset["enfermedades"]

    errores = {
        enfermedad: {
            "verdaderos_positivos": 0,
            "falsos_positivos": 0,
            "falsos_negativos": 0,
            "soporte_real": 0,
        }
        for enfermedad in nombres
    }

    muestras_evaluadas = 0

    for muestra in dataset["muestras"]:
        sintomas = muestra["sintomas_ids"]

        if len(sintomas) != 3:
            continue

        reales = muestra["etiquetas"]

        coincidencias = {}

        for manifestacion in catalogo["manifestaciones"]:
            if manifestacion["id"] not in sintomas:
                continue

            for enfermedad in manifestacion["enfermedades"]:
                coincidencias[enfermedad] = (
                    coincidencias.get(enfermedad, 0) + 1
                )

        predichas = [
            int(coincidencias.get(enfermedad, 0) >= 2)
            for enfermedad in nombres
        ]

        for indice, enfermedad in enumerate(nombres):
            real = int(reales[indice])
            predicha = predichas[indice]

            if real:
                errores[enfermedad]["soporte_real"] += 1

            if real and predicha:
                errores[enfermedad]["verdaderos_positivos"] += 1
            elif not real and predicha:
                errores[enfermedad]["falsos_positivos"] += 1
            elif real and not predicha:
                errores[enfermedad]["falsos_negativos"] += 1

        muestras_evaluadas += 1

    resumen = []

    for enfermedad, datos in errores.items():
        tp = datos["verdaderos_positivos"]
        fp = datos["falsos_positivos"]
        fn = datos["falsos_negativos"]

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )

        resumen.append({
            "enfermedad": enfermedad,
            **datos,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        })

    resumen.sort(
        key=lambda x: (
            x["falsos_positivos"] + x["falsos_negativos"],
            x["falsos_positivos"],
        ),
        reverse=True,
    )

    return {
        "metodo": "analisis_errores_baseline",
        "criterio": "al_menos_2_de_3",
        "muestras_evaluadas": muestras_evaluadas,
        "total_falsos_positivos": sum(
            x["falsos_positivos"] for x in resumen
        ),
        "total_falsos_negativos": sum(
            x["falsos_negativos"] for x in resumen
        ),
        "enfermedades": resumen,
    }
def extraer_confusiones_baseline(
    catalogo: dict | None = None,
    limite: int = 30,
) -> dict:
    """
    Extrae y agrupa los falsos positivos del criterio
    de al menos 2 de 3 síntomas.
    """
    if catalogo is None:
        catalogo = construir_catalogo()

    if limite < 1:
        raise ValueError("El límite debe ser mayor que cero.")

    dataset = construir_dataset(
        catalogo=catalogo,
        max_sintomas=3,
    )

    nombres = dataset["enfermedades"]

    # Relacionar cada enfermedad con sus síntomas.
    sintomas_por_enfermedad = {
        enfermedad: set()
        for enfermedad in nombres
    }

    frases_por_id = {}

    for manifestacion in catalogo["manifestaciones"]:
        sid = manifestacion["id"]
        frases_por_id[sid] = (
           manifestacion["frases_originales"][0]
           if manifestacion["frases_originales"]
           else manifestacion["canonico"]
        )

        for enfermedad in manifestacion["enfermedades"]:
            if enfermedad in sintomas_por_enfermedad:
                sintomas_por_enfermedad[enfermedad].add(sid)

    confusiones = {}
    ejemplos = []

    for muestra in dataset["muestras"]:
        sintomas = set(muestra["sintomas_ids"])

        if len(sintomas) != 3:
            continue

        reales = {
            nombres[i]
            for i, valor in enumerate(muestra["etiquetas"])
            if valor == 1
        }

        predichas = {
            enfermedad
            for enfermedad in nombres
            if len(
                sintomas & sintomas_por_enfermedad[enfermedad]
            ) >= 2
        }

        falsos_positivos = predichas - reales

        if not falsos_positivos:
            continue

        nombres_sintomas = [
            frases_por_id.get(sid, sid)
            for sid in sorted(sintomas)
        ]

        for original in sorted(reales):
            for sugerida in sorted(falsos_positivos):
                clave = (original, sugerida)

                if clave not in confusiones:
                    confusiones[clave] = {
                        "enfermedad_original": original,
                        "enfermedad_sugerida": sugerida,
                        "frecuencia": 0,
                        "ejemplos": [],
                    }

                confusiones[clave]["frecuencia"] += 1

                if len(confusiones[clave]["ejemplos"]) < 3:
                    confusiones[clave]["ejemplos"].append(
                        nombres_sintomas
                    )

        if len(ejemplos) < limite:
            ejemplos.append({
                "sintomas": nombres_sintomas,
                "enfermedades_originales": sorted(reales),
                "falsos_positivos": sorted(falsos_positivos),
            })

    ranking = sorted(
        confusiones.values(),
        key=lambda x: x["frecuencia"],
        reverse=True,
    )

    return {
        "metodo": "extraccion_confusiones_baseline",
        "criterio": "al_menos_2_de_3",
        "total_pares_confusion": len(ranking),
        "total_combinaciones_con_falsos_positivos": sum(
            1
            for muestra in dataset["muestras"]
            if len(muestra["sintomas_ids"]) == 3
            and any(
                len(
                    set(muestra["sintomas_ids"])
                    & sintomas_por_enfermedad[enfermedad]
                ) >= 2
                for enfermedad in nombres
                if enfermedad not in {
                    nombres[i]
                    for i, valor in enumerate(muestra["etiquetas"])
                    if valor == 1
                }
            )
        ),
        "ranking_confusiones": ranking,
        "ejemplos": ejemplos,
    }
def analizar_especificidad_sintomas(
    catalogo: dict | None = None,
) -> dict:
    """
    Analiza la especificidad de los síntomas según
    cuántas enfermedades los comparten.

    Menos enfermedades asociadas = mayor especificidad
    dentro del catálogo.
    """
    if catalogo is None:
        catalogo = construir_catalogo()

    enfermedades = set()
    sintomas = []

    for manifestacion in catalogo["manifestaciones"]:
        enfermedades.update(manifestacion["enfermedades"])

        total = len(set(manifestacion["enfermedades"]))

        sintomas.append({
            "id": manifestacion["id"],
            "sintoma": (
                manifestacion["frases_originales"][0]
                if manifestacion["frases_originales"]
                else manifestacion["canonico"]
            ),
            "enfermedades_asociadas": sorted(
                set(manifestacion["enfermedades"])
            ),
            "total_enfermedades": total,
            "especificidad": round(
                1 / total, 4
            ) if total else 0.0,
        })

    sintomas.sort(
        key=lambda x: (
            x["total_enfermedades"],
            x["sintoma"],
        )
    )

    distribucion = {}

    for sintoma in sintomas:
        cantidad = sintoma["total_enfermedades"]
        distribucion[cantidad] = (
            distribucion.get(cantidad, 0) + 1
        )

    resumen_enfermedades = []

    for enfermedad in sorted(enfermedades):
        asociados = [
            sintoma
            for sintoma in sintomas
            if enfermedad in sintoma["enfermedades_asociadas"]
        ]

        exclusivos = [
            sintoma
            for sintoma in asociados
            if sintoma["total_enfermedades"] == 1
        ]

        resumen_enfermedades.append({
            "enfermedad": enfermedad,
            "total_sintomas": len(asociados),
            "sintomas_exclusivos": len(exclusivos),
            "sintomas_compartidos": (
                len(asociados) - len(exclusivos)
            ),
            "manifestaciones": [
                sintoma["sintoma"]
                for sintoma in asociados
            ],
        })

    resumen_enfermedades.sort(
        key=lambda x: (
            x["sintomas_exclusivos"],
            x["total_sintomas"],
        ),
        reverse=True,
    )

    return {
        "metodo": "analisis_especificidad_sintomas",
        "total_enfermedades": len(enfermedades),
        "total_sintomas": len(sintomas),
        "sintomas_exclusivos": sum(
            1 for s in sintomas
            if s["total_enfermedades"] == 1
        ),
        "sintomas_compartidos": sum(
            1 for s in sintomas
            if s["total_enfermedades"] > 1
        ),
        "distribucion_por_numero_enfermedades": dict(
            sorted(distribucion.items())
        ),
        "sintomas_mas_especificos": sintomas[:20],
        "sintomas_menos_especificos": sintomas[-20:][::-1],
        "resumen_por_enfermedad": resumen_enfermedades,
    }