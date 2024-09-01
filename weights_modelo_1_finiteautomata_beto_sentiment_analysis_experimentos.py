# -*- coding: utf-8 -*-
"""Weights - Modelo 1 - finiteautomata/beto-sentiment-analysis - Experimentos

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1yDl8e2aaAdOZuY0YUOehX9AFs1U8JVR-

# Preparación del entorno: instalaciones y librerías
"""

#Instalaciones
!pip install -q datasets

#Librerías
import os
import numpy as np
import pandas as pd
import glob
import shutil
import torch
import torch.nn.functional as F
from torch import nn
from google.colab import drive
from datasets import load_dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments, DataCollatorWithPadding, EarlyStoppingCallback
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, f1_score
from torch.optim import Adam
from sklearn.model_selection import ParameterGrid
from datasets import concatenate_datasets

"""# Dataset"""

#Carga del dataset de España
dataset_es = load_dataset("alttal/SA_opiniones_indumentaria_ES_Espanya_splits")

#Se eliminan columnas innecesarias
dataset_es = dataset_es.remove_columns(["id","__index_level_0__"])
dataset_es

"""# Métricas de evaluación"""

#Definimos las métricas para evaluar el modelo
#Este conjunto de métricas depende de la tarea.
#Para clasificación de textos se suelen utilizar accuracy, precision, recall y F1-score.

def compute_metrics(pred):
  y_true = pred.label_ids              # son las etiquetas reales
  y_pred = pred.predictions.argmax(-1) # son las predicciones
  acc = accuracy_score(y_true, y_pred)
  precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='weighted')

  #métricas por clase
  precision_per_class, recall_per_class, f1_per_class, _ = precision_recall_fscore_support(y_true, y_pred, average=None)

  #conversiones necesarias para evitar errores de registro en Tensorboard
  precision_per_class = list(precision_per_class)
  recall_per_class = list(recall_per_class)
  f1_per_class = list(f1_per_class)

  return {
      'accuracy': acc,
      'f1': f1,
      'precision': precision,
      'recall': recall,
      'precision_per_class': precision_per_class,
      'recall_per_class': recall_per_class,
      'f1_per_class': f1_per_class
  }

"""# Documentación del progreso"""

#Montar unidad de disco
drive.mount('/content/drive')

#Ruta raíz para guardar cada experimento
path = '/content/drive/My Drive/TFM/TFM-Experimentos'

#Cambiar directorio actual de trabajo
os.chdir(path)

#Verificar directorio actual
print("Directorio actual:", os.getcwd())

#Definición de una función para eliminar logs antiguos (para evitar falta de almacenamiento)
def clean_old_logs(logging_dir, keep_last_n=1):
    log_files = sorted(glob.glob(os.path.join(logging_dir, '*')), key=os.path.getmtime)
    for log_file in log_files[:-keep_last_n]:
        os.remove(log_file)

#Ruta al directorio de logs
log_dir = path

#Eliminar archivos antiguos de TensorBoard (para evitar acumulación de demasiados logs)
for file in os.listdir(log_dir):
    if file.startswith('events.out.tfevents'):
        os.remove(os.path.join(log_dir, file))

"""# Modelo 1

##Carga del modelo 1 y adaptación de los datos
"""

#Carga del modelo pre-entrenado
model1 = AutoModelForSequenceClassification.from_pretrained("finiteautomata/beto-sentiment-analysis", num_labels=3)

#A modo de información, vemos la configuración del modelo
model1.config

#¿Cómo son las etiquetas del modelo? Importante porque deben ser iguales a las del dataset
model1.config.id2label

#Las etiquetas de los datasets son strings. Se las cambia a valores numéricos
def label_to_int(label):
    if label == "POS":
        return 2
    elif label == "NEG":
        return 0
    else:
        return 1

dataset_es_1 = dataset_es.map(lambda x: {"label": label_to_int(x["label"])})

"""##Tokenización del dataset"""

#Carga del tokenizador específico
tokenizer1 = AutoTokenizer.from_pretrained("finiteautomata/beto-sentiment-analysis")

"""Primer test, sin especificar límites para la tokenización"""

#Se define tokenizador del primer modelo
def tokenize_function1(example):
    return tokenizer1(example["text"], padding=True, truncation=True)

#Tokenización del dataset
encoded_dataset_es_1 = dataset_es_1.map(tokenize_function1, batched=True)

