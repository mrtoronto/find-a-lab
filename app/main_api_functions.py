from app.util_functions import *
from app.pubmed_scraper_parser import get_article_ids, query_to_paa_index
from config import Config
from flask import jsonify
import itertools


def query_author_papers_data(query, from_year, locations, affils, n_authors, timeit_start, api_key):
    
    papers_data, paper_author_affil_mapping = query_to_paa_index(query = query, from_year = from_year, 
                                                    locations = locations, affils = affils,
                                                    api_key = api_key, timeit_start=timeit_start)

    if papers_data[0].get('error'):
        return papers_data[0]

    affiliations_by_author, top_authors = group_papers_by_top_obj(paa_cross_mapping=paper_author_affil_mapping, 
                                                                n_affiliations = 5, obj_key = 'author_string')
    """
    Get papers for top 25 authors
    Each element of contained in `paper_top_author_dict` looks like :
    {author_of_interest : {
        'author' : author_of_interest, 
        'title' : matchedPaper['title'], 
        'pubdate' : matchedPaper['pubdate'], 
        'link' : matchedPaper['link'], 
        'pmid' : matchedPaper['pmid'],
        'pubtype_list' : ",".join(matchedPaper['pub_type_list']),
        'all_authors_list' : ",".join([author_affil[0][2] + ', ' + author_affil[0][0] for author_affil in matchedPaper['author_list']]), 
        'mesh_keywords' : list(matchedPaper['mesh_keywords'].keys()),
        'other_ids' : ",".join(matchedPaper['other_ids'].values())}
    }
    """
    paper_top_author_dict = get_top_obj_papers(top_objs = top_authors, obj_key = 'author_string',
                            authors_affils=paper_author_affil_mapping, papers_data=papers_data)

    print(f"Matched papers found in {round(time.time() - timeit_start, 4)} seconds.")

    paper_top_author_df = pd.DataFrame(paper_top_author_dict).T
    affiliations_df = pd.DataFrame([{'author': author_affil_dict['author_string'], 
                                    'pmid' : author_affil_dict['pmid'],
                                    'location' : author_affil_dict['locations'],
                                    'affiliation' : author_affil_dict['affiliations']} for \
                                    author_affil_dict in paper_author_affil_mapping])
    

    big_df = pd.merge(paper_top_author_df, affiliations_df, left_on = ['join_obj', 'pmid'], right_on = ['author', 'pmid'])#.drop('join_obj', index=1)
    out_dict = create_out_dict_obj_index(affiliations_by_author, big_df, 'author')    
    return out_dict


def query_affil_papers_data(query, from_year, locations, affils, n_authors, timeit_start, api_key):

    
    """
    `paper_author_affil_mapping` looks like:
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
    """
    papers_data, paper_author_affil_mapping = query_to_paa_index(query = query, from_year = from_year, 
                                                locations = locations, affils = affils,
                                                api_key = api_key, timeit_start=timeit_start)
    if papers_data[0].get('error'):
        return papers_data[0]
    """
    `affil_authors` looks like :
    {'affiliation' : affil, 
       'total_papers' : count_papers(affil, authors_affils, 'affiliations'),
       'authors' : count_author_affil_locations(
                            matching_value=affil, 
                            papers_data=authors_affils, 
                            pmid_suffix='author_string', 
                            n_affiliations=n_affiliations, 
                            matching_key='affiliations')
                           }
    """
    print(f"PAA Mapping made in {round(time.time() - timeit_start, 4)} seconds.")
    affil_authors, top_affil_list = group_papers_by_top_obj(
                                    paa_cross_mapping = paper_author_affil_mapping, 
                                    n_affiliations = 5, obj_key = 'affiliations')
    print(f"Top affiliations found in {round(time.time() - timeit_start, 4)} seconds.")
    """
    Get papers for top 25 authors
    Each element of contained in `paper_top_author_dict` looks like :
    {author_of_interest : {
        'author' : author_of_interest, 
        'title' : matchedPaper['title'], 
        'pubdate' : matchedPaper['pubdate'], 
        'link' : matchedPaper['link'], 
        'pmid' : matchedPaper['pmid'],
        'pubtype_list' : ",".join(matchedPaper['pub_type_list']),
        'all_authors_list' : ",".join([author_affil[0][2] + ', ' + author_affil[0][0] for author_affil in matchedPaper['author_list']]), 
        'mesh_keywords' : list(matchedPaper['mesh_keywords'].keys()),
        'other_ids' : ",".join(matchedPaper['other_ids'].values())}
    }
    """
    paper_top_obj_dict = get_top_obj_papers(top_objs = top_affil_list, obj_key = 'affiliations',
                                    authors_affils=paper_author_affil_mapping, papers_data=papers_data)
    print(f"Matched papers found in {round(time.time() - timeit_start, 4)} seconds.")

    paper_top_obj_df = pd.DataFrame(paper_top_obj_dict).T
    df_to_match = pd.DataFrame([{'affiliation' : author_affil_dict['affiliations'], 
                                'proc_Affiliation' : preprocess(author_affil_dict['affiliations']),
                                    'pmid' : author_affil_dict['pmid'],
                                    'author': author_affil_dict['author_string']} for \
                                    author_affil_dict in paper_author_affil_mapping])
    big_df = pd.merge(paper_top_obj_df, df_to_match, 
        left_on = ['join_obj', 'pmid'], right_on = ['proc_Affiliation', 'pmid']).drop(['join_obj'], axis=1)
    
    out_dict = create_out_dict_obj_index(affil_authors, big_df, 'affiliations')
    
    
    return out_dict