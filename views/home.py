import time
import datetime
import json
import hashlib
import hmac

from flask import request, abort, render_template
import shopify

from lib.shopify import make_signature, get_data_from_metafields
from lib.aescipher import AESCipher
from app import app
from models import Merchant, Order


@app.route('/', methods=['POST'])
def home():

    print(request.form)

    # x_account_id == shopify_shopname
    shop_name = request.form.get('x_account_id')

    if not shop_name:
        print('not x_shop_name')
        abort(403)

    shop_name = '{}.myshopify.com'.format(shop_name.lower())

    try:
        merchant = Merchant.get(Merchant.shop_name == shop_name)

        if not merchant.enable:

            return 'merchant is disable', 403

    except Merchant.DoesNotExist:
        print('not merchant')
        abort(403)

    data = None
    # получаем пароль шлюза, апи кей/секрет шлюза
    # попытаемся получить с метаполей
    with shopify.Session.temp(shop_name, app.config.get('SHOPIFY_VERSION'),
                              merchant.token):
        shop = shopify.Shop.current()
        data = get_data_from_metafields(app.config.get('METAFIELD_NAMESPACE'),
                                        'merchant')
        override_lang = get_data_from_metafields(app.config.get('METAFIELD_NAMESPACE'),
                                                 'override_lang')
        # берем язык с магазина
        lang = shop.primary_locale.upper()

        # переопределяем если есть в метаполе
        if override_lang:
            lang = override_lang.strip().upper()

        if len(lang) > 2:
            lang = lang[:2]

        # берем домен если есть
        domain = shop.domain

    # попытаемся получить с базы
    if not data:
        data = merchant.merchant

    if not data:
        app.logger.warning('not data')
        abort(403)

    cipher = AESCipher(app.config.get('KEY_CRYPTO'))
    data = cipher.decrypt(data.encode('utf-8'))
    data = json.loads(data)

    print('***')
    print(data)
    print('***')
    shopify_password = data['password']
    merchantAccount = data['merchantAccount']
    merchantSecretKey = data['SecretKey']


    # проверяем сигнатуру
    check_sign = make_signature(request.form.items(), shopify_password)

    if request.form['x_signature'].lower() != check_sign.lower():
        app.logger.warning('not signature')
        abort(403)

    x_reference = request.form['x_reference']
    amount = request.form.get('x_amount')

    # надо сохранить в базу
    order = Order()
    order.merchant = merchant
    order.x_reference = x_reference
    order.x_amount = amount
    order.request_shopify = json.dumps(request.form.to_dict())
    order.save()

    returnUrl = app.config['HTTP_HOST'] + '/success'
    serviceUrl = app.config['HTTP_HOST'] + '/callback'
    orderDate = int(time.mktime(datetime.datetime.utcnow().timetuple()))
    #merchantAccount = 'test_merch_n1'
    #merchantSecretKey = 'flk3409refn54t54t*FNJRET'

    clientAddress = '{}, {}'.format(
        request.form.get('x_customer_billing_address1'),
        request.form.get('x_customer_billing_address2')
    )

    params = {
        'merchantAccount': merchantAccount,
        'merchantDomainName': domain,
        'merchantTransactionSecureType': 'AUTO',
        'merchantSignature': '',
        'returnUrl': returnUrl,
        'serviceUrl': serviceUrl,
        'orderReference': '{}{}'.format(app.config.get('PREFIX_ID'), order.id),
        'orderDate': orderDate,
        'amount': amount,
        #'currency': 'UAH',
        #'currency': 'USD',
        'currency': request.form.get('x_currency'),
        'language': 'EN',
        'productName[]': 'Selected products',
        'productPrice[]': amount,
        'productCount[]': 1,

        'clientFirstName': request.form.get('x_customer_first_name'),
        'clientLastName': request.form.get('x_customer_last_name'),
        'clientAddress': clientAddress,
        'clientCity': request.form.get('x_customer_billing_city'),
        'clientCountry': request.form.get('x_customer_billing_country'),
        'clientZipCode': request.form.get('x_customer_billing_zip')
    }

    if lang == 'UK':
        lang = 'UA'

    if lang in ['RU', 'UA']:
        params['language'] = lang

    if params['language'] == 'RU':
        params['productName[]'] = 'Товары в ассортименте'

    elif params['language'] == 'UA':
        params['productName[]'] = 'Товари в асортименті'

    msg = ';'.join([str(item) for item in [
        params['merchantAccount'],
        params['merchantDomainName'],
        params['orderReference'],
        params['orderDate'],
        params['amount'],
        params['currency'],
        params['productName[]'],
        params['productCount[]'],
        params['productPrice[]']
    ]])
    print('***')
    print(msg)
    print('***')
    merchantSignature = hmac.new(merchantSecretKey.encode('utf-8'),
                                 msg.encode('utf-8'),
                                 hashlib.md5).hexdigest()
    params['merchantSignature'] = merchantSignature

    # сохраняем параметры запроса
    order.params_gateway = json.dumps(params)
    order.save()

    print(params)

    return render_template('home.html', params=params)
