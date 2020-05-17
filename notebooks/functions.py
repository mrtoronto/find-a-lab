import os
import pandas as pd
from xml.etree.ElementTree import fromstring, ElementTree
import requests
import datetime
from tqdm.notebook import tqdm


def pubmed_xml_parse(filename):
    now = datetime.datetime.now()

    ### Parse XML File using an ElementTree
    tree_ab = ElementTree(fromstring(filename))
    root_ab = tree_ab.getroot()

    ### These lists will contain lists where each list has data for 1 article
    ### Some will be for their own sheet
    papers_df = []
    pub_type_df_list = []
    abstract_df_list = []
    artID_df_list = []
    keyword_df_list = []
    author_df_list = []
    mesh_df_list = []
    affiliation_df_list = []
    journal_list_df = []

    ### For each article in the imported file
    for article in root_ab.findall('./PubmedArticle'):

        ### These will be used to make a row in the `papers_df`
        uni_mesh_dict = {}
        keyword_list = []
        artID_list = []
        abstract_list = []
        journal_list = []
        pub_type_list = []
        author_list = []
        affiliation_list = []

        ### Iterate through different parts of the articles
        ### Publication Date
        for PubMedPubDate in article.findall('./PubmedData/History/PubMedPubDate'):
            ### Grab data article was published on PubMed
            if PubMedPubDate.get('PubStatus') == 'pubmed':
                year = PubMedPubDate.findall('./Year')[0].text
        art_pubdate = year

        ### Link and PMID
        PMID = article.find('./MedlineCitation/PMID').text
        link_str = 'https://www.ncbi.nlm.nih.gov/pubmed/' + PMID

        ### Article Title
        for title in article.findall('./MedlineCitation/Article/ArticleTitle'):
            title_text = ' '.join(title.itertext())

        ### Publication Types
        for type in article.findall('./MedlineCitation/Article/PublicationTypeList/PublicationType'):
            pub_type_list.append(type.text)
            pub_type_df_list.append([PMID, title_text, type.text])

        ### Journal Information
        for journal in article.findall('./MedlineCitation/Article/Journal'):
            try:
                journal_title = journal.find('Title').text
                journal_abbr = journal.find('ISOAbbreviation').text
                journal_issn = journal.find('ISSN').text
                journal_issn_type = journal.find('ISSN').get('IssnType')
                journal_list = [journal_title, journal_issn, journal_issn_type, journal_abbr]
                journal_list_df.append([PMID, journal_title, journal_issn, journal_issn_type, journal_abbr])
            ### Sometimes there's no ISSN so just in case that's the case :
            except AttributeError:
                journal_list = [journal_title, None, None, journal_abbr]
                journal_list_df.append([PMID, journal_title, None, None, journal_abbr])

        ### Abstracts
        for abstract in article.findall('./MedlineCitation/Article/Abstract/AbstractText'):
            abstract_type = abstract.get('Label')
            if abstract_type == None:
                abstract_type = 'No Abstract Type Label'
            abstract_text = abstract.text
            abstract_list.append(abstract_text)
            abstract_df_list.append([PMID, title_text, abstract_type, abstract_text])

        ### Other keywords attached to the article
        for keyword_elem in article.findall('./MedlineCitation/KeywordList/Keyword'):
            keyword = keyword_elem.text
            keyword_signif = keyword_elem.get('MajorTopicYN')
            keyword_list.append(keyword)
        keyword_df_list.append([PMID, title_text, keyword_list])

        ### Author information
        for author in article.findall('./MedlineCitation/Article/AuthorList/Author'):
            try:
                try:
                    fore_name = author.findall('ForeName')[0].text
                    initials = author.findall('./Initials')[0].text
                    last_name = author.findall('LastName')[0].text
                    affiliation = author.findall('./AffiliationInfo/Affiliation')
                    aff_list = []
                    for i in affiliation:
                        aff_list.append(i.text)
                    #author_text = fore_name + initials + ", " + last_name
                    author_text = [fore_name, initials, last_name]
                except:
                    initials = author.findall('./Initials')[0].text
                    last_name = author.findall('LastName')[0].text
                    affiliation = author.findall('./AffiliationInfo/Affiliation')
                    aff_list = []
                    for i in affiliation:
                        aff_list.append(i.text)
                    #author_text = initials + ", " + last_name
                    author_text = [initials, last_name]
            except:
                try:
                    author_text = author.findall('./CollectiveName')[0].text
                except:
                    author_text = 'error'
            author_list.append(author_text)
            affiliation_list.append([author_text, aff_list, PMID])
            author_df_list.append([PMID, title_text, art_pubdate, author_text])
            affiliation_df_list.append([author_text, aff_list, PMID])

        ### Article IDs and information
        for ArtID in article.findall('./PubmedData/ArticleIdList/ArticleId'):
            ArtID_text = ArtID.text
            ArtID_type = ArtID.get('IdType')
            if ArtID_type != 'pubmed':
                artID_list.append([ArtID_type, ArtID_text])
                artID_df_list.append([PMID, title_text, ArtID_type, ArtID_text])
            else:
                continue

        ### MeSH Headings and Terms
        for MeshHeading in article.findall('./MedlineCitation/MeshHeadingList/MeshHeading'):
            DescName = MeshHeading.findall('./DescriptorName')[0].text
            mesh_df_list.append([PMID, title_text, '-', DescName])
            QualName_list = []
            for QualName in MeshHeading.findall('./QualifierName'):
                QualName_list.append(QualName.text)
                mesh_df_list.append([PMID, title_text, QualName.text, DescName])
            uni_mesh_dict.update({DescName: QualName_list})

        ### papers List
        papers_df.append(
            [title_text, PMID, keyword_list, pub_type_list, journal_list, author_list, aff_list, art_pubdate, link_str, abstract_list])

    ### papers DF creation
    papers_df = pd.DataFrame(papers_df,
                             columns=['title', 'pmid', 'keywords', 'pub_type_list', 'journal_info_list', 'author_list', 'affil_list', 'pubdate', 'link', 'abstract'])

    return [papers_df, affiliation_df_list]

