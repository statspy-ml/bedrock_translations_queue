import pika
import json

# Configurações de conexão RabbitMQ
credentials = pika.PlainCredentials('user', 'password')
parameters = pika.ConnectionParameters('localhost', 5672, '/', credentials)
import os
import pandas as pd
from celery import Celery
import time

# Configurar Celery
app = Celery('producer',
             broker='pyamqp://user:password@localhost//',
             backend='db+postgresql://user:password@localhost/translations')

# Leitura do dataset
data = pd.read_csv('dataset.csv')

# Configuração do tamanho do lote
batch_size = 10000  # Ajuste conforme necessário

# Enviar mensagens não processadas para a fila em lotes
for i in range(0, len(data), batch_size):
    batch = data[i:i + batch_size]
    for _, row in batch.iterrows():
        app.send_task('tasks.send_to_queue', args=[row['chave'], row['comentario']])
    time.sleep(1)  # Pequeno atraso para evitar sobrecarga