#¿Cuál es la longitud de tokens para cada entrada?
token_lengths_train = [len(tokens) for tokens in encoded_dataset_es_1['train']['input_ids']]
token_lengths_eval = [len(tokens) for tokens in encoded_dataset_es_1['validation']['input_ids']]
token_lengths_test = [len(tokens) for tokens in encoded_dataset_es_1['test']['input_ids']]

#Calculamos la media para cada subconjunto de datos
media_tokens_train = sum(token_lengths_train) / len(token_lengths_train)
media_tokens_eval = sum(token_lengths_eval) / len(token_lengths_eval)
media_tokens_test = sum(token_lengths_test) / len(token_lengths_test)

print(f"La media de cantidad de tokens por entrada en el conjunto de datos tokenizado, subsplit train es: {media_tokens_train:.2f}")
print(f"La media de cantidad de tokens por entrada en el conjunto de datos tokenizado, subsplit validation es: {media_tokens_eval:.2f}")
print(f"La media de cantidad de tokens por entrada en el conjunto de datos tokenizado, subsplit test es: {media_tokens_test:.2f}")

#¿Cuál es la longitud máxima en cuanto a tokens de cada subconjunto de datos?
max_tokens_train = max(token_lengths_train)
max_tokens_eval = max(token_lengths_eval)
max_tokens_test = max(token_lengths_test)

#¿Cuál es la longitud máxima considerando todos los splits?
max_tokens_all = max(max_tokens_train, max_tokens_eval, max_tokens_test)
print(f"La longitud máxima, en cuanto a tokens, es: {max_tokens_all:.2f}")

"""Con esta información, se puede crear un tokenizador que se adapte mejor a los datos"""

#Se define tokenizador del primer modelo
def tokenize_function1(example):
    return tokenizer1(example["text"], max_length=314, padding='max_length', truncation=True)

#Tokenización del dataset
encoded_dataset_es_1 = dataset_es_1.map(tokenize_function1, batched=True)
#Luego de tokenizar se puede eliminar la columna "text" porque el modelo no la necesita
encoded_dataset_es_1 = encoded_dataset_es_1.remove_columns(["text"])
encoded_dataset_es_1

#Ejemplo de la tokenización en cada split
print(encoded_dataset_es_1['train'][0])
print(encoded_dataset_es_1['validation'][0])
print(encoded_dataset_es_1['test'][0])

#¿Cuál es la longitud máxima considerando todos los splits?
max_tokens_all = max(max_tokens_train, max_tokens_eval, max_tokens_test)
print(f"La longitud máxima, en cuanto a tokens, es: {max_tokens_all:.2f}")

"""## Modificación de pesos

Al tener un dataset desbalanceado en el cual la mayoría de las instancias pertenecen a la clase POS, y con una minoría de instancias etiquetadas como NEU, se ha observado en otros experimentos que el modelo tiene grandes dificultades a la hora de predecir la clase neutral porque, al recibir tan pocos ejemplos, no parece poder aprenderla.

Una alternativa en estos casos es modificar los pesos y penalizar al modelo para que aprenda mejor a identificar la clase minoritaria.
"""

class_weights_dict = {}

#Iteración sobre cada split (train, test, validation)
for split in ['train', 'test', 'validation']:
    #Acceder a split
    dataset = encoded_dataset_es_1[split]

    #Convertir la columna 'label' a una serie de pandas
    labels_series = pd.Series(dataset['label'])

    #Calcular los pesos de clase
    class_weights = (1 - (labels_series.value_counts().sort_index() / len(labels_series))).values

    #Guardar los pesos en un diccionario
    class_weights_dict[split] = class_weights

print(class_weights_dict)

#El trainer se basa en pytorch, por eso se modifica de array numpy a tensores pytorch
class_weights = torch.from_numpy(class_weights).float().to("cuda")
class_weights

#Siguiendo la documentación, el trainer puede calcular la pérdida si se le provee un argumento 'labels'
#Fuente: https://huggingface.co/docs/transformers/main_classes/trainer & https://www.youtube.com/watch?v=u--UVvH-LIQ
#El que tenemos se llama 'label', por eso se lo modifica
encoded_dataset_es_1 = encoded_dataset_es_1.rename_column("label", "labels")

