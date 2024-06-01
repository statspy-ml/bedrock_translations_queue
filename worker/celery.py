from __future__ import absolute_import, unicode_literals
from celery import Celery

app = Celery('tasks',
             broker='pyamqp://user:password@rabbitmq//',
             backend='db+postgresql://user:password@postgres/translations',
             include=['tasks']

app.conf.update(
    result_expires=3600,
)

if __name__ == '__main__':
    app.start()
