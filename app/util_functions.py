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


def create_author_affil_list(papers_result):
    """
    Create a list of dictionaries where each element represents an author + paper + affiliation combination. 
        - Multi-author papers and multiple affiliation authors will each generate 
            multiple elements for an individual paper in the resulting list

    If any errors, print the error and the author/affiliation to the console and skip. 

    Args:
        papers_result - List: Elements in list are dictionaries of data generated from XML parser
    Returns:
        List: Elements are dictionaries of author-affiliation-paper data points containing individual author-affiliation-pmid combinations.
    """
    author_affils = []
    ### Loop through papers from results
    for paper_dictionary in papers_result:
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


def filter_authors(author_dicts, locations_of_interest, affils_of_interest):
    """
    Given a list of author's affiliations and the user's locations of interest, filter the affiliations
    to only contain locations the user is interested in.
    
    Args:
        author_dicts - 
        locations_of_interest - List: Hardcoded list of interesting locations
    Returns:
        
    """
    kept_authors = []
    ### Loop through authors
    if locations_of_interest or affils_of_interest:
        for author_dict in author_dicts:
            ### Flag to prevent duplicate keeps
            kept_author_flag = False
            if locations_of_interest:
                for author_location in author_dict['locations'].keys():
                    for location_of_interest in locations_of_interest:
                        if re.search(location_of_interest.lower().strip(), author_location.lower().strip()):
                            if kept_author_flag == False:
                                kept_authors.append(author_dict)
                                kept_author_flag = True
                            else:
                                pass

            if affils_of_interest:
                for author_affil in author_dict['affiliations'].keys():
                    for affil_of_interest in affils_of_interest:
                        if re.search(affil_of_interest.lower().strip(), author_affil.lower().strip()):
                            if kept_author_flag == False:
                                kept_authors.append(author_dict)
                                kept_author_flag = True
                            else:
                                pass
    else:
        kept_authors = author_dicts
                    
    return kept_authors

def count_author_affil_locations(author_name, authors_affils, affil_loc, n_affiliations):
    """
    


    Args:

        affil_loc - Str: 'affiliations' or 'locations' to determine which the function is looking at
    """
    ### Create a list of *PMID*__*Location/Affiliation* strings from each author-paper-affiliation data point 
    ### if the data point's author matches `author_name`
    author_affiliations = [paper_author_affil.get('pmid') + '__' + paper_author_affil.get(affil_loc, '') for paper_author_affil in authors_affils \
                                 if paper_author_affil.get('author_string') == author_name]
    
    ### Count up the number of *PMID*__*Location/Affiliation*
    author_affil_counts = Counter(author_affiliations)
    ### Create a dictionary of *Location/Affiliation* : count
    reformatted_affiliations = {affil[0].split('__')[1] : affil[1] for affil in author_affil_counts.most_common(n_affiliations * 3)}
    
    
    return reformatted_affiliations

def count_papers(author_name, authors_affils):
    author_papers = list(set([paper_author_affil.get('pmid') for paper_author_affil in \
        authors_affils if paper_author_affil.get('pmid') and paper_author_affil.get('author_string') == author_name]))
    return len(author_papers)


def map_author_to_affil(authors_affils, locations_of_interest, affils_of_interest, n_affiliations=3):
    """
    Get `n` most common authors, find their top 3 affiliations and their geographic locations. 
    
    Filter list of authors by whether one of their affiliation locations lands in a location_of_interest
    
    Args:
    
    Returns:
        List - List elements are dictionaries containing data on an author's top 3 affiliations 
            if they land in the supplied `locations_of_interest`. 
    """

    author_affil_df = pd.DataFrame(authors_affils)
    top_authors = dict(Counter(author_affil_df['author_string']).most_common(200))
    #Get Affiliations for Top 200 Authors
    author_locs_affils = []
    ### Count up most common authors
    author_list = list(top_authors.keys())

    for author_name in author_list:

        author_locs_affils.append({'author' : author_name, 
                                   'total_papers' : count_papers(author_name, authors_affils),
                                   'locations' : count_author_affil_locations(author_name, authors_affils, 'locations', n_affiliations),
                                   'affiliations' : count_author_affil_locations(author_name, authors_affils, 'affiliations', n_affiliations)
                                   })

    return author_locs_affils, top_authors, False 

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


def get_authors_papers(author_of_interest, authors_affils, papers_result):
    author_pmids = [{'author': author_affil_dict['author_string'], \
                    'pmid' : author_affil_dict['pmid']} for author_affil_dict in authors_affils]

    matching_pmids = []
    ### Find an authors PMIDs
    for author_pmid in author_pmids:
        if author_pmid['author'] == author_of_interest:
            matching_pmids.append(author_pmid['pmid'])

    matching_papers = []
    for paper in papers_result:
        if paper['pmid'] in matching_pmids:
            matching_papers.append(paper)

    matching_papers_df = pd.DataFrame(matching_papers)
    matchedPapers = matching_papers_df#.drop(columns=['pub_type_list', 'journal_info_list', 'author_list', 'keywords'])
    matchedPapers_dicts = matchedPapers.to_dict('records')
        
    return matchedPapers_dicts


def get_top_authors_papers(top_authors, authors_affils, papers_result):
    paper_top_author_dict = {}
    for author_of_interest in top_authors:
        matchedPapers_dicts = get_authors_papers(author_of_interest, authors_affils, papers_result)
        for matchedPaper in matchedPapers_dicts:
            paper_top_author_dict[f"{author_of_interest}_{matchedPaper['pmid']}"] = {
                        'author' : author_of_interest, 
                        'title' : matchedPaper['title'], 
                        'pubdate' : matchedPaper['pubdate'], 
                        'link' : matchedPaper['link'], 
                        'pmid' : matchedPaper['pmid'],
                        'pubtype_list' : ",".join(matchedPaper['pub_type_list']),
                        'all_authors_list' : ",".join([author_affil[0][2] + ', ' + author_affil[0][0] for author_affil in matchedPaper['author_list']]), 
                        'mesh_keywords' : list(matchedPaper['mesh_keywords'].keys()),
                        'other_ids' : ",".join(matchedPaper['other_ids'].values())
                        }

            
    return paper_top_author_dict