#Creamos una clase que es subclase de la clase Trainer
#Desde ahí definimos cómo calcular la pérdida (loss function)
class WeightedLossTrainer(Trainer):
  def compute_metrics(self, model, inputs, return_outputs=False):
    #Introducir inputs al modelo
    outputs = model(**inputs)
    logits = outputs.get("logits")
    #Extraer labels
    labels = inputs.get("labels")
    #Definir función de pérdida con los nuevos pesos
    loss = loss_func = nn.CrossEntropyLoss(weight=class_weights)
    #Calcular pérdida
    loss = loss_func(logits, labels)
    return (loss, outputs) if return_outputs else loss

"""## Experimento 1.1"""

#Documentación
#Definición de directorios para el primer experimento
output_dir = "./outputs/weights_model1_lit"
shutil.make_archive("./outputs/weights_model1_lit", 'zip', output_dir)
logging_dir = "./logs/weights_model1_lit"
shutil.make_archive("./logs/weights_model1_lit", 'zip', output_dir)

#Si directorios no existen, crearlos
os.makedirs(output_dir, exist_ok=True)
os.makedirs(logging_dir, exist_ok=True)

"""Entrenamiento con hiperparámetros recomendados"""

#Definición de EarlyStopping
early_stopping = EarlyStoppingCallback(
    early_stopping_patience=3,    # Número de épocas para esperar sin mejora
    early_stopping_threshold=0.0  # Umbral para la mejora mínima
)

#Definición de hiperparámetros
training_args_weights_model1_lit = TrainingArguments(
    output_dir=output_dir,           # Directorio de salida
    logging_dir=logging_dir,         # Directorio para los logs
    eval_strategy="steps",           # Estrategia de evaluación
    save_strategy="steps",           # Estrategia de guardado (debe coincidir con la de evaluación)
    save_steps=1000,                 # Número de pasos entre cada guardado
    logging_strategy="steps",        # Estrategia de registro
    logging_steps=1000,              # Número de pasos entre cada registro
    num_train_epochs=3,              # Número de épocas de entrenamiento
    per_device_train_batch_size=16,  # Tamaño del batch de entrenamiento (podría ser también 32)
    per_device_eval_batch_size=16,   # Tamaño del batch de evaluación (podría ser también 32)
    learning_rate=3e-5,              # Tasa de aprendizaje
    weight_decay=0.01,               # Decadencia de peso (podría ser también 0.1)
    warmup_ratio=0.1,                # Proporción de épocas de calentamiento
    save_total_limit=1,              # Número máximo de checkpoints a guardar (para evitar problemas de almacenamiento)
    seed=42,                         # Semilla para garantizar reproducibilidad
    fp16=True,                       # Uso de fp16 para acelerar el entrenamiento
    load_best_model_at_end=True,     # Cargar el mejor modelo al final del entrenamiento
    metric_for_best_model="f1",      # Métrica objetivo, a optimizar para encontrar el mejor modelo
)

#Definición de optimizador
optimizer = Adam(model1.parameters(), lr=3e-5, weight_decay=0.01)

#Definición de un objeto de la clase Trainer para el primer experimento con el modelo 1
trainer_weights_model1_lit = WeightedLossTrainer(
    model = model1,
    args = training_args_weights_model1_lit,
    train_dataset = encoded_dataset_es_1['train'],
    eval_dataset = encoded_dataset_es_1['validation'],
    compute_metrics=compute_metrics,
    tokenizer = tokenizer1,
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer1),
    optimizers = (optimizer, None),
    callbacks = [early_stopping])

"""Entrenamiento"""

trainer_weights_model1_lit.train()

"""Validación"""

trainer_weights_model1_lit.evaluate()

"""Reporte de clasificación (sobre conjunto de validación)"""

#Obtención de predicciones del conjunto de validación
predictions = trainer_weights_model1_lit.predict(encoded_dataset_es_1['validation'])
y_true = predictions.label_ids
y_pred = predictions.predictions.argmax(-1)

print("Predicciones:")

#Generación del reporte (diccionario)
reporte_dict = classification_report(y_true, y_pred, output_dict=True)

#Reporte completo (texto)
print("Reporte de Clasificación:")
print(classification_report(y_true, y_pred))

#Preparación de datos para el DataFrame
metrics_per_class = []
for label, metrics in reporte_dict.items():
    if label.isdigit():
        metrics_class = {
            "Clase": label,
            "Precisión": f"{metrics['precision']:.2f}",
            "Recall": f"{metrics['recall']:.2f}",
            "F1-score": f"{metrics['f1-score']:.2f}"
        }
        metrics_per_class.append(metrics_class)

