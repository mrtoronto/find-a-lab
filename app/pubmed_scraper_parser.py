import os
import pandas as pd
from xml.etree.ElementTree import fromstring, ElementTree
import requests
import datetime
import time
import re
from config import Config
from app.util_functions import *

def query_to_paa_index(query, from_year, locations, affils, api_key, timeit_start):
    
    papers_data, count_results = get_article_ids(query, sort = 'relevance', from_year = from_year, 
                    locations = locations, affils = affils,
                    time_start = timeit_start, api_key = api_key)
    if not papers_data:
        return [{'error' : 'No results returned from query. Trying adding more locations, removing locations entirely or broadening your search terms.'}], ''
    
    if papers_data[0].get('error'):
        return [{'error' : papers_data[0].get('error')}], ''

    paper_author_affil_mapping = create_paper_author_affil_index(papers_data=papers_data)

    return papers_data, paper_author_affil_mapping

def other_id_extract(article_id_list, id_type):

    if [ArtID.text for ArtID in article_id_list if ArtID.get('IdType') == id_type]:
        article_id = [ArtID.text for ArtID in article_id_list if ArtID.get('IdType') == id_type][0]
    else:
        article_id = ''
    return article_id


def pubmed_xml_parse(xml_text, locations, affils):
    now = datetime.datetime.now()
    locations_regex = f'({"|".join(locations)})'
    affils_regex = f'({"|".join(affils)})'
    ### Parse XML File using an ElementTree
    root_ab = ElementTree(fromstring(xml_text)).getroot()

    ### These lists will contain lists where each list has data for 1 article
    ### Some will be for their own sheet
    papers = []

    ### For each article in the imported file
    for article in root_ab.findall('./PubmedArticle'):

        ### Author information
        author_list = []
        filter_affils = []
        for author in article.findall('./MedlineCitation/Article/AuthorList/Author'):
            if author.find('Forename'):
                fore_name = author.find('Forename').text
            else:
                fore_name = ''
            if author.find('./CollectiveName'):
                author_text = author.find('./CollectiveName').text
            else:
                try:
                    fore_name = author.findall('ForeName')[0].text
                    initials = author.findall('./Initials')[0].text
                    last_name = author.findall('LastName')[0].text
                    author_text = [fore_name, initials, last_name]
                except:
                    author_text = 'error'

            aff_list = [i.text for i in author.findall('./AffiliationInfo/Affiliation')]
            filter_affils += aff_list
            author_list.append([author_text, aff_list])

        if affils:
            if any([True if re.search(affils_regex, affil.lower()) else False for affil in filter_affils]):
                pass
            else:
                continue

        if locations:
            if any([True if re.search(locations_regex, get_location(affil).lower()) else False for affil in filter_affils]):
                pass
            else:
                continue


        ### Iterate through different parts of the articles
        ### Publication Date
        art_pubdate = ''
        for PubMedPubDate in article.findall('./PubmedData/History/PubMedPubDate'):
            ### Grab data article was published on PubMed
            if PubMedPubDate.get('PubStatus') == 'pubmed':
                art_pubdate = PubMedPubDate.find('./Year').text

        ### Link and PMID
        PMID = article.find('./MedlineCitation/PMID').text
        link_str = 'https://www.ncbi.nlm.nih.gov/pubmed/' + PMID

        ### Article Title
        title_text = ' '.join(article.find('./MedlineCitation/Article/ArticleTitle').itertext())

        ### Publication Types
        pub_type_list = []
        for pubtype in article.findall('./MedlineCitation/Article/PublicationTypeList/PublicationType'):
            pub_type_list.append(pubtype.text)

        ### Journal Information
        journal_list = []
        for journal in article.findall('./MedlineCitation/Article/Journal'):
            try:
                journal_title = journal.find('Title').text
                journal_abbr = journal.find('ISOAbbreviation').text
                journal_issn = journal.find('ISSN').text
                journal_issn_type = journal.find('ISSN').get('IssnType')
                journal_list = [journal_title, journal_issn, journal_issn_type, journal_abbr]
            ### Sometimes there's no ISSN so just in case that's the case :
            except AttributeError:
                journal_list = [journal_title, None, None, journal_abbr]

        ### Abstracts
        abstract_list = {abstract.get('Label', 'Abstract') : abstract.text for abstract in article.findall('./MedlineCitation/Article/Abstract/AbstractText')}

        ### Other keywords attached to the article
        keyword_list = [keyword_elem.text for keyword_elem in article.findall('./MedlineCitation/KeywordList/Keyword')]

        ### Article IDs and information
        article_id_list = article.findall('./PubmedData/ArticleIdList/ArticleId')
        article_doi = other_id_extract(article_id_list, 'doi')
        article_pmc_id = other_id_extract(article_id_list, 'pmc')
        pmc_doi_ids = {'pmc' : article_pmc_id, 'doi' : article_doi}
        
        ### MeSH Headings and Terms
        uni_mesh_dict = {MeshHeading.findall('./DescriptorName')[0].text: \
                        [QualName.text for QualName in MeshHeading.findall('./QualifierName')] \
                        for MeshHeading in article.findall('./MedlineCitation/MeshHeadingList/MeshHeading')}

        ### papers List
        papers.append(
            [title_text, PMID, uni_mesh_dict, pub_type_list, journal_list, author_list, art_pubdate, link_str, pmc_doi_ids, abstract_list])

    ### papers DF creation
    papers_df = pd.DataFrame(papers,
                             columns=['title', 'pmid', 'mesh_keywords', 'pub_type_list', 'journal_info_list', 'author_list', 'pubdate', 'link', 'other_ids', 'abstract'])
    return papers_df

