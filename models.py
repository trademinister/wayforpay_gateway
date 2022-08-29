import datetime
from peewee import CharField, DateTimeField, TextField, ForeignKeyField, BooleanField

from app import db


class Merchant(db.Model):
    shop_name = CharField(unique=True)
    token = CharField(null=True)
    created = DateTimeField(default=datetime.datetime.utcnow, null=True)  # время создания в юникоде
    merchant = TextField(null=True)  # закодированный json обьект
    enable = BooleanField(default=False, null=True)


class Order(db.Model):
    merchant = ForeignKeyField(Merchant, null=True)
    shop_name = CharField(null=True)
    x_reference = CharField(null=True)
    x_amount = CharField(null=True)
    created = DateTimeField(default=datetime.datetime.utcnow)  # время создания в юникоде
    request_shopify = TextField(null=True)  # поля которые приходит от shopify
    request_callback = TextField(null=True)  # поля которые приходят на колбек
    params_gateway = TextField(null=True)  # поля которые отправляем на шлюз
    status = CharField(null=True)


class Refund(db.Model):
    merchant = ForeignKeyField(Merchant)

    order_reference = CharField()
    x_amount = CharField()
    created = DateTimeField(default=datetime.datetime.utcnow)  # время создания в юникоде

    request_shopify = TextField(null=True)  # поля которые приходит от shopify
    params_gateway = TextField(null=True)  # параметры которые уходят на сервис
    result_gateway = TextField(null=True)  # поля которые приходят от сервиса в ответ
    status = CharField(null=True)  # от сервиса