#Creación de DataFrame con métricas por clase
df_metrics_per_class = pd.DataFrame(metrics_per_class)

#Tabla de métricas por clase
print("\nMétricas por Clase:")
print(df_metrics_per_class.to_string(index=False))

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""Test

Reporte de clasificación (sobre conjunto de test)
"""

#Obtención de predicciones del conjunto de test
predictions = trainer_weights_model1_lit.predict(encoded_dataset_es_1['test'])
y_true = predictions.label_ids
y_pred = predictions.predictions.argmax(-1)

print("Predicciones:")

#Generación del reporte (diccionario)
reporte_dict = classification_report(y_true, y_pred, output_dict=True)

#Reporte completo (texto)
print("Reporte de Clasificación:")
print(classification_report(y_true, y_pred))

#Preparación de datos para el DataFrame
metrics_per_class = []
for label, metrics in reporte_dict.items():
    if label.isdigit():
        metrics_class = {
            "Clase": label,
            "Precisión": f"{metrics['precision']:.2f}",
            "Recall": f"{metrics['recall']:.2f}",
            "F1-score": f"{metrics['f1-score']:.2f}"
        }
        metrics_per_class.append(metrics_class)

#Creación de DataFrame con métricas por clase
df_metrics_per_class = pd.DataFrame(metrics_per_class)

#Tabla de métricas por clase
print("\nMétricas por Clase:")
print(df_metrics_per_class.to_string(index=False))

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""## Grid Search

Búsqueda de hiperparámetros optimizados con la técnica Grid Search:
"""

#Definición del espacio de búsqueda
param_grid = {
    'num_train_epochs': [3, 10],
    'per_device_train_batch_size': [16, 32],
    'per_device_eval_batch_size': [16, 32],
    'learning_rate': [1e-5, 2e-5, 3e-5, 5e-5, 1e-4],
    'weight_decay': [0.01, 0.1],
    'warmup_ratio': [0.06, 0.1],
}

grid = ParameterGrid(param_grid)

#Función para calcular el f1-score
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = logits.argmax(axis=-1)
    return {
        'f1': f1_score(labels, predictions, average='weighted')
    }

#Inicialización de variables para guardar los mejores resultados
best_score = 0
best_params = None

#Documentación
#Definición de directorios para el primer experimento
output_dir = "./outputs/weights_model1_search"
shutil.make_archive("./outputs/weights_model1_search", 'zip', output_dir)
logging_dir = "./logs/weights_model1_search"
shutil.make_archive("./logs/weights_model1_search", 'zip', output_dir)

#Si directorios no existen, crearlos
os.makedirs(output_dir, exist_ok=True)
os.makedirs(logging_dir, exist_ok=True)

#Bucle para probar los diferentes parámetros
for params in grid:
    print(f"Entrenando con parámetros: {params}")

    #Definición de hiperparámetros
    training_args_weights_model1_search = TrainingArguments(
        output_dir=output_dir,                                                  # Directorio de salida
        logging_dir=logging_dir,                                                # Directorio para los logs
        eval_strategy="steps",                                                  # Estrategia de evaluación
        save_strategy="steps",                                                  # Estrategia de guardado (debe coincidir con la de evaluación)
        save_steps=1000,                                                        # Número de pasos entre cada guardado
        logging_strategy="steps",                                               # Estrategia de registro
        logging_steps=1000,                                                     # Número de pasos entre cada registro
        num_train_epochs=params['num_train_epochs'],                            # Número de épocas de entrenamiento
        per_device_train_batch_size=params['per_device_train_batch_size'],      # Tamaño del batch de entrenamiento
        per_device_eval_batch_size=params['per_device_eval_batch_size'],        # Tamaño del batch de evaluación
        learning_rate=params['learning_rate'],                                  # Tasa de aprendizaje
        weight_decay=params['weight_decay'],                                    # Decadencia de peso
        warmup_ratio=params['warmup_ratio'],                                    # Proporción de épocas de calentamiento
        save_total_limit=1,                                                     # Número máximo de checkpoints a guardar (para evitar problemas de almacenamiento)
        seed=42,                                                                # Semilla para garantizar reproducibilidad
        fp16=True,                                                              # Uso de fp16 para acelerar el entrenamiento
        load_best_model_at_end=True,                                            # Cargar el mejor modelo al final del entrenamiento
        metric_for_best_model='f1',                                             # Métrica objetivo, a optimizar para encontrar el mejor modelo
    )

    #Definición de un objeto de la clase Trainer para la búsqueda con el modelo 1
    trainer_weights_model1_search = WeightedLossTrainer(
        model=model1,
        args=training_args_weights_model1_search,
        train_dataset=encoded_dataset_es_1['train'],
        eval_dataset=encoded_dataset_es_1['validation'],
        tokenizer=tokenizer1,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer1),
        compute_metrics=compute_metrics,
        optimizers = (optimizer, None),
        callbacks = [early_stopping]
    )

    #Entrenamiento
    trainer_weights_model1_search.train()

    #Limpiar logs antiguos después del entrenamiento en cada iteración
    clean_old_logs(logging_dir, keep_last_n=1)

    #Validación
    eval_result = trainer_weights_model1_search.evaluate()

    #Guardamos métrica objetivo
    score = eval_result.get('eval_f1', 0)

    #Siempre que la métrica objetivo sea mejor que el score guardado hasta el momento, se lo actualiza
    if score > best_score:
        best_score = score
        best_params = params

