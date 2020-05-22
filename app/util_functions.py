import os
import pandas as pd
from xml.etree.ElementTree import fromstring, ElementTree
import requests
import datetime
from collections import Counter
from geotext import GeoText
import time
import re
import itertools

def preprocess(text):
    if text:
        text = re.sub('[,\.\d]', '', text.lower().strip())
        text = re.sub(' +', ' ', text.lower().strip())
    return text

def get_location(affiliation):
    """
    Function takes an affiliation string and attempts to extract a location. 

    If multiple cities are extracted, all will be included in the final location.

    If no countries are found, leave it blank.

    Args:
        affiliation - Str: 
    Returns:
        Str: geotext's attempt to extract `City, Country` from affiliation

    """
    places = GeoText(affiliation)
    if places:
        city_str = ' '.join(set([city for city in places.cities if city != 'University'])).strip()
        if len(places.countries) == 0:
            country_str = ''
        else:
            country_str = places.countries[0]
        locations = f"{city_str}, {country_str}"
    else:
        locations = ''
    return locations


def create_paper_author_affil_index(papers_data):
    """
    Create a list of dictionaries where each element represents an author + paper + affiliation combination. 
        - Multi-author papers and multiple affiliation authors will each generate 
            multiple elements for an individual paper in the resulting list

    If any errors, print the error and the author/affiliation to the console and skip. 

    Args:
        papers_data - List: Elements in list are dictionaries of data generated from XML parser
    Returns:
        List: Elements are dictionaries of author-affiliation-paper data points containing individual author-affiliation-pmid combinations.
    """
    author_affils = []
    ### Loop through papers from results
    for paper_dictionary in papers_data:
        ### Loop through paper's authors
        for author in paper_dictionary['author_list']:
            ### Loop through author's affiliations
            for author_affil in author[1]:
                try:
                    author_affils.append({'author_list' : author[0], 
                                    'author_string' : author[0][2] + ", " + author[0][0],
                                    'affiliations' : author_affil, 
                                    'locations' : get_location(author_affil), 
                                    'title' : paper_dictionary['title'],
                                    'pmid' : paper_dictionary['pmid']
                                   })             
                except Exception as err:
                    print(f"Error making authors entry with {author} and {affil} // {get_location(affil)} \n{err}")
                    pass
    return author_affils


def count_obj_occurance(matching_value, obj_key, paa_cross_mapping, pmid_suffix, n_affiliations):
    """
    


    Args:

        affil_loc - Str: 'affiliations' or 'locations' to determine which the function is looking at
    """
    ### Create a list of *PMID*__*Location/Affiliation* strings from each author-paper-affiliation data point 
    ### if the data point's author matches `author_name`
    if obj_key == 'affiliations' and obj_key == 'affiliations':
        author_affiliations = [paper_data.get('pmid') + '__' + paper_data.get(pmid_suffix, '') for paper_data in paa_cross_mapping \
                                 if preprocess(paper_data.get(obj_key)) == matching_value]
    else:
        author_affiliations = [paper_data.get('pmid') + '__' + paper_data.get(pmid_suffix, '') for paper_data in paa_cross_mapping \
                                 if paper_data.get(obj_key) == matching_value]
    
    ### Count up the number of *PMID*__*Location/Affiliation*
    author_affil_counts = Counter(author_affiliations)
    ### Create a dictionary of *Location/Affiliation* : count
    reformatted_affiliations = {}
    for pmid_affil, affil_count in author_affil_counts.most_common(n_affiliations * 3):
        loop_pmid = pmid_affil.split('__')[0]
        loop_affil = pmid_affil.split('__')[1]

        if reformatted_affiliations.get(loop_pmid):
            if reformatted_affiliations[loop_pmid].get(loop_affil):
                reformatted_affiliations[loop_pmid][loop_affil] += affil_count
            else:
                reformatted_affiliations[loop_pmid][loop_affil] = affil_count
        else:
            reformatted_affiliations[loop_pmid] = {}
            reformatted_affiliations[loop_pmid][loop_affil] = affil_count
    
    return reformatted_affiliations

def count_papers(matching_value, papers_data, matching_field):
    author_papers = list(set([paper_data.get('pmid') for paper_data in \
        papers_data if paper_data.get('pmid') and preprocess(paper_data.get(matching_field)) == matching_value]))
    return len(author_papers)


