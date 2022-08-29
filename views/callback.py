import time
import datetime
import hashlib
import hmac
import json

import requests
import shopify
from flask import request, abort, jsonify
from lib.shopify import make_signature, get_data_from_metafields
from lib.aescipher import AESCipher
from models import Order, Refund
from app import app


def get_x_result(transaction_status):
    refund_transaction = False
    x_result = False

    if transaction_status == 'Created':
        x_result = 'pending'

    elif transaction_status == 'InProcessing':
        x_result = 'pending'

    elif transaction_status == 'WaitingAuthComplete':
        x_result = 'pending'

    elif transaction_status == 'Approved':
        x_result = 'completed'

    elif transaction_status == 'Pending':
        x_result = 'pending'

    elif transaction_status == 'Expired':
        x_result = 'failed'

    elif transaction_status == 'Refunded':
        x_result = 'completed'
        refund_transaction = True

    elif transaction_status == 'Voided':
        x_result = 'completed'
        refund_transaction = True

    elif transaction_status == 'Declined':
        x_result = 'failed'

    elif transaction_status == 'RefundInProcessing':
        x_result = 'pending'
        refund_transaction = True

    return x_result, refund_transaction


def get_merchant_data(app, entity):
    data = None
    # получаем пароль шлюза, апи кей/секрет шлюза
    # попытаемся получить с метаполей
    with shopify.Session.temp(entity.merchant.shop_name, app.config.get('SHOPIFY_VERSION'),
                              entity.merchant.token):
        data = get_data_from_metafields(app.config.get('METAFIELD_NAMESPACE'),
                                        'merchant')

    # попытаемся получить с базы
    if not data:
        data = entity.merchant.merchant

    return data


@app.route('/callback', methods=['POST'])
def callback():

    try:
        json_str = request.get_data(as_text=True)
        request_callback = json.loads(json_str)
        print(request_callback)

    except:
        print('json error')
        abort(403)

    x_result, refund_transaction = get_x_result(request_callback.get('transactionStatus'))

    if not x_result:
        print('not x_result')
        abort(403)

    if refund_transaction:
        try:
            _amount = request_callback.get('amount')

            if type(_amount) is int or type(_amount) is float:
                _amount = '{:.2f}'.format(_amount)

            trans = Refund.get((Refund.order_reference == request_callback.get('orderReference')) &
                               (Refund.x_amount == _amount))

        except Refund.DoesNotExist:
            print('no row refund')
            abort(403)

    else:

        try:
            order_id = int(request_callback['orderReference'].replace(app.config.get('PREFIX_ID'), ''))
            trans = Order.get(Order.id == order_id)

        except Order.DoesNotExist:
            print('no row order')
            abort(403)

    merchant_data = get_merchant_data(app, trans)
    request_shopify = json.loads(trans.request_shopify)

    if not merchant_data:
        abort(403)

    cipher = AESCipher(app.config.get('KEY_CRYPTO'))
    merchant_data = cipher.decrypt(merchant_data.encode('utf-8'))
    merchant_data = json.loads(merchant_data)

    shopify_password = merchant_data['password']
    merchantSecretKey = merchant_data['SecretKey']

    merchantSignature = request_callback.get('merchantSignature')

    if not merchantSignature:
        abort(403)

    msg = ';'.join([str(item) for item in [
        request_callback['merchantAccount'],
        request_callback['orderReference'],
        request_callback['amount'],
        request_callback['currency'],
        request_callback['authCode'],
        request_callback['cardPan'],
        request_callback['transactionStatus'],
        request_callback['reasonCode']
    ]])
    merchantSignatureCalc = hmac.new(merchantSecretKey.encode('utf-8'),
                                     msg.encode('utf-8'),
                                     hashlib.md5).hexdigest()

    if merchantSignature != merchantSignatureCalc:
        abort(403)

    trans.request_callback = json.dumps(request_callback)
    trans.status = request_callback['transactionStatus']
    trans.save()

    # готовим параметры для отправки на шопифай
    x_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    params = {
        'x_account_id': request_shopify['x_account_id'],
        'x_reference': request_shopify['x_reference'],
        'x_currency': request_shopify['x_currency'],
        'x_test': request_shopify['x_test'],
        'x_amount': request_shopify['x_amount'],
        'x_gateway_reference': request_callback['orderReference'],
        'x_timestamp': x_timestamp,
        'x_result': x_result
    }

    if refund_transaction:
        params.update({
            'x_transaction_type': request_shopify.get('x_transaction_type')
        })

    fields = [(k, params[k]) for k in params]
    params['x_signature'] = make_signature(fields, shopify_password)

    # отправляем на колбек шопифая данные
    r = requests.post(request_shopify['x_url_callback'], params)
    status_code = r.status_code
    print(status_code)

    if r.status_code != 200:
        print(r.text)

    # готовим параметры для ОТВЕТА шлюзу
    orderDate = int(time.mktime(datetime.datetime.utcnow().timetuple()))
    response_callback = {
        'orderReference': request_callback['orderReference'],
        'status': 'accept',
        'time': orderDate
    }
    msg = ';'.join([str(item) for item in [
        response_callback['orderReference'],
        response_callback['status'],
        response_callback['time']
    ]])
    signature = hmac.new(merchantSecretKey.encode('utf-8'),
                         msg.encode('utf-8'),
                         hashlib.md5).hexdigest()
    response_callback['signature'] = signature

    return jsonify(response_callback)
