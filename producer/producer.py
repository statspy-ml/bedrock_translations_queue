import os
import pandas as pd
from tasks import send_to_queue
import time

# Leitura do dataset
data = pd.read_csv('dataset.csv')

# Configuração do tamanho do lote
batch_size = 10000  # Ajuste conforme necessário

# Enviar mensagens não processadas para a fila em lotes
for i in range(0, len(data), batch_size):
    batch = data[i:i + batch_size]
    for _, row in batch.iterrows():
        send_to_queue.delay(row['chave'], row['comentario'])
    time.sleep(1)  # Pequeno atraso para evitar sobrecarga
