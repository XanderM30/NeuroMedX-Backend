import numpy as np

from app.ia.iasintomas.catalogo import construir_catalogo
from app.ia.iasintomas.dataset import construir_dataset


def preparar_datos_entrenamiento(
    catalogo: dict | None = None,
) -> dict:

    if catalogo is None:
        catalogo = construir_catalogo()

    dataset = construir_dataset(
        catalogo=catalogo,
        max_sintomas=3,
    )

    entrenamiento = [
        muestra
        for muestra in dataset["muestras"]
        if len(muestra["sintomas_ids"]) <= 2
    ]

    evaluacion = [
        muestra
        for muestra in dataset["muestras"]
        if len(muestra["sintomas_ids"]) == 3
    ]

    return {
        "X_train": np.asarray(
            [m["entrada"] for m in entrenamiento],
            dtype=np.float32,
        ),
        "y_train": np.asarray(
            [m["etiquetas"] for m in entrenamiento],
            dtype=np.float32,
        ),
        "X_test": np.asarray(
            [m["entrada"] for m in evaluacion],
            dtype=np.float32,
        ),
        "y_test": np.asarray(
            [m["etiquetas"] for m in evaluacion],
            dtype=np.float32,
        ),
        "manifestaciones": dataset["manifestaciones"],
        "enfermedades": dataset["enfermedades"],
    }


def preparar_particiones(
    catalogo: dict | None = None,
    proporcion_validacion: float = 0.20,
    semilla: int = 42,
) -> dict:
    from iterstrat.ml_stratifiers import (
        MultilabelStratifiedShuffleSplit,
    )

    datos = preparar_datos_entrenamiento(catalogo)

    X = datos["X_train"]
    y = datos["y_train"]

    separador = MultilabelStratifiedShuffleSplit(
        n_splits=1,
        test_size=proporcion_validacion,
        random_state=semilla,
    )

    indices_train, indices_val = next(
        separador.split(X, y)
    )

    particiones = {
        "X_train": X[indices_train],
        "y_train": y[indices_train],
        "X_val": X[indices_val],
        "y_val": y[indices_val],
        "X_test": datos["X_test"],
        "y_test": datos["y_test"],
        "manifestaciones": datos["manifestaciones"],
        "enfermedades": datos["enfermedades"],
        "semilla": semilla,
    }

    for nombre in ["y_train", "y_val", "y_test"]:
        if np.any(particiones[nombre].sum(axis=0) == 0):
            raise ValueError(
                f"Existen enfermedades sin representacion en {nombre}."
            )

    return particiones


def construir_modelo(
    total_manifestaciones: int,
    total_enfermedades: int,
    semilla: int = 42,
):
    import tensorflow as tf

    tf.keras.utils.set_random_seed(semilla)

    modelo = tf.keras.Sequential(
        [
            tf.keras.layers.Input(
                shape=(total_manifestaciones,),
                name="manifestaciones",
            ),

            tf.keras.layers.Dense(
                64,
                activation="relu",
            ),

            tf.keras.layers.Dropout(0.20),

            tf.keras.layers.Dense(
                64,
                activation="relu",
            ),

            tf.keras.layers.Dropout(0.20),

            tf.keras.layers.Dense(
                total_enfermedades,
                activation="sigmoid",
                name="enfermedades",
            ),
        ],
        name="NeuroMedX_IA_Sintomas",
    )

    modelo.compile(
        optimizer=tf.keras.optimizers.Adam(
            learning_rate=0.001,
        ),
        loss=tf.keras.losses.BinaryCrossentropy(),
        metrics=[
            tf.keras.metrics.Precision(
                name="precision",
                thresholds=0.5,
            ),
            tf.keras.metrics.Recall(
                name="recall",
                thresholds=0.5,
            ),
        ],
    )

    return modelo


def entrenar_modelo(
    particiones: dict,
    epocas: int = 400,
    batch_size: int = 16,
    semilla: int = 42,
) -> dict:
    import tensorflow as tf

    modelo = construir_modelo(
        total_manifestaciones=len(
            particiones["manifestaciones"]
        ),
        total_enfermedades=len(
            particiones["enfermedades"]
        ),
        semilla=semilla,
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            mode="min",
            patience=30,
            restore_best_weights=True,
            verbose=1,
        ),

        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            mode="min",
            factor=0.5,
            patience=10,
            min_lr=0.000001,
            verbose=1,
        ),

        tf.keras.callbacks.TerminateOnNaN(),
    ]

    historial = modelo.fit(
        particiones["X_train"],
        particiones["y_train"],
        validation_data=(
            particiones["X_val"],
            particiones["y_val"],
        ),
        epochs=epocas,
        batch_size=batch_size,
        callbacks=callbacks,
        shuffle=True,
        verbose=2,
    )

    return {
        "modelo": modelo,
        "historial": historial.history,
        "epocas_ejecutadas": len(
            historial.history["loss"]
        ),
    }


def guardar_entrenamiento(
    resultado: dict,
    particiones: dict,
    directorio: str = "modelos/sintomas",
) -> dict:
    import json
    from pathlib import Path

    ruta = Path(directorio)
    ruta.mkdir(parents=True, exist_ok=True)

    ruta_modelo = ruta / "modelo_sintomas.keras"
    ruta_configuracion = ruta / "configuracion.json"
    ruta_historial = ruta / "historial_entrenamiento.json"

    resultado["modelo"].save(ruta_modelo)

    configuracion = {
        "version": 1,
        "arquitectura": "MLP",
        "tipo": "multietiqueta",
        "tipo_dataset": "sintetico_catalogo",
        "manifestaciones": particiones["manifestaciones"],
        "enfermedades": particiones["enfermedades"],
        "total_manifestaciones": len(
            particiones["manifestaciones"]
        ),
        "total_enfermedades": len(
            particiones["enfermedades"]
        ),
        "muestras_entrenamiento": len(
            particiones["X_train"]
        ),
        "muestras_validacion": len(
            particiones["X_val"]
        ),
        "muestras_prueba": len(
            particiones["X_test"]
        ),
        "semilla": particiones["semilla"],
        "epocas_ejecutadas": resultado["epocas_ejecutadas"],
        "umbral_provisional": 0.5,
        "validacion_clinica": False,
    }

    with ruta_configuracion.open("w", encoding="utf-8") as archivo:
        json.dump(
            configuracion,
            archivo,
            ensure_ascii=False,
            indent=4,
        )

    historial = {
        nombre: [float(valor) for valor in valores]
        for nombre, valores in resultado["historial"].items()
    }

    with ruta_historial.open("w", encoding="utf-8") as archivo:
        json.dump(historial, archivo, indent=4)

    return {
        "modelo": str(ruta_modelo),
        "configuracion": str(ruta_configuracion),
        "historial": str(ruta_historial),
    }
