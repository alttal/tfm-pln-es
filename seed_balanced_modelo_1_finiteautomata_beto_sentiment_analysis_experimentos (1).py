# -*- coding: utf-8 -*-
"""seed - balanced - Modelo 1 - finiteautomata/beto-sentiment-analysis - Experimentos

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/13_oSZUykSG-0jtSajGqvFnEMx9r4GgqM

# Preparación del entorno: instalaciones y librerías
"""

#Instalaciones
!pip install -q datasets

#Librerías
import os
import pandas as pd
import glob
import shutil
from google.colab import drive
import torch.nn.functional as F
from torch.optim import Adam

#Semilla
SEED = 42

#Librerías donde fijar semilla para garantizar reproducibilidad
import random
random.seed(SEED)
import numpy as np
np.random.seed(SEED)
import torch
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
import seaborn as sns
import matplotlib.pyplot as plt
import transformers
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments, DataCollatorWithPadding, EarlyStoppingCallback, set_seed
set_seed(SEED)
from datasets import load_dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, f1_score, confusion_matrix
from sklearn.model_selection import ParameterGrid

"""# Dataset"""

#Carga del dataset de España
dataset_es = load_dataset("alttal/balanced_SA_opiniones_indumentaria_ES_Espanya_splits")

dataset_es

"""# Métricas de evaluación"""

#Definimos las métricas para evaluar el modelo
#Este conjunto de métricas depende de la tarea.
#Para clasificación de textos se suelen utilizar accuracy, precision, recall y F1-score.

def compute_metrics(pred):
  y_true = pred.label_ids              # son las etiquetas reales
  y_pred = pred.predictions.argmax(-1) # son las predicciones
  acc = accuracy_score(y_true, y_pred)
  precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='macro')

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
path = '/content/drive/My Drive/TFM/Experimentos balanced'

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

"""##Tokenización del dataset"""

#Carga del tokenizador específico
tokenizer1 = AutoTokenizer.from_pretrained("finiteautomata/beto-sentiment-analysis")

#Se define tokenizador del primer modelo
def tokenize_function1(example):
    return tokenizer1(example["text"], padding='longest', truncation=True)

#Tokenización del dataset
encoded_dataset_es_1 = dataset_es.map(tokenize_function1, batched=True)
#Luego de tokenizar se puede eliminar la columna "text" porque el modelo no la necesita
encoded_dataset_es_1 = encoded_dataset_es_1.remove_columns(["text"])
encoded_dataset_es_1

#Ejemplo de la tokenización en cada split
print(encoded_dataset_es_1['train'][0])
print(encoded_dataset_es_1['validation'][0])
print(encoded_dataset_es_1['test'][0])

"""## Experimento 1.1"""

#Documentación
#Definición de directorios para el primer experimento
output_dir = "./outputs/model1_lit"
shutil.make_archive("./outputs/model1_lit", 'zip', output_dir)
logging_dir = "./logs/model1_lit"
shutil.make_archive("./logs/model1_lit", 'zip', output_dir)

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
training_args_model1_lit = TrainingArguments(
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
    seed=SEED,                       # Semilla para garantizar reproducibilidad
    fp16=True,                       # Uso de fp16 para acelerar el entrenamiento
    load_best_model_at_end=True,     # Cargar el mejor modelo al final del entrenamiento
    metric_for_best_model="f1",      # Métrica objetivo, a optimizar para encontrar el mejor modelo
)

#Definición de optimizador
optimizer = Adam(model1.parameters(), lr=3e-5, weight_decay=0.01)

#Definición de un objeto de la clase Trainer para el primer experimento con el modelo 1
trainer_model1_lit = Trainer(
    model = model1,
    args = training_args_model1_lit,
    train_dataset = encoded_dataset_es_1['train'],
    eval_dataset = encoded_dataset_es_1['validation'],
    compute_metrics=compute_metrics,
    tokenizer = tokenizer1,
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer1),
    optimizers = (optimizer, None),
    callbacks = [early_stopping])

"""Entrenamiento"""

trainer_model1_lit.train()

"""Validación"""

trainer_model1_lit.evaluate()

"""Reporte de clasificación (sobre conjunto de validación)"""

#Obtención de predicciones del conjunto de validación
predictions = trainer_model1_lit.predict(encoded_dataset_es_1['validation'])
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

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""Test

Reporte de clasificación (sobre conjunto de test)
"""

#Obtención de predicciones del conjunto de test
predictions = trainer_model1_lit.predict(encoded_dataset_es_1['test'])
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

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""## Grid Search

Búsqueda de hiperparámetros optimizados con la técnica Grid Search:
"""

