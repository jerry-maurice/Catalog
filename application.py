# !/usr/bin/env python
# created by Jerry Maurice
# import step
from flask import Flask, render_template, request, redirect
from flask import jsonify, url_for, flash, abort, g
from flask import session as login_session
from flask import make_response

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Items, User

import time
from redis import Redis
from functools import update_wrapper
import random
import string
import requests
import httplib2
import json

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

# client id
CLIENT_ID = json.loads(
    open('client_secret.json', 'r').read())['web']['client_id']

# name of application
APPLICATION_NAME = "Sport Catalog"
app = Flask(__name__)

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()
redis = Redis()


# Control the usage of the api
class RateLimit(object):
    expiration_window = 10

    def __init__(self, key_prefix, limit, per, send_x_headers):
        self.reset = (int(time.time()) // per) * per + per
        self.key = key_prefix + str(self.reset)
        self.limit = limit
        self.per = per
        self.send_x_headers = send_x_headers
        p = redis.pipeline()
        p.incr(self.key)
        p.expireat(self.key, self.reset + self.expiration_window)
        self.current = min(p.execute()[0], limit)

    remaining = property(lambda x: x.limit - x.current)
    over_limit = property(lambda x: x.current >= x.limit)


def get_view_rate_limit():
    return getattr(g, '_view_rate_limit', None)


def on_over_limit(limit):
    return (jsonify({'data': 'You hit the rate limit', 'error': '429'}),
            429)


def ratelimit(limit, per=300, send_x_headers=True,
              over_limit=on_over_limit,
              scope_func=lambda: request.remote_addr,
              key_func=lambda: request.endpoint):
    def decorator(f):
        def rate_limited(*args, **kwargs):
            key = 'rate-limit/%s/%s/' % (key_func(), scope_func())
            rlimit = RateLimit(key, limit, per, send_x_headers)
            g._view_rate_limit = rlimit
            if over_limit is not None and rlimit.over_limit:
                return over_limit(rlimit)
            return f(*args, **kwargs)
        return update_wrapper(rate_limited, f)
    return decorator


@app.after_request
def inject_x_rate_headers(response):
    limit = get_view_rate_limit()
    if limit and limit.send_x_headers:
        h = response.headers
        h.add('X-RateLimit-Remaining', str(limit.remaining))
        h.add('X-RateLimit-Limit', str(limit.limit))
        h.add('X-RateLimit-Reset', str(limit.reset))
    return response


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


# login a user
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'),
                                 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secret.json',
                                             scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'),
            401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."),
            401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        app.logger.info("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already' +
                                            ' connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # verify if user exist, if note create a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    return render_template('logininfo.html',
                           login_session=login_session)


# create a new user
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    app.logger.info("creating new user")
    return user.id


# get a user info
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


# get user id
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except ValueError:
        return None


# logout
@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        app.logger.info('Access Token is None')
        response = make_response(json.dumps('Current user not connected.'),
                                 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?'
    url += 'token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        flash('Successfully disconnected')
        return redirect(url_for('showHomePage'))
    else:
        response = make_response(json.dumps('Failed to revoke token for ' +
                                            'given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# first page user. this page show all the categories
@app.route('/')
@app.route('/categories')
def showHomePage():
    categories = session.query(Category).all()
    app.logger.info("user accessing the homepage")
    if 'username' not in login_session:
        return render_template('categories.html', categories=categories)
    else:
        return render_template('categoriesprotected.html',
                               categories=categories)


# adding a new category
@app.route('/categories/new', methods=['GET', 'POST'])
def newCategory():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newCategory = Category(name=request.form['title'],
                               user_id=login_session['user_id'])
        session.add(newCategory)
        flash('New Category %s successfully created' % newCategory.name)
        session.commit()
        return redirect(url_for('showHomePage'))
    else:
        return render_template('addcategory.html')


# editing a category
@app.route('/category/<int:category_id>/edit', methods=['GET', 'POST'])
def editingCategory(category_id):
    if 'username' not in login_session:
        return redirect('/login')
    editCategory = session.query(Category).filter_by(id=category_id).one()
    if request.method == 'POST':
        if editCategory.user_id != login_session['user_id']:
            return render_template('editRestricted.html',
                                   category=editCategory)
        if request.form['title']:
            editCategory.name = request.form['title']
            session.add(editCategory)
            flash('Category Successfully Edited %s' % editCategory.name)
            session.commit()
            return redirect(url_for('showHomePage'))
    else:
        return render_template('editCategory.html',
                               category_id=category_id, category=editCategory)


# delete category
@app.route('/category/<int:category_id>/delete', methods=['GET', 'POST'])
def deleteCategory(category_id):
    if 'username' not in login_session:
        return redirect('/login')
    deleteCategory = session.query(Category).filter_by(id=category_id).one()
    if request.method == 'POST':
        if deleteCategory.user_id != login_session['user_id']:
            return render_template('deleteRestricted.html',
                                   category=deleteCategory)
        session.delete(deleteCategory)
        flash('%s Successfully deleted' % deleteCategory.name)
        session.commit()
        return redirect(url_for('showHomePage'))
    else:
        return render_template('deleteCategory.html', category=deleteCategory)


# view items based on selected category
@app.route('/catalog/<int:category_id>/items')
def viewCategoryItems(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    categories = session.query(Category).all()
    items = session.query(Items).filter_by(category_id=category_id).all()
    if 'username' not in login_session:
        return render_template('items.html', items=items,
                               category=category.name, categories=categories)
    else:
        return render_template('itemsprotected.html', items=items,
                               category=category, categories=categories)


# add category items
@app.route('/catalog/<int:category_id>/items/add', methods=['GET', 'POST'])
def addCategoryItems(category_id):
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        if request.form['nameitems']:
            item = Items(name=request.form['nameitems'],
                         description=request.form['description'],
                         category_id=category_id,
                         user_id=login_session['user_id'])
            session.add(item)
            session.commit()
            flash('New category %s item successfully added' % (item.name))
            return redirect(url_for('viewCategoryItems',
                                    category_id=category_id))
    else:
        return render_template('additems.html',
                               category_id=category_id)


# edit category items
@app.route('/catalog/<int:category_id>/items/<int:item_id>/edit',
           methods=['GET', 'POST'])
def editCategoryItems(category_id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    item = session.query(Items).filter_by(id=item_id,
                                          category_id=category_id).one()
    if request.method == 'POST':
        if item.user_id != login_session['user_id']:
            return render_template('edititemRestricted.html', item=item)
        item.name = request.form['itemName']
        item.description = request.form['itemDescription']
        session.add(item)
        session.commit()
        flash('Item successfully edited')
        return redirect(url_for('viewCategoryItems', category_id=category_id))
    else:
        return render_template('editItemsProtected.html',
                               category_id=category_id, item=item)


# delete category items
@app.route('/catalog/<int:category_id>/items/<int:item_id>delete',
           methods=['GET', 'POST'])
def deleteCategoryItems(category_id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    deleteItem = session.query(Items).filter_by(id=item_id).one()
    if request.method == 'POST':
        if deleteItem.user_id != login_session['user_id']:
            return render_template('deleteitemRestricted.html',
                                   item=deleteItem)
        session.delete(deleteItem)
        session.commit()
        flash('Item successfuly deleted')
        return redirect(url_for('showHomePage'))
    else:
        return render_template('deleteItem.html', item=deleteItem,
                               category_id=category_id)


# view description of selected item
@app.route('/catalog/<int:category_id>/items/<int:item_id>/description')
def viewDetailedItem(category_id, item_id):
    item = session.query(Items).filter_by(id=item_id,
                                          category_id=category_id).one()
    if 'username' not in login_session:
        return render_template('itemDetailed.html', item=item)
    else:
        return render_template('itemDetailedprotected.html', item=item)


''' Api endpoint side of the project '''


# route decorator
@app.route('/catalog/categories', methods=['GET', 'POST'])
@ratelimit(limit=30, per=60 * 1)
def categories():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'GET':
        # method to get all the categories
        categories = session.query(Category).all()
        return jsonify(categories=[i.serialize for i in categories])
    elif request.method == 'POST':
        # method to make a new category
        category_name = request.args.get('name', '')
        if category_name:
            category = Category(name=unicode(category_name),
                                user_id=login_session['user_id'])
            session.add(category)
            session.commit()
            return jsonify(category=category.serialize)
        else:
            return jsonify({"error": "No category added"})


# category function
@app.route('/catalog/categories/<int:id>', methods=['GET', 'POST'])
@ratelimit(limit=30, per=60 * 1)
def categoryFunction(id):
    if 'username' not in login_session:
        return redirect('/login')
    category = session.query(Category).filter_by(id=id).one()
    if request.method == 'GET':
        # return a specific category
        return jsonify(category=category.serialize)

    if request.method == 'PUT':
        # update a category
        category_name = request.args.get('name')
        if category_name:
            category.name = category_name
        session.commit()
        return jsonify(category=category.serialize)

    elif request.method == 'DELETE':
        # delte category
        session.delete(category)
        session.commit()
        return "Category deleted"


# items in the category
@app.route('/catalog/category/items/<int:id>', methods=['GET', 'POST'])
@ratelimit(limit=30, per=60 * 1)
def itemsCategory(id):
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'GET':
        # method to get all the item in this category
        items = session.query(Items).filter_by(category_id=id).all()
        return jsonify(items=[i.serialize for i in items])

    elif request.method == 'POST':
        # method to make a new category
        item_name = request.args.get('name', '')
        item_description = request.args.get('description', '')
        if item_name:
            item = Item(name=unicode(item_name),
                        description=unicode(item_description), category_id=id,
                        user_id=login_session['user_id'])
            session.add(item)
            session.commit()
            return jsonify(item=item.serialize)
        else:
            return jsonify({"error": "No category added"})


@app.route('/catalog/category/<int:id>/items/<int:item_id>',
           methods=['GET', 'POST'])
@ratelimit(limit=30, per=60 * 1)
def itemsCategoryFunction(id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    item = session.query(Items).filter_by(id=item_id, category_id=id).one()
    if request.method == 'GET':
        # return a specific item
        return jsonify(item=item.serialize)

    if request.method == 'PUT':
        # update an item
        item_name = request.args.get('name')
        item_description = request.args.get('description')
        if item_name:
            item.name = item_name
        if item_description:
            item.description = item_description
        session.commit()
        return jsonify(item=item.serialize)

    elif request.method == 'DELETE':
        # delete an item
        session.delte(item)
        session.commit()
        return "Category deleted"


if __name__ == '__main__':
    app.secret_key = 'super_secrete_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
