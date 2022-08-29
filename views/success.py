import datetime
import json
from urllib.parse import urlencode
import shopify
from flask import request, abort, redirect

from lib.aescipher import AESCipher
from lib.shopify import make_signature, get_data_from_metafields

from app import app
from models import Order


@app.route('/success', methods=['POST'])
def success():
    app.logger.warning('success form data')
    app.logger.warning(request.form)
    request_callback = request.form.to_dict()

    try:
        order_id = int(request_callback['orderReference'].replace(app.config.get('PREFIX_ID'), ''))
        order = Order.get(Order.id == order_id)
        request_shopify = json.loads(order.request_shopify)
        merchant = order.merchant

    except Order.DoesNotExist:
        abort(403)

    data = None
    # получаем пароль шлюза, апи кей/секрет шлюза
    # попытаемся получить с метаполей
    with shopify.Session.temp(merchant.shop_name, app.config.get('SHOPIFY_VERSION'),
                              merchant.token):
        data = get_data_from_metafields(app.config.get('METAFIELD_NAMESPACE'),
                                        'merchant')

    # попытаемся получить с базы
    if not data:
        data = merchant.merchant

    cipher = AESCipher(app.config.get('KEY_CRYPTO'))
    data = cipher.decrypt(data.encode('utf-8'))
    data = json.loads(data)

    shopify_password = data['password']

    if order.status == 'Approved':
        x_result = 'completed'

    elif order.status in ['Pending', 'Created', 'InProcessing', 'WaitingAuthComplete']:
        x_result = 'pending'

    else:
        x_result = 'failed'

    if x_result in ['completed', 'pending']:
        x_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        # готовим гет параметры для отправки на shopify x_url_complete
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
        fields = [(k, params[k]) for k in params]
        params['x_signature'] = make_signature(fields, shopify_password)
        url_complete = request_shopify['x_url_complete'] + '?' + urlencode(params)

        return redirect(url_complete)

    else:
        return redirect(request_shopify['x_url_cancel'])