def get_article_ids(query, sort, locations, affils, from_year = "", 
                    api_key="", chunk_size = 5000, time_start=time.time()):
    now = datetime.datetime.now()

    esearch_base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'

    ### More DB options here : https://www.ncbi.nlm.nih.gov/books/NBK3837/
    if from_year:
        reldate = '&reldate=' + str((2021 - int(from_year)) * 365)
    else:
        reldate = ''
    ### Get the webpage with the IDs for the articles you'll want to fetch
    url_search = f"{esearch_base}?db=pubmed&term={query}&usehistory=y&datetype=edat{reldate}"
    docsearch_resp = requests.get(url_search)

    ### Search the results
    root_search = fromstring(docsearch_resp.content)
    QK = "&query_key=" + root_search.find('./QueryKey').text
    WE = "&WebEnv=" + root_search.find('./WebEnv').text
    count_results = int(root_search.find('./Count').text)
    retstarts = list(range(0, count_results, chunk_size))

    response_list = []

    print(f'Query for "{query}" from {from_year} started {round(time.time() - time_start, 4)} seconds ago has {str(count_results)} results. Downloading now.')
    parsed_papers = []

    if count_results > int(Config.MAX_RESULTS):
        papers_result = [{'error' : f"Your query was too large. The results had {count_results} papers and the current max is set to {Config.MAX_RESULTS}. I apologize for this limit. Making websites is harder than you'd think."}]
        return papers_result, 0
    else:
        ### Get Abstracts with efetch
        efetch_base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
        rettype_mode = "&rettype=abstract&retmode=xml"
        retmax_string = "&retmax=" + str(chunk_size)
        for retstart in retstarts:
            url_ab = f"{efetch_base}?db=pubmed{QK}{WE}{rettype_mode}{retmax_string}&retstart={str(retstart)}"
            parsed_papers.append(pubmed_xml_parse(requests.get(url_ab).text, 
                                                locations = locations, affils = affils))

        papers_result = pd.concat(parsed_papers, axis=0, ignore_index=True)
    print(f'Query for "{query}" from {from_year} onward has downloaded and been parsed in {round(time.time() - time_start, 4)} seconds. It was filtered to {count_results} rows.')

    return papers_result.to_dict('records'), count_results


if __name__ == "__main__":
    with open('example.txt') as f:
        f.write(get_article_ids("Thiele EA[Author]", sort = 'relevance', from_year = 2010,
                    api_key="9f66a38099f29d882365afb5ea170b1ef608", time_start = 0))
