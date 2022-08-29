import time
import re
import hashlib
import hmac

import shopify


def make_signature(fields, password):
    # fields - flask request.form.items()

    # сортируем по названию поля
    fields = sorted(fields, key=lambda field: field[0])

    # берем те поля которые начинаются с x_
    fields = list(filter(
        lambda field: re.match(r'^x_', field[0]) and 'x_signature' != field[0], fields))

    # соеденяем ключ/значение
    fields = [str(field[0]) + str(field[1]) for field in fields]

    # соеденяем полностю массив в строку
    message = ''.join(fields)

    # получаем сигнатуру
    return hmac.new(password.encode('utf-8'),
                    message.encode('utf-8'),
                    hashlib.sha256).hexdigest()


def _get_data_from_metafields(metafields, namespace, key):

    for metafield in metafields:

        if metafield.namespace == namespace and metafield.key == key:

            return metafield.value

    return None


def pause_sdk(sleep):
    if shopify.Limits.credit_used() > shopify.Limits.credit_limit() / 2:
        time.sleep(sleep)


def get_data_from_metafields(namespace, key):
    """
    :param namespace: metafield namespace
    :param key: metafield key
    :return: str
    """

    shop = shopify.Shop.current()
    metafields = shop.metafields()
    data = _get_data_from_metafields(metafields, namespace, key)
    pause_sdk(2)

    if not data:

        while metafields.has_next_page():
            metafields = metafields.next_page()
            data = _get_data_from_metafields(metafields, namespace, key)

            if data:
                break

            pause_sdk(2)

    return data
