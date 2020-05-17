from app.util_functions import *
from app.pubmed_scraper_parser import get_article_ids
from config import Config


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


def query_author_papers_data(query, from_year, locations, affils, n_authors, timeit_start):
    
    response, count_results = get_article_ids(query, sort = 'relevance', from_year = from_year, 
                    locations = locations, affils = affils,
                    api_key="9f66a38099f29d882365afb5ea170b1ef608", time_start = timeit_start)
    papers_result = response.to_dict('records')
    if len(papers_result) == 0:
        papers_result = pd.DataFrame([f"Query returned no results after filtering. Try again with less specific query terms. This query had {count_results} results and the current max is set to {Config.MAX_RESULTS}. I apologize for this limit. Making websites is harder than you'd think."])
        return papers_result.to_dict('records')
    print(len(papers_result))
    ### If query length was > MAX_RESULT setting
    if len(papers_result) == 1:
        return papers_result

    authors_affils = create_author_affil_list(papers_result)
    affiliations_by_author, top_authors, fully_filtered_flag = map_author_to_affil(authors_affils, 
                            locations_of_interest = locations, affils_of_interest = affils, n_affiliations = 5)
    #Get papers for top 25 authors

    paper_top_author_list = get_top_authors_papers(top_authors, authors_affils, papers_result)

    print(f"Matched papers found in {round(time.time() - timeit_start, 4)} seconds.")

    paper_top_author_df = pd.DataFrame(paper_top_author_list)
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
            if locations:
                n_relevant_papers_loc = len([location for location in author_papers_df['location'] if re.search(locations_regex, location.lower().strip())])
            else:
                n_relevant_papers_loc = 0
            if affils:
                n_relevant_papers_afil = len([affiliation for affiliation in author_papers_df['affiliation'] if re.search(affils_regex, affiliation.lower().strip())])
            else:
                n_relevant_papers_afil = 0

            out_author_dict = {'author' : author_dict['author'], 
                            'total_count' : author_dict['total_papers'],
                            'affiliations' : author_dict['affiliations'],
                            'locations' : author_dict['locations']}
            if not locations and not affils:
                pass
            elif locations and not affils:
                out_author_dict['location_relevant_count'] = n_relevant_papers_loc
                out_author_dict['relevant_locations'] = author_dict['relevant_locations']
            elif affils and not locations:
                out_author_dict['affiliation_relevant_count'] = n_relevant_papers_afil
                out_author_dict['relevant_affiliations'] = author_dict['relevant_affiliations']
            else:
                out_author_dict['affiliation_relevant_count'] = n_relevant_papers_afil
                out_author_dict['location_relevant_count'] = n_relevant_papers_loc
                out_author_dict['relevant_affiliations'] = author_dict['relevant_affiliations']
                out_author_dict['relevant_locations'] = author_dict['relevant_locations']
            out_author_dict['papers_dict'] = big_df.loc[big_df['author'] == author_dict['author'], :].to_dict('records')

            out_dict[author_dict['author']] = out_author_dict
        if locations:
            out_dict = {k:v for (k,v) in sorted(out_dict.items(), key=lambda item: item[1]['location_relevant_count'], reverse=True)}
        elif affils:
            out_dict = {k:v for (k,v) in sorted(out_dict.items(), key=lambda item: item[1]['affiliation_relevant_count'], reverse=True)}
    
    elif fully_filtered_flag:
        out_dict = {'error' : 'There were results but they were filtered by your location/affiliation criteria.'}
    
    else:
        out_dict = {'error' : 'no results for this query'}
    
    
    return out_dict