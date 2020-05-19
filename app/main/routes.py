
from app import db
from app.main.forms import LoginForm, RegistrationForm, EditProfileForm, \
    ResetPasswordRequestForm, ResetPasswordForm, authorIndexQueryForm
from app.models import User, Query
from app.email import send_password_reset_email
from app.main import bp

from app.main_api_functions import *

from datetime import datetime, timezone
from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from config import Config
from werkzeug.urls import url_parse
import itertools
import re
import ast
import datetime
import pandas as pd
from collections import Counter
from geotext import GeoText
import time


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.datetime.now(timezone.utc)
        db.session.commit()


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
def index():
    return render_template('index.html')



@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()    
    return render_template('user.html', user=user)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)



@bp.route('/query/<query_type>', methods=['GET', 'POST'])
@login_required
def make_a_query(query_type):
    if query_type == 'author_papers':
        form = authorIndexQueryForm()      
    elif query_type == 'affil_papers':
        form = authorIndexQueryForm()

    if form.validate_on_submit() :
        flash('Your query is running!')
        if query_type == 'author_papers':
            author_dicts = query_author_papers(query = form.query_text.data, 
                                                    from_year = form.query_from.data,
                                                    locations = form.locations.data, 
                                                    n_authors = 25, 
                                                    affils = form.affiliations.data, 
                                                    api_key = form.api_key.data,
                                                    api_out = False)
            query = Query(query_type = query_type,
                query_text = form.query_text.data, 
                query_from = form.query_from.data,
                query_affiliations=form.affiliations.data, 
                query_locations=form.locations.data,
                user_querying = current_user.username,
                length_of_results = len(author_dicts.keys()))

            db.session.add(query)
            db.session.commit()
            if author_dicts.get('error'):
                return render_template('errors/data_error.html', data = author_dicts.get('error'), 
                        query_text = query.query_text, query_from = query.query_from , 
                        query_location =  query.query_locations, query_affiliations = query.query_affiliations)
            
            n_results = sum([author_dict['total_count'] for author_dict in author_dicts.values()])
            return render_template('query_results/author_papers.html', data = author_dicts, n_results = n_results)
        elif query_type == 'affil_papers':
            affil_dicts = query_affil_papers(query = form.query_text.data, 
                                            from_year = form.query_from.data,
                                            locations = form.locations.data, 
                                            n_authors = 25, 
                                            affils = form.affiliations.data, 
                                            api_key = form.api_key.data,
                                            api_out = False)
            query = Query(query_type = query_type,
                query_text = form.query_text.data, 
                query_from = form.query_from.data,
                query_affiliations=form.affiliations.data, 
                query_locations=form.locations.data,
                user_querying = current_user.username,
                length_of_results = len(affil_dicts.keys()))

            db.session.add(query)
            db.session.commit()
            if affil_dicts.get('error'):
                return render_template('errors/data_error.html', data = affil_dicts.get('error'), 
                        query_text = query.query_text, query_from = query.query_from , 
                        query_location =  query.query_locations, query_affiliations = query.query_affiliations)
            
            n_results = sum([affil_dicts['total_count'] for affil_dicts in affil_dicts.values()])
            return render_template('query_results/affil_papers.html', data = affil_dicts, n_results = n_results)

    return render_template('make_a_query.html', form=form)



#######


@bp.route('/api/help/', methods = ['GET'])
def help():
    return {'endpoints' : {'/api/query/author_affils/' : {'parameters' : 
                                                {'query' : '', 'from' : '', 'locations' : '', 'n' : ''}, 'info' : ''},
                            '/api/query/author_papers/' : {'parameters' : 
                                                {'query' : '', 'from' : '', 'locations' : '', 'n' : ''}, 'info' : ''}
                        },
            'general_notes' : 'chris smells'}


@bp.route('/api/query/author_papers/', methods = ['GET'])
def query_author_papers(query = "", from_year = "", 
                    locations = "", n_authors = "", 
                    affils = "", api_key = "", api_out = True):

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
    if request.args.get('api_out'):
        api_out = request.args.get('api_out')

    if locations:
        locations = [location.strip().lower() for location in locations.split(',')]

    if affils:
        affils = [affil.strip().lower() for affil in affils.split(',')]

    if not api_key:
        no_key_dict = {'error' : 'Please supply an API key to run your query under!'}
        if api_out == True:
            return jsonify(no_key_dict)
        else:
            return no_key_dict 

    out_dict = query_author_papers_data(query, from_year, locations, affils, n_authors, timeit_start, api_key)

    timeit_end = time.time()
    print(f'`query_author_papers` for "{query}" from {from_year} onward ran in {round(timeit_end - timeit_start,4)} seconds. Returning results.')
    if api_out == True:
        return jsonify(out_dict)
    else:
        return out_dict


@bp.route('/api/query/affil_papers/', methods = ['GET'])
def query_affil_papers(query = "", 
                    from_year = "", 
                    locations = "",
                    n_authors = "",
                    affils = "", 
                    api_key = "",
                    api_out = True):
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

    if not api_key:
        no_key_dict = {'error' : 'Please supply an API key to run your query under!'}
        if api_out == True:
            return jsonify(no_key_dict)
        else:
            return no_key_dict 

    out_dict = query_affil_papers_data(query, from_year, locations, affils, n_authors, timeit_start, api_key)

    timeit_end = time.time()
    #print(f'`author_papers_w_location` for "{query}" from {from_year} onward ran in {round(timeit_end - timeit_start,4)} seconds. Returning results.')
    print(f'`query_affil_papers` for "{query}" from {from_year} onward ran in {round(timeit_end - timeit_start,4)} seconds. Returning results.')
    if api_out == True:
        return jsonify(out_dict)
    else:
        return out_dict