#Vemos los resultados del Grid Search
print(f"Mejores hiperparámetros: {best_params}")
print(f"Mejor puntuación F1: {best_score}")

"""## Experimento 1.2."""

#Documentación
#Definición de directorios para el segundo experimento
output_dir = "./outputs/weights_model1_opt"
shutil.make_archive("./outputs/weights_model1_opt", 'zip', output_dir)
logging_dir = "./logs/weights_model1_opt"
shutil.make_archive("./logs/weights_model1_opt", 'zip', output_dir)

#Si directorios no existen, crearlos
os.makedirs(output_dir, exist_ok=True)
os.makedirs(logging_dir, exist_ok=True)

"""Entrenamiento con hiperparámetros optimizados"""

#Definición de EarlyStopping
early_stopping = EarlyStoppingCallback(
    early_stopping_patience=3,    # Número de épocas para esperar sin mejora
    early_stopping_threshold=0.0  # Umbral para la mejora mínima
)

#Definición de hiperparámetros (basados en Grid Search)
training_args_weights_model1_opt = TrainingArguments(
    output_dir=output_dir,                                # Directorio de salida
    logging_dir=logging_dir,                              # Directorio para los logs
    eval_strategy="steps",                                # Estrategia de evaluación
    save_strategy="steps",                                # Estrategia de guardado (debe coincidir con la de evaluación)
    save_steps=1000,                                      # Número de pasos entre cada guardado
    logging_strategy="steps",                             # Estrategia de registro
    logging_steps=1000,                                   # Número de pasos entre cada registro
    num_train_epochs=3,                                   # Número de épocas de entrenamiento
    per_device_train_batch_size=16,                       # Tamaño del batch de entrenamiento
    per_device_eval_batch_size=16,                        # Tamaño del batch de evaluación
    learning_rate=1e-05,                                  # Tasa de aprendizaje
    weight_decay=0.01,                                    # Decadencia de peso
    warmup_ratio=0.06,                                    # Proporción de épocas de calentamiento
    save_total_limit=1,                                   # Número máximo de checkpoints a guardar (para evitar problemas de almacenamiento)
    seed=42,                                              # Semilla para garantizar reproducibilidad
    fp16=True,                                            # Uso de fp16 para acelerar el entrenamiento
    load_best_model_at_end=True,                          # Cargar el mejor modelo al final del entrenamiento
    metric_for_best_model="f1",                           # Métrica objetivo, a optimizar para encontrar el mejor modelo
)

#Definición de optimizador
optimizer = Adam(model1.parameters(), lr=params['learning_rate'], weight_decay=params['weight_decay'])

#Definición de un objeto de la clase Trainer para el segundo experimento con el modelo 1
trainer_weights_model1_opt = WeightedLossTrainer(
    model = model1,
    args = training_args_weights_model1_opt,
    train_dataset = encoded_dataset_es_1['train'],
    eval_dataset = encoded_dataset_es_1['validation'],
    compute_metrics=compute_metrics,
    tokenizer = tokenizer1,
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer1),
    optimizers = (optimizer, None),
    callbacks = [early_stopping])

"""Entrenamiento"""

trainer_weights_model1_opt.train()

"""Validación"""

trainer_weights_model1_opt.evaluate()

"""Reporte de clasificación (sobre conjunto de validación)"""