def get_article_ids(query, sort, from_year = "", api_key="", chunk_size = 5000):
    now = datetime.datetime.now()

    if os.path.isdir("output") == False:
        os.mkdir('output')
    if os.path.isdir("output/xml") == False:
        os.mkdir('output/xml')

    print('Query:' + query)

    esearch_base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'

    ### More DB options here : https://www.ncbi.nlm.nih.gov/books/NBK3837/
    if from_year:
        reldate = '&reldate=' + str((2021 - from_year) * 365)
    else:
        reldate = ''
    ### Get the webpage with the IDs for the articles you'll want to fetch
    url_search = f"{esearch_base}?db=pubmed&term={query}&usehistory=y&datetype=edat{reldate}"
    docsearch_resp = requests.get(url_search)

    ### Search the results
    root_search = fromstring(docsearch_resp.content)
    QK = "&query_key=" + root_search.findall('./QueryKey')[0].text
    WE = "&WebEnv=" + root_search.findall('./WebEnv')[0].text
    count_results = int(root_search.findall('./Count')[0].text)
    print('Number of Results: ' + str(count_results))
    retstarts = list(range(0, count_results, chunk_size))

    response_list = []

    for retstart in retstarts:
        ### Get Abstracts with efetch
        efetch_base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
        rettype_mode = "&rettype=abstract&retmode=xml"
        retstart_string = "&retstart=" + str(retstart)
        retmax_string = "&retmax=" + str(chunk_size)

        url_ab = efetch_base + '?db=pubmed' + QK + WE + rettype_mode + retmax_string + retstart_string
        url_ab = f"{efetch_base}?db=pubmed{QK}{WE}{rettype_mode}{retmax_string}{retstart_string}"
        docsab_resp = requests.get(url_ab)
        response_list.append(docsab_resp.text)

    parsed_papers = []
    parsed_authors = []

    for response in response_list:
        parsed = pubmed_xml_parse(response)
        parsed_papers.append(parsed[0])
        for author_pair in parsed[1]:
            parsed_authors.append({'author': author_pair[0], 'affiliation': author_pair[1], 'pmid' :
                                   author_pair[2]})

    papers_result = pd.concat(parsed_papers, axis=0, ignore_index=True)

    return [papers_result, parsed_authors]