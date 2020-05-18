from app.util_functions import *
from app.pubmed_scraper_parser import get_article_ids
from config import Config
import itertools


def query_author_affils_data(query, from_year, locations, n_authors, timeit_start):
    """
    Function provides data for the `query_author_affils()` function which serves the /api/query/author_affils/ endpoint.

    Currently n_authors filters before results are filtered by location so it would be good to swap that.

    Args:

    Returns:
        dataframe - Contains data on author's top affiliations potentially filtered with location 
    """
    response, count_results = get_article_ids(query, sort = 'relevance', from_year = from_year, \
                                api_key="9f66a38099f29d882365afb5ea170b1ef608")
    papers_result = response.to_dict('records')
    if len(papers_result) == 1:
        return papers_result
    if len(papers_result) == 0:
        papers_result = pd.DataFrame([f"Query returned no results after filtering. Try again with less specific query terms. This query had {count_results} results and the current max is set to {Config.MAX_RESULTS}. I apologize for this limit. Making websites is harder than you'd think."])
        return papers_result.to_dict('records')
    print(len(papers_result))
    #affiliations_result = response[1]
    print(f'`author_affils_w_location` for "{query}" from {from_year} has downloaded articles in {round(time.time() - timeit_start, 4)} seconds.')

    authors_affils = create_author_affil_list(papers_result)

    print(f'`author_affils_w_location` for "{query}" from {from_year} has created lists in {round(time.time() - timeit_start, 4)} seconds.')

    affiliations_by_author, top_authors = map_author_to_affil(authors_affils, 
                                    locations_of_interest = locations, n_affiliations = 3)
    print(f'`author_affils_w_location` for "{query}" from {from_year} has mapped affiliations in {round(time.time() - timeit_start, 4)} seconds.')

    author_df = author_affil_total_df(affiliations_by_author, n_authors)

    return author_df


def query_author_papers_data(query, from_year, locations, affils, n_authors, timeit_start, api_key):
    
    response, count_results = get_article_ids(query, sort = 'relevance', from_year = from_year, 
                    locations = locations, affils = affils,
                    time_start = timeit_start, api_key = api_key)
    papers_result = response.to_dict('records')
    if len(papers_result) == 0:
        papers_result = pd.DataFrame([f"Query returned no results after filtering. Try again with less specific query terms. This query had {count_results} results and the current max is set to {Config.MAX_RESULTS}. I apologize for this limit. Making websites is harder than you'd think."])
        return papers_result.to_dict('records')
    ### If query length was > MAX_RESULT setting
    if len(papers_result) == 1:
        return papers_result

    authors_affils = create_author_affil_list(papers_result)
    affiliations_by_author, top_authors, fully_filtered_flag = map_author_to_affil(authors_affils, 
                            locations_of_interest = locations, affils_of_interest = affils, n_affiliations = 5)
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
    paper_top_author_dict = get_top_authors_papers(top_authors, authors_affils, papers_result)

    print(f"Matched papers found in {round(time.time() - timeit_start, 4)} seconds.")

    paper_top_author_df = pd.DataFrame(paper_top_author_dict).T
    affiliations_df = pd.DataFrame([{'author': author_affil_dict['author_string'], 
                                    'pmid' : author_affil_dict['pmid'],
                                    'location' : author_affil_dict['locations'],
                                    'affiliation' : author_affil_dict['affiliations']} for \
                                    author_affil_dict in authors_affils])
    
    locations_regex = f'({"|".join(locations)})'
    affils_regex = f'({"|".join(affils)})'

    big_df = pd.merge(paper_top_author_df, affiliations_df, on = ['author', 'pmid'])
    out_dict = {}
    if affiliations_by_author:
        for author_dict in affiliations_by_author:
            author_papers_df = big_df.loc[big_df['author'] == author_dict['author'], :]
            author_papers_titles_links = big_df.loc[big_df['author'] == author_dict['author'], ['pmid', 'title', 'link']].drop_duplicates()
            author_papers_pmids_keywords = big_df.loc[big_df['author'] == author_dict['author'], ['pmid', 'mesh_keywords']].drop_duplicates(subset=['pmid'])
            author_papers_pmids_pubtypes = big_df.loc[big_df['author'] == author_dict['author'], ['pmid', 'pubtype_list']].drop_duplicates(subset=['pmid'])


            out_author_dict = {'author' : author_dict['author'], 
                            'total_count' : author_dict['total_papers'],
                            'affiliations' : author_dict['affiliations'],
                            'locations' : author_dict['locations']}

            out_author_dict['papers_dict'] = big_df.loc[big_df['author'] == author_dict['author'], :].drop_duplicates(subset=['pmid']).to_dict('records')
            out_author_dict['papers_links'] = author_papers_titles_links.to_dict('records')
            out_author_dict['papers_keywords'] = [paper['mesh_keywords'] for paper in author_papers_pmids_keywords.to_dict('records')]
            out_author_dict['papers_keywords_counts'] = sorted(list(Counter([item for sublist in out_author_dict['papers_keywords'] \
                for item in sublist]).items()), key=lambda x: x[1], reverse=True)

            out_author_dict['papers_pubtypes'] = [paper['pubtype_list'] for paper in author_papers_pmids_pubtypes.to_dict('records')]
            out_author_dict['papers_pubtype_counts'] = sorted(list(Counter([item for sublist in out_author_dict['papers_pubtypes'] \
                for item in sublist]).items()), key=lambda x: x[1], reverse=True)


            out_dict[author_dict['author']] = out_author_dict
    
    elif fully_filtered_flag:
        out_dict = {'error' : 'There were results but they were filtered by your location/affiliation criteria.'}
    
    else:
        out_dict = {'error' : 'no results for this query'}
    
    
    return out_dict