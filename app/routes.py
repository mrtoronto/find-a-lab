from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from config import Config

from werkzeug.urls import url_parse
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, \
    ResetPasswordRequestForm, ResetPasswordForm, authorIndexQueryForm
from app.models import User, Query
from app.email import send_password_reset_email
import itertools
import re
import ast
import datetime
from datetime import timezone
import pandas as pd
from app import app
from app.main_api_functions import *
from collections import Counter
#from tqdm.notebook import tqdm
from geotext import GeoText
import time

def make_string_from_dict(input_dict):
    output_str = ''
    for item, value in input_dict.items():
        output_str += '{"' + str(item) + '" : "' + str(value) + '"},'
    output_str = output_str[:-1]
    return output_str

def make_string_from_dict2(input_dict):
    output_str = ''
    for item, value in input_dict.items():
        output_str += str(item) + ' : ' + str(value) + '\n'
    output_str = output_str[:-1]
    return output_str

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.datetime.now(timezone.utc)
        db.session.commit()


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()    
    return render_template('user.html', user=user)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)



@app.route('/query/<query_type>', methods=['GET', 'POST'])
@login_required
def make_a_query(query_type):
    if query_type == 'author_papers':
        form = authorIndexQueryForm()      
    elif query_type == 'author_affils':
        form = authorIndexQueryForm()      

    if form.validate_on_submit() and current_user.is_authenticated:
        query = Query(query_type = query_type,
                    query_text = form.query_text.data, 
                    query_from = form.query_from.data,
                    query_affiliations=form.affiliations.data, 
                    query_locations=form.locations.data,
                    user_querying = current_user.username)

        db.session.add(query)
        db.session.commit()
        flash('Your query is running!')
        results = query_author_papers(query = query.query_text, 
                                                from_year = query.query_from,
                                                locations = query.query_locations, 
                                                n_authors = 25, 
                                                affils = query.query_affiliations, 
                                                api_key = form.api_key.data)
        author_keywords = {author : author_dict['papers_keywords_counts'] for author, author_dict in results.items()}
        return render_template('query_results.html', json_data = results)

    return render_template('make_a_query.html', form=form)



#######


@app.route('/api/help/', methods = ['GET'])
def help():
    return {'endpoints' : {'/api/query/author_affils/' : {'parameters' : 
                                                {'query' : '', 'from' : '', 'locations' : '', 'n' : ''}, 'info' : ''},
                            '/api/query/author_papers/' : {'parameters' : 
                                                {'query' : '', 'from' : '', 'locations' : '', 'n' : ''}, 'info' : ''}
                        },
            'general_notes' : 'chris smells'}


@app.route('/api/query/author_affils/', methods = ['GET'])
def query_author_affils():

    timeit_start = time.time()

    query = request.args.get('query')
    from_year = int(request.args.get('from'))
    locations = request.args.get('locations')
    n_authors = request.args.get('n') or 25
    if locations:
        locations = [location.strip() for location in locations.split(',')]
    else:
        locations = None

    author_df = query_author_affils_data(query, from_year, locations, n_authors, timeit_start)

    if len(author_df) == 0:
        abort(404)
    
    timeit_end = time.time()
    app.logger.info(f'`author_affils_w_location` for "{query}" from {from_year} onward ran in {round(timeit_end - timeit_start, 4)} seconds. Returning results.')
    #print(f'`author_affils_w_location` for "{query}" from {from_year} onward ran in {round(timeit_end - timeit_start, 4)} seconds. Returning results.')

    return jsonify(author_df.to_dict('records'))


@app.route('/api/query/author_papers/', methods = ['GET'])

def query_author_papers(query = "", from_year = "", locations = "", n_authors = "", affils = "", api_key = ""):

    timeit_start = time.time()
    if request.args.get('query'): 
        query = request.args.get('query')
    if request.args.get('from'):
        from_year = int(request.args.get('from', 2000))
    if request.args.get('locations'):    
        locations = request.args.get('locations', [])
    if request.args.get('n', 25):
        n_authors = request.args.get('n', 25)
    if request.args.get('affiliations', []):
        affils = request.args.get('affiliations', [])
    if request.args.get('api_key'):
        api_key = request.args.get('api_key')

    if locations:
        locations = [location.strip().lower() for location in locations.split(',')]

    if affils:
        affils = [affil.strip().lower() for affil in affils.split(',')]

    out_dict = query_author_papers_data(query, from_year, locations, affils, n_authors, timeit_start, api_key)

    timeit_end = time.time()
    #print(f'`author_papers_w_location` for "{query}" from {from_year} onward ran in {round(timeit_end - timeit_start,4)} seconds. Returning results.')
    app.logger.info(f'`author_papers_w_location` for "{query}" from {from_year} onward ran in {round(timeit_end - timeit_start,4)} seconds. Returning results.')
    return out_dict