def map_author_to_affil(papers_data, n_affiliations=3):
    """
    Get `n` most common authors, find their top 3 affiliations and their geographic locations. 
    
    Filter list of authors by whether one of their affiliation locations lands in a location_of_interest
    
    Args:
        author_affils - List: Looks like;
            [
                {
                'author_list' : author[0], 
                'author_string' : author[0][2] + ", " + author[0][0],
                'affiliations' : author_affil, 
                'locations' : get_location(author_affil), 
                'title' : paper_dictionary['title'],
                'pmid' : paper_dictionary['pmid']
                }
            ]
    
    Returns:
        List - List elements are dictionaries containing data on an author's top 3 affiliations 
            if they land in the supplied `locations_of_interest`. 
    """

    papers_df = pd.DataFrame(papers_data)
    top_authors = dict(Counter(papers_df['author_string']).most_common(200))
    #Get Affiliations for Top 200 Authors
    author_locs_affils = []
    ### Count up most common authors
    author_list = list(top_authors.keys())

    for author_name in author_list:

        author_locs_affils.append({'author' : author_name, 
                                   'total_papers' : count_papers(author_name, papers_data, 'author_string'),
                                   'locations' : count_obj_occurance(
                                                matching_value=author_name, 
                                                papers_data=papers_data, 
                                                pmid_suffix='locations', 
                                                n_affiliations=n_affiliations, 
                                                obj_key='author_string'),
                                   'affiliations' : count_obj_occurance(
                                                matching_value=author_name, 
                                                papers_data=papers_data, 
                                                pmid_suffix='affiliations', 
                                                n_affiliations=n_affiliations, 
                                                obj_key='author_string')
                                   })

    return author_locs_affils, top_authors 

def group_papers_by_top_obj(paa_cross_mapping, obj_key, n_affiliations=3):
    """
    Get `n` most common authors, find their top 3 affiliations and their geographic locations. 
    
    Filter list of authors by whether one of their affiliation locations lands in a location_of_interest
    
    Args:
        author_affils - List: Looks like;
            [
                {
                'author_list' : author[0], 
                'author_string' : author[0][2] + ", " + author[0][0],
                'affiliations' : author_affil, 
                'locations' : get_location(author_affil), 
                'title' : paper_dictionary['title'],
                'pmid' : paper_dictionary['pmid']
                }
            ]
        Options for obj_key are: `affiliations` or ...
    Returns:
        List - List elements are dictionaries containing data on an author's top 3 affiliations 
            if they land in the supplied `locations_of_interest`. 
    """

    obj_list = pd.DataFrame(paa_cross_mapping)[obj_key]
    if obj_key == 'affiliations':
        obj_list = [preprocess(affil) for affil in obj_list]
    top_objs = dict(Counter(obj_list).most_common(200))
    #Get Affiliations for Top 200 Authors
    out_list = []
    ### Count up most common authors
    top_obj_list = list(top_objs.keys())


    for affil in top_obj_list:
        obj_dict = {}
        if obj_key == 'affiliations':
            obj_dict = {'proc_Affiliation' : affil, 
               'total_papers' : count_papers(affil, paa_cross_mapping, 'affiliations'),
               'authors' : count_obj_occurance(
                            matching_value=affil, 
                            paa_cross_mapping=paa_cross_mapping, 
                            pmid_suffix='author_string', 
                            n_affiliations=n_affiliations, 
                            obj_key='affiliations'),
               'raw_affiliations' : count_obj_occurance(
                            matching_value=affil, 
                            paa_cross_mapping=paa_cross_mapping, 
                            pmid_suffix='affiliations', 
                            n_affiliations=n_affiliations, 
                            obj_key='affiliations')}

        elif obj_key == 'author_string':
            obj_dict = {'author' : author_name, 
                        'total_papers' : count_papers(author_name, paa_cross_mapping, 'author_string'),
                        'locations' : count_obj_occurance(
                            matching_value=author_name, 
                            paa_cross_mapping=paa_cross_mapping, 
                            pmid_suffix='locations', 
                            n_affiliations=n_affiliations, 
                            obj_key='author_string'),
                        'affiliations' : count_obj_occurance(
                            matching_value=author_name, 
                            paa_cross_mapping=paa_cross_mapping, 
                            pmid_suffix='affiliations', 
                            n_affiliations=n_affiliations, 
                            obj_key='author_string')
                        }

        out_list.append(obj_dict)

    return out_list, top_obj_list 