#Obtención de predicciones del conjunto de validación
predictions = trainer_weights_model1_opt.predict(encoded_dataset_es_1['validation'])
y_true = predictions.label_ids
y_pred = predictions.predictions.argmax(-1)

print("Predicciones:")

#Generación del reporte (diccionario)
reporte_dict = classification_report(y_true, y_pred, output_dict=True)

#Reporte completo (texto)
print("Reporte de Clasificación:")
print(classification_report(y_true, y_pred))

#Preparación de datos para el DataFrame
metrics_per_class = []
for label, metrics in reporte_dict.items():
    if label.isdigit():
        metrics_class = {
            "Clase": label,
            "Precisión": f"{metrics['precision']:.2f}",
            "Recall": f"{metrics['recall']:.2f}",
            "F1-score": f"{metrics['f1-score']:.2f}"
        }
        metrics_per_class.append(metrics_class)

#Creación de DataFrame con métricas por clase
df_metrics_per_class = pd.DataFrame(metrics_per_class)

#Tabla de métricas por clase
print("\nMétricas por Clase:")
print(df_metrics_per_class.to_string(index=False))

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""Test

Reporte de clasificación (sobre conjunto de test)
"""

#Obtención de predicciones del conjunto de test
predictions = trainer_weights_model1_opt.predict(encoded_dataset_es_1['test'])
y_true = predictions.label_ids
y_pred = predictions.predictions.argmax(-1)

print("Predicciones:")

#Generación del reporte (diccionario)
reporte_dict = classification_report(y_true, y_pred, output_dict=True)

#Reporte completo (texto)
print("Reporte de Clasificación:")
print(classification_report(y_true, y_pred))

#Preparación de datos para el DataFrame
metrics_per_class = []
for label, metrics in reporte_dict.items():
    if label.isdigit():
        metrics_class = {
            "Clase": label,
            "Precisión": f"{metrics['precision']:.2f}",
            "Recall": f"{metrics['recall']:.2f}",
            "F1-score": f"{metrics['f1-score']:.2f}"
        }
        metrics_per_class.append(metrics_class)

#Creación de DataFrame con métricas por clase
df_metrics_per_class = pd.DataFrame(metrics_per_class)

#Tabla de métricas por clase
print("\nMétricas por Clase:")
print(df_metrics_per_class.to_string(index=False))

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""## Experimento extra 1.3"""

#Documentación
#Definición de directorios para el tercer experimento
output_dir = "./outputs/weights_model1_est"
shutil.make_archive("./outputs/weights_model1_est", 'zip', output_dir)
logging_dir = "./logs/weights_model1_est"
shutil.make_archive("./logs/weights_model1_est", 'zip', output_dir)

#Si directorios no existen, crearlos
os.makedirs(output_dir, exist_ok=True)
os.makedirs(logging_dir, exist_ok=True)

"""Entrenamiento con hiperparámetros originales"""

#Definición de hiperparámetros estándar
training_args_weights_model1_est = TrainingArguments(
    output_dir=output_dir,
    logging_dir=logging_dir,
    eval_strategy="steps",
    save_strategy="steps",
    save_steps=1000,
    logging_strategy="steps",
    logging_steps=1000,
    seed=42,
    fp16=True,
    load_best_model_at_end=True,
    metric_for_best_model="f1",
)

#Definición de un objeto de la clase Trainer para el tercer experimento con el modelo 1
trainer_weights_model1_est = WeightedLossTrainer(
    model = model1,
    args = training_args_weights_model1_est,
    train_dataset = encoded_dataset_es_1['train'],
    eval_dataset = encoded_dataset_es_1['validation'],
    compute_metrics=compute_metrics,
    tokenizer = tokenizer1,
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer1),
    optimizers = (optimizer, None),
    callbacks = [early_stopping])

"""Entrenamiento"""

trainer_weights_model1_est.train()

"""Validación"""

trainer_weights_model1_est.evaluate()

"""Reporte de clasificación (sobre conjunto de validación)"""

#Obtención de predicciones del conjunto de validación
predictions = trainer_weights_model1_est.predict(encoded_dataset_es_1['validation'])
y_true = predictions.label_ids
y_pred = predictions.predictions.argmax(-1)

print("Predicciones:")

#Generación del reporte (diccionario)
reporte_dict = classification_report(y_true, y_pred, output_dict=True)