#Definición del espacio de búsqueda
param_grid = {
    'num_train_epochs': [3, 5],
    'per_device_train_batch_size': [16, 32],
    'per_device_eval_batch_size': [16, 32],
    'learning_rate': [1e-5, 2e-5, 3e-5, 5e-5, 1e-4],
    'weight_decay': [0.01, 0.1]
}

grid = ParameterGrid(param_grid)

#Función para calcular el f1-score
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = logits.argmax(axis=-1)
    return {
        'f1': f1_score(labels, predictions, average='macro')
    }

#Inicialización de variables para guardar los mejores resultados
best_score = 0
best_params = None

#Documentación
#Definición de directorios para el primer experimento
output_dir = "./outputs/model1_search"
shutil.make_archive("./outputs/model1_search", 'zip', output_dir)
logging_dir = "./logs/model1_search"
shutil.make_archive("./logs/model1_search", 'zip', output_dir)

#Si directorios no existen, crearlos
os.makedirs(output_dir, exist_ok=True)
os.makedirs(logging_dir, exist_ok=True)

#Bucle para probar los diferentes parámetros
for params in grid:
    print(f"Entrenando con parámetros: {params}")

    #Definición de hiperparámetros
    training_args_model1_search = TrainingArguments(
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
        save_total_limit=1,                                                     # Número máximo de checkpoints a guardar (para evitar problemas de almacenamiento)
        seed=SEED,                                                              # Semilla para garantizar reproducibilidad
        fp16=True,                                                              # Uso de fp16 para acelerar el entrenamiento
        load_best_model_at_end=True,                                            # Cargar el mejor modelo al final del entrenamiento
        metric_for_best_model='f1',                                             # Métrica objetivo, a optimizar para encontrar el mejor modelo
    )

    #Definición de un objeto de la clase Trainer para la búsqueda con el modelo 1
    trainer_model1_search = Trainer(
        model=model1,
        args=training_args_model1_search,
        train_dataset=encoded_dataset_es_1['train'],
        eval_dataset=encoded_dataset_es_1['validation'],
        tokenizer=tokenizer1,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer1),
        compute_metrics=compute_metrics,
        optimizers = (optimizer, None),
        callbacks = [early_stopping]
    )

    #Entrenamiento
    trainer_model1_search.train()

    #Limpiar logs antiguos después del entrenamiento en cada iteración
    clean_old_logs(logging_dir, keep_last_n=1)

    #Validación
    eval_result = trainer_model1_search.evaluate()

    #Guardamos métrica objetivo
    score = eval_result.get('eval_f1', 0)

    #Siempre que la métrica objetivo sea mejor que el score guardado hasta el momento, se lo actualiza
    if score > best_score:
        best_score = score
        best_params = params

#Vemos los resultados del Grid Search
print(f"Mejores parámetros: {best_params}")
print(f"Mejor puntuación F1: {best_score}")

"""## Experimento 1.2."""

#Documentación
#Definición de directorios para el segundo experimento
output_dir = "./outputs/model1_opt"
shutil.make_archive("./outputs/model1_opt", 'zip', output_dir)
logging_dir = "./logs/model1_opt"
shutil.make_archive("./logs/model1_opt", 'zip', output_dir)

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
training_args_model1_opt = TrainingArguments(
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
    weight_decay=0.1,                                     # Decadencia de peso
    save_total_limit=1,                                   # Número máximo de checkpoints a guardar (para evitar problemas de almacenamiento)
    seed=42,                                              # Semilla para garantizar reproducibilidad
    fp16=True,                                            # Uso de fp16 para acelerar el entrenamiento
    load_best_model_at_end=True,                          # Cargar el mejor modelo al final del entrenamiento
    metric_for_best_model="f1",                           # Métrica objetivo, a optimizar para encontrar el mejor modelo
)

#Definición de optimizador
optimizer = Adam(model1.parameters(), lr=params['learning_rate'], weight_decay=params['weight_decay'])

#Definición de un objeto de la clase Trainer para el segundo experimento con el modelo 1
trainer_model1_opt = Trainer(
    model = model1,
    args = training_args_model1_opt,
    train_dataset = encoded_dataset_es_1['train'],
    eval_dataset = encoded_dataset_es_1['validation'],
    compute_metrics=compute_metrics,
    tokenizer = tokenizer1,
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer1),
    optimizers = (optimizer, None),
    callbacks = [early_stopping])

"""Entrenamiento"""

