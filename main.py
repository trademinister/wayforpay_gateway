from app import app
from views.home import home
from views.callback import callback
from views.success import success
import views.refund


if __name__ == '__main__':
    app.run(host=app.config.get('IP'), port=app.config.get('PORT'))
