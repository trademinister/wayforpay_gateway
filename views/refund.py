import json
import hmac
import hashlib
import datetime

import requests
import shopify
from flask import request, abort

from lib.shopify import make_signature, get_data_from_metafields
from lib.aescipher import AESCipher
from app import app
from models import Merchant, Refund


@app.route('/refund', methods=['POST'])
def refund_view():

    if not request.is_json:
        abort(403)

    j = request.get_json()

    print(j)

    if 'x_test' in j:

        if j['x_test']:
            j['x_test'] = 'true'

        else:
            j['x_test'] = 'false'

    try:
        # shop_name до .myshopify.com
        shop_name = '{}.myshopify.com'.format(j['x_account_id'])
        merchant = Merchant.get(Merchant.shop_name == shop_name)

    except:
        abort(403)

    data = None
    # получаем пароль шлюза, апи кей/секрет шлюза
    # попытаемся получить с метаполей
    with shopify.Session.temp(shop_name, app.config.get('SHOPIFY_VERSION'),
                              merchant.token):
        data = get_data_from_metafields(app.config.get('METAFIELD_NAMESPACE'),
                                        'merchant')

    # попытаемся получить с базы
    if not data:
        data = merchant.merchant

    if not data:
        abort(403)

    cipher = AESCipher(app.config.get('KEY_CRYPTO'))
    data = cipher.decrypt(data.encode('utf-8'))
    data = json.loads(data)

    shopify_password = data['password']
    merchantAccount = data['merchantAccount']
    merchantSecretKey = data['SecretKey']

    ### проверим сигнатуру ###
    # 1) подготовим json для функции make_signature
    j_sign = [(k, j[k]) for k in j]

    # 2) проверяем сигнатуру
    check_sign = make_signature(j_sign, shopify_password)

    if j['x_signature'].lower() != check_sign.lower():
        print('not signature')
        abort(403)

    # параметры на шлюз
    params = {
        'transactionType': 'REFUND',
        'merchantAccount': merchantAccount,
        'orderReference': str(j['x_gateway_reference']),
        'amount': j['x_amount'],
        'currency': j['x_currency'],
        #'currency': 'UAH',
        'comment': 'Refund',
        'apiVersion': '1'
    }
    msg = ';'.join([str(item) for item in [
        params['merchantAccount'],
        params['orderReference'],
        params['amount'],
        params['currency'],
    ]])
    merchantSignature = hmac.new(merchantSecretKey.encode('utf-8'),
                                 msg.encode('utf-8'),
                                 hashlib.md5).hexdigest()
    params['merchantSignature'] = merchantSignature

    r = requests.post('https://api.wayforpay.com/api', json=params)

    if r.status_code != 200:
        print(r.status_code)
        abort(403)

    result_gateway = r.json()
    print(result_gateway)

    # проверяем код ответа
    # https://wiki.wayforpay.com/pages/viewpage.action?pageId=852131


    # параметры на колбек шопифая
    if result_gateway['reasonCode'] == 1100 and \
            result_gateway['transactionStatus'] == 'Refunded':
        x_result = 'completed'

    elif result_gateway['reasonCode'] == 1100 and \
            result_gateway['transactionStatus'] == 'Voided':
        x_result = 'completed'

    elif result_gateway['reasonCode'] == 1100 and \
            result_gateway['transactionStatus'] == 'RefundInProcessing':
        x_result = 'pending'

    else:
        x_result = 'failed'

    # сохраняем в базу
    refund = Refund()
    refund.merchant = merchant
    refund.order_reference = j['x_gateway_reference']
    refund.x_amount = j['x_amount']
    refund.request_shopify = json.dumps(j)
    refund.params_gateway = json.dumps(params)
    refund.result_gateway = json.dumps(result_gateway)
    refund.status = result_gateway['transactionStatus']
    refund.save()

    # отправляем на колбек
    x_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    params = {
        'x_account_id': j['x_account_id'],
        'x_reference': j['x_reference'],
        'x_currency': j['x_currency'],
        'x_test': j['x_test'],
        'x_amount': j['x_amount'],
        'x_gateway_reference': j['x_gateway_reference'],
        'x_timestamp': x_timestamp,
        'x_result': x_result,
        'x_transaction_type': j['x_transaction_type']
    }
    fields = [(k, params[k]) for k in params]
    params['x_signature'] = make_signature(fields, shopify_password)

    # отправляем на колбек шопифая данные
    r = requests.post(j['x_url_callback'], params)

    if r.status_code != 200:
        print(r.status_code)
        print(r.text)
        abort(403)

    return ''