#Reporte completo (texto)
print("Reporte de Clasificación:")
print(classification_report(y_true, y_pred))

#Preparación de datos para el DataFrame
metrics_per_class = []
for label, metrics in reporte_dict.items():
    if label.isdigit():
        metrics_class = {
            "Clase": label,
            "Precisión": f"{metrics['precision']:.2f}",
            "Recall": f"{metrics['recall']:.2f}",
            "F1-score": f"{metrics['f1-score']:.2f}"
        }
        metrics_per_class.append(metrics_class)

#Creación de DataFrame con métricas por clase
df_metrics_per_class = pd.DataFrame(metrics_per_class)

#Tabla de métricas por clase
print("\nMétricas por Clase:")
print(df_metrics_per_class.to_string(index=False))

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""Test

Reporte de clasificación (sobre conjunto de test)
"""

#Obtención de predicciones del conjunto de test
predictions = trainer_weights_model1_est.predict(encoded_dataset_es_1['test'])
y_true = predictions.label_ids
y_pred = predictions.predictions.argmax(-1)

print("Predicciones:")

#Generación del reporte (diccionario)
reporte_dict = classification_report(y_true, y_pred, output_dict=True)

#Reporte completo (texto)
print("Reporte de Clasificación:")
print(classification_report(y_true, y_pred))

#Preparación de datos para el DataFrame
metrics_per_class = []
for label, metrics in reporte_dict.items():
    if label.isdigit():
        metrics_class = {
            "Clase": label,
            "Precisión": f"{metrics['precision']:.2f}",
            "Recall": f"{metrics['recall']:.2f}",
            "F1-score": f"{metrics['f1-score']:.2f}"
        }
        metrics_per_class.append(metrics_class)

#Creación de DataFrame con métricas por clase
df_metrics_per_class = pd.DataFrame(metrics_per_class)

#Tabla de métricas por clase
print("\nMétricas por Clase:")
print(df_metrics_per_class.to_string(index=False))

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""# Mejor modelo, nuevo dataset

## Dataset
"""

#Carga del dataset de España
dataset_ar = load_dataset("alttal/SA_opiniones_indumentaria_ES_Argentina_splits")
dataset_ar

#Unimos los splits: sólo necesitaremos uno para el test
dataset_ar = concatenate_datasets([dataset_ar['train'], dataset_ar['test'], dataset_ar['validation']])

#Ejemplo
print(dataset_ar)

#Se eliminan columnas innecesarias
dataset_ar = dataset_ar.remove_columns(["id","__index_level_0__"])
dataset_ar

"""Adaptación de los datos"""

#Las etiquetas de los datasets son strings. Se las cambia a valores numéricos
def label_to_int(label):
    if label == "POS":
        return 2
    elif label == "NEG":
        return 0
    else:
        return 1

dataset_ar_1 = dataset_ar.map(lambda x: {"label": label_to_int(x["label"])})

"""## Tokenización"""

#Tokenización del dataset
encoded_dataset_ar_1 = dataset_ar_1.map(tokenize_function1, batched=True)
#Luego de tokenizar se puede eliminar la columna "text" porque el modelo no la necesita
encoded_dataset_ar_1 = encoded_dataset_ar_1.remove_columns(["text"])
encoded_dataset_ar_1

"""## Experimento con dataset de Argentina"""

#Obtención de predicciones del conjunto de test
predictions = trainer_weights_model1_lit.predict(encoded_dataset_ar_1)
y_true = predictions.label_ids
y_pred = predictions.predictions.argmax(-1)

print("Predicciones:")

#Generación del reporte (diccionario)
reporte_dict = classification_report(y_true, y_pred, output_dict=True)

#Reporte completo (texto)
print("Reporte de Clasificación:")
print(classification_report(y_true, y_pred))

#Preparación de datos para el DataFrame
metrics_per_class = []
for label, metrics in reporte_dict.items():
    if label.isdigit():
        metrics_class = {
            "Clase": label,
            "Precisión": f"{metrics['precision']:.2f}",
            "Recall": f"{metrics['recall']:.2f}",
            "F1-score": f"{metrics['f1-score']:.2f}"
        }
        metrics_per_class.append(metrics_class)

#Creación de DataFrame con métricas por clase
df_metrics_per_class = pd.DataFrame(metrics_per_class)

#Tabla de métricas por clase
print("\nMétricas por Clase:")
print(df_metrics_per_class.to_string(index=False))