def author_affil_total_df(affiliations_by_author, n_authors=25):
    """
    Combines data from previous steps to generate a dataframe of top publishing authors and their most frequently
    cited affiliations.
    """
    #Get top 25 from remaining authors
    affiliations_by_author_df = pd.DataFrame(affiliations_by_author)

    ### affiliations_by_author_df['totalPapers'] = affiliations_by_author_df['author'].map(top_authors)
    ### Removed because occasionally totalPapers was < sum of counts of topAffiliations which seems like a no-no
    ### `total_papers` is calculated in the `map_author_to_affil()` function and is calculated before 
    ### undesirable locations are filtered out
    affiliations_by_author_df['totalPapers'] = affiliations_by_author_df['total_papers']

    paper_counts_affiliations = affiliations_by_author_df.to_dict('records')

    flat_dict = []
    for author in paper_counts_affiliations:
        topAffiliations = []
        topAffiliations = {affiliation['affiliation'] : str(affiliation['count']) for affiliation in \
                           author['affiliations']}
        
        flat_dict.append({'author' : author['author'],
                          'topAffiliations' : topAffiliations,
                          'totalPapers' : author['totalPapers']})

    out_df = pd.DataFrame(flat_dict).sort_values(by='totalPapers', ascending=False).reset_index(drop=True)
    return out_df.head(n_authors)


def get_obj_papers(obj_of_interest, obj_key, authors_affils, papers_data):
    if obj_key == 'affiliations':
        obj_pmids = [{obj_key: preprocess(author_affil_dict.get(obj_key)), \
                    'pmid' : author_affil_dict['pmid']} for author_affil_dict in authors_affils]

    else:
        obj_pmids = [{obj_key: author_affil_dict.get(obj_key), \
                    'pmid' : author_affil_dict['pmid']} for author_affil_dict in authors_affils]
    matching_pmids = []
    ### Find an authors PMIDs
    for author_pmid in obj_pmids:
        if author_pmid[obj_key] == obj_of_interest:
            matching_pmids.append(author_pmid['pmid'])
    matching_papers = []
    for paper in papers_data:
        if paper['pmid'] in matching_pmids:
            matching_papers.append(paper)

    matching_papers_df = pd.DataFrame(matching_papers)
    matchedPapers = matching_papers_df#.drop(columns=['pub_type_list', 'journal_info_list', 'author_list', 'keywords'])
    matchedPapers_dicts = matchedPapers.to_dict('records')
        
    return matchedPapers_dicts


def get_top_obj_papers(top_objs, authors_affils, papers_data, obj_key):
    top_obj_papers = {}
    for obj_of_interest in top_objs:
        raw_obj_of_interest = obj_of_interest
        if obj_key == 'affiliations':
            obj_of_interest = preprocess(obj_of_interest)
        matchedPapers_dicts = get_obj_papers(obj_of_interest=obj_of_interest, obj_key = obj_key, 
                                            authors_affils=authors_affils, papers_data=papers_data)
        for matchedPaper in matchedPapers_dicts:
            top_obj_papers[f"{obj_of_interest}_{matchedPaper['pmid']}"] = {
                        'join_obj' : obj_of_interest, 
                        'raw_join_obj' : raw_obj_of_interest,
                        'title' : matchedPaper['title'], 
                        'pubdate' : matchedPaper['pubdate'], 
                        'link' : matchedPaper['link'], 
                        'pmid' : matchedPaper['pmid'],
                        'pubtype_list' : list(matchedPaper['pub_type_list']),
                        'all_authors_list' : ",".join([author_affil[0][2] + ', ' + author_affil[0][0] for author_affil in matchedPaper['author_list']]), 
                        'mesh_keywords' : list(matchedPaper['mesh_keywords'].keys()),
                        'other_ids' : ",".join(matchedPaper['other_ids'].values())
                        }

            
    return top_obj_papers