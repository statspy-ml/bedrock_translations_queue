import os
from celery import Celery
import time


app = Celery('producer',
             broker='pyamqp://user:password@localhost//',
             backend='db+postgresql://user:password@localhost/translations')


messages = [
    {"chave": 6, "comentario": "eye balls burning"},
    {"chave": 7, "comentario": "my blood is so hot"},
    {"chave": 8, "comentario": "dizzness and insomina"},
    
]


for message in messages:
    app.send_task('tasks.send_to_queue', args=[message['chave'], message['comentario']])
    time.sleep(1)  

print("Todas as mensagens foram enviadas.")