trainer_model1_opt.train()

"""Validación"""

trainer_model1_opt.evaluate()

"""Reporte de clasificación (sobre conjunto de validación)"""

#Obtención de predicciones del conjunto de validación
predictions = trainer_model1_opt.predict(encoded_dataset_es_1['validation'])
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

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""Test

Reporte de clasificación (sobre conjunto de test)
"""

#Obtención de predicciones del conjunto de test
predictions = trainer_model1_opt.predict(encoded_dataset_es_1['test'])
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

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""## Experimento extra 1.3"""

#Documentación
#Definición de directorios para el tercer experimento
output_dir = "./outputs/model1_est"
shutil.make_archive("./outputs/model1_est", 'zip', output_dir)
logging_dir = "./logs/model1_est"
shutil.make_archive("./logs/model1_est", 'zip', output_dir)

#Si directorios no existen, crearlos
os.makedirs(output_dir, exist_ok=True)
os.makedirs(logging_dir, exist_ok=True)

"""Entrenamiento con hiperparámetros originales"""

#Definición de hiperparámetros estándar
training_args_model1_estandar = TrainingArguments(
    output_dir=output_dir,
    logging_dir=logging_dir,
    eval_strategy="steps",
    save_strategy="steps",
    save_steps=1000,
    logging_strategy="steps",
    logging_steps=1000,
    seed=SEED,
    fp16=True,
    load_best_model_at_end=True,
    metric_for_best_model="f1",
)

#Definición de un objeto de la clase Trainer para el tercer experimento con el modelo 1
trainer_model1_estandar = Trainer(
    model = model1,
    args = training_args_model1_estandar,
    train_dataset = encoded_dataset_es_1['train'],
    eval_dataset = encoded_dataset_es_1['validation'],
    compute_metrics=compute_metrics,
    tokenizer = tokenizer1,
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer1)
)

"""Entrenamiento"""

trainer_model1_estandar.train()

"""Validación"""

trainer_model1_estandar.evaluate()

"""Reporte de clasificación (sobre conjunto de validación)"""

#Obtención de predicciones del conjunto de validación
predictions = trainer_model1_estandar.predict(encoded_dataset_es_1['validation'])
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

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""Test

Reporte de clasificación (sobre conjunto de test)
"""

#Obtención de predicciones del conjunto de test
predictions = trainer_model1_estandar.predict(encoded_dataset_es_1['test'])
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

#Limpiar logs antiguos
clean_old_logs(logging_dir, keep_last_n=1)

"""## Experimento final: mejor modelo, nuevo dataset"""

#Elección del mejor modelo
#Modelo final -> Modelo con hiperparámetros recomendados
#Carga del nuevo dataset: comentarios de Argentina
dataset_ar = load_dataset("alttal/SA_opiniones_indumentaria_ES_Argentina_splits")

#Unimos los splits: sólo necesitaremos uno para el test
from datasets import concatenate_datasets
dataset_ar = concatenate_datasets([dataset_ar['train'], dataset_ar['test'], dataset_ar['validation']])

#Ejemplo
print(dataset_ar)

#Se eliminan columnas innecesarias
dataset_ar = dataset_ar.remove_columns(["id","__index_level_0__"])
dataset_ar

#Las etiquetas de los datasets son strings. Se las cambia a valores numéricos
def label_to_int(label):
    if label == "POS":
        return 2
    elif label == "NEG":
        return 0
    else:
        return 1

dataset_ar_1 = dataset_ar.map(lambda x: {"label": label_to_int(x["label"])})

#Tokenización del dataset
encoded_dataset_ar_1 = dataset_ar_1.map(tokenize_function1, batched=True)
#Luego de tokenizar se puede eliminar la columna "text" porque el modelo no la necesita
encoded_dataset_ar_1 = encoded_dataset_ar_1.remove_columns(["text"])
encoded_dataset_ar_1

"""Reporte de clasificación sobre el conjunto de datos de Argentina"""

#Obtención de predicciones del conjunto de test
predictions = trainer_model1_lit.predict(encoded_dataset_ar_1)
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

#Matriz de confusión
conf_matrix = confusion_matrix(y_true, y_pred)

#Configuración del gráfico
plt.figure(figsize=(10, 7))
sns.heatmap(conf_matrix, annot=True, fmt='d', cmap='Blues', xticklabels=set(y_true), yticklabels=set(y_true))
plt.xlabel('Predicciones')
plt.ylabel('Valores Verdaderos')
plt.title('Matriz de Confusión - Argentina')
plt.show()