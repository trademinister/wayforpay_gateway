import os

from flask import Flask
from flask_peewee.db import Database

app = Flask(__name__)
app.config.from_pyfile('config.py')

if os.environ.get('YOURAPPLICATION_SETTINGS'):
    app.config.from_envvar('YOURAPPLICATION_SETTINGS')

db = Database(app)


'''




@app.route('/refund', methods=['POST'])
def refund():

    if not request.is_json:
        abort(403)

    j = request.get_json()
    j_orig = dict(j)

    try:
        merchant = Merchant.get(Merchant.shopify_shopname == j['x_account_id'].lower())

    except Merchant.DoesNotExist:
        print('not merchant')
        abort(403)

    except Exception:
        print('not x_account_id')
        abort(403)

    ### проверим сигнатуру ###
    # 1) подготовим json для функции make_signature

    if 'x_test' in j:

        if j['x_test']:
            j['x_test'] = 'true'
            print('тестовый')
            return '', 200  # если тестовый запрос

        else:
            j['x_test'] = 'false'

    j_sign = [(k, j[k]) for k in j]

    # 2) проверяем сигнатуру
    check_sign = make_signature(j_sign, merchant.shopify_password)

    print(check_sign)

    if j['x_signature'].lower() != check_sign.lower():
        print('not signature')
        abort(403)

    # 3) проверить соотвествует ли ID order-а в таблице на шлюзе - магазину (взять метаполе)
    # авторизируемся
    shop_url = "https://%s:%s@%s.myshopify.com/admin" % (
        merchant.shopifyapi_login,
        merchant.shopifyapi_password,
        merchant.shopify_shopname)
    shopify.ShopifyResource.set_site(shop_url)

    order_shopify = shopify.Order.find(int(j['x_shopify_order_id']))
    metafields = order_shopify.metafields()
    order_id = None  # с метаполя

    if metafields:

        for metafield in metafields:
            metafield = metafield.to_dict()

            if metafield.get('namespace') == 'liqpay' and metafield.get('key') == 'order_id':

                try:
                    order_id = int(metafield.get('value'))

                except:
                    pass

    # очищаем сесию шопифая
    shopify.ShopifyResource.clear_session()

    if not order_id:
        print('нету ордера в метаполе')
        abort(403)

    try:
        order = Order.get(Order.id == order_id)

    except Order.DoesNotExist:
        print('нету ордера в таблице')
        abort(403)

    if order.merchant != merchant:
        print('ордер не принадлежит магазину')
        abort(403)

    ### делаем запрос на отмену платежа
    params_payment = {
        'action': 'refund',
        'version': '3',
        #'public_key': merchant.liqpay_pub_key,
        'order_id': str(order_id),
        'amount': j['x_amount']
    }

    print(params_payment)

    liqpay = LiqPay(merchant.liqpay_pub_key, merchant.liqpay_priv_key)

    try:
        result_payment = liqpay.api('request', params_payment)
        status = result_payment['status']
        result = result_payment['result']
        #result_payment = {}
        #status = ''
        #result = ''

        if status == 'reversed' or status == 'sanbox':
            # готовим гет параметры для отправки на shopify x_url_complete
            params_callback = {
                'x_account_id': j['x_account_id'],
                'x_reference': j['x_reference'],
                'x_currency': j['x_currency'],
                'x_test': j['x_test'],
                'x_amount': j['x_amount'],
                'x_gateway_reference': j['x_gateway_reference'],
                'x_timestamp': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                # result_gateway['refund']['request_date'], # берем с обьекта refund
                'x_result': 'completed',
                # 'x_result': 'pending',
                'x_transaction_type': 'refund'
            }
            fields = [(k, params_callback[k]) for k in params_callback]
            params_callback['x_signature'] = make_signature(fields, merchant.shopify_password)
            print('параметры на колб. шопифая')
            print(params_callback)
            # отправляем на колбек шопифая данные

            r = requests.post(j['x_url_callback'], params_callback)

            print(r.status_code)
            print(r.text)

    except:
        print('liqpay error')
        result_payment = {}
        status = ''
        result = ''
        pass

    # сохраняем все в базе
    refund_obj = Refund()
    refund_obj.merchant = merchant
    refund_obj.x_shopify_order_id = j['x_shopify_order_id']
    refund_obj.x_amount = j['x_amount']
    refund_obj.request_shopify = json.dumps(j_orig)
    refund_obj.params_payment = json.dumps(params_payment)

    refund_obj.result_payment = json.dumps(result_payment)
    refund_obj.status = status
    refund_obj.result = result
    refund_obj.save()

    return ''

'''
