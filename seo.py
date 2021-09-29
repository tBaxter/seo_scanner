import csv
import requests
import re
import sys

from http import HTTPStatus

from bs4 import BeautifulSoup
from builtwith import builtwith

from sitemap import scan as sitemap_scan

"""
Fairly simple scanner that makes a few checks for SEO and
search indexing readiness.
It first runs the sitemap scanner to capture the presence of
(and key contents of) sitemap.xml and robots.txt files.
then runs additional SEO checks to determine:

* What platform does the site run on
# Does a sitemap.xml exist?
# How many of the total URLs are in the sitemap
# How many PDFs are in the sitemap?
# How many URLs are there total
# Does a Robots.txt exist
# Crawl delay? (number)
# Est hours to index (crawl delay x #number of URLs)
# Does a Main element exist
# Does OG Date metadata exist
# Are Title tags unique
# Are meta descriptions unique

Further, by comparing the site root with a second page (/privacy) it
will compare the two pages to determine if the title and descriptions
appear to be unique.

Possible future scope:
* expanded checking (grab some set of URLs from Nav and look at them, too)

"""

# This is the list of pages that we will be checking.
pages = [
    "/",
    "/privacy",
]

# this will be populated by our scans, and also form our CSV headers.
# Note that you need to call this again to empty it out for each scan.
scan_data = {
    'Platforms': None,
    'Sitemap status code': None,
    'Sitemap final url': None,
    'Sitemap items': 0,
    'PDFs in sitemap': 0,
    'Sitemaps from index': [],
    'Robots.txt': None,
    'Crawl delay': None,
    'Sitemaps from robots': [],
    'Total URLs': 0,
    'Est time to index': 'Unknown',
    'Main tags found': None,
    'Search found': None,
    'Pages': None,
    'Warnings': None
}
# now add in the pages we plan to check
for page in pages:
    scan_data[page] = None


def sitemap_scan(fqd, results):
    """
    Looks at sitemap-related items for SEO.
    1. Is the sitemap findable?
    2. Where?
    3. Can we see the items in it?
    4. How many are PDFs?
    5. Can we find and retrieve robots.txt?
    6. Can we find a crawl delay defined?
    7. Are additional sitemaps defined in robots.txt?
    8. Can we retrieve those?
    9. How many URLs did we find altogether?
    10. Given a crawl delay, how long should it take to crawl?
    """
    print("Sitemap scan called for %s" % fqd)
    # get status_code and final_url for sitemap.xml
    try:
        sitemap = requests.get(fqd + '/sitemap.xml', timeout=4)
        results['status_code'] = sitemap.status_code
        results['final_url'] = sitemap.url
    except Exception as error:
        error_str = "Could not get data from %s/sitemap.xml: %s" % (fqd, error)
        print(error_str)
        results['status_code'] = error_str

    # Check once more that we have a usable sitemap before parsing it
    if sitemap and sitemap.status_code == HTTPStatus.OK:
        print("Examining sitemap...")
        soup = BeautifulSoup(sitemap.text, 'lxml')
        urls = soup.find_all('url')
        url_count = len(urls)
        results['url_tag_count'] = url_count if url_count else 0

        # and how many of those URLs appear to be PDFs
        if urls:
            results['pdfs_in_urls'] = len([u for u in urls if '.pdf' in u.get_text()])
        # And check if it's a sitemap index
        if soup.find('sitemapindex'):
            results['sitemap_locations_from_index'] = [loc.text for loc in soup.select("sitemap > loc")]

    # Now search robots.txt for crawl delay and sitemap locations
    # when we have Python 3.8 RobotFileParser may be a better option than regex for this.
    # But it can be kinda funky, too.
    print("Accessing robots.txt")
    try:
        robots = requests.get(fqd + '/sitemap.xml', timeout=4)
        if robots and robots.status_code == HTTPStatus.OK:
            results['robots'] = 'OK'
            # now read it. Note we have seen cases where a site is defining
            # crawl delay more than once or are declaring different crawl
            # delays per user agent. We are only grabbing the first instance.
            # Subsequent declarations are ignored. This could lead to incorrect
            # results and should be double-checked if the crawl delay is particularly
            # critical to you. For our purposes, simply grabbing the first is Good Enough.
            cd = re.findall('[cC]rawl-[dD]elay: (.*)', robots.text)
            if cd:
                results['crawl_delay'] = cd[0]
            results['sitemap_locations_from_robotstxt'] = re.findall('[sS]itemap: (.*)', robots.text)
        else:
            results['robots'] = robots.status_code
    except Exception as error:
        print("Error parsing robots.txt for %s: %s" % (fqd, error))

    # If we found additional sitemaps in a sitemap index or in robots.txt, we
    # need to go look at them and update our url total.
    print("Checking for additional sitemaps...")
    additional_urls = 0
    for loc in results['sitemap_locations_from_index']:
        if loc != results['final_url']:
            #print("checking %s" % loc)
            sitemap = requests.get(loc)
            if sitemap.status_code == HTTPStatus.OK:
                soup = BeautifulSoup(sitemap.text, 'xml')
                additional_urls += len(soup.find_all('url'))

    for loc in results['sitemap_locations_from_robotstxt']:
        if loc != results['final_url']:
            sitemap = requests.get(loc)
            if sitemap.status_code == HTTPStatus.OK:
                soup = BeautifulSoup(sitemap.text, 'xml')
                additional_urls += len(soup.find_all('url'))
    results['Total URLs'] = results['Total URLs'] + additional_urls
    print("Found %s URLs" % results['Total URLs'])
    
    # Can we compute how long it will take to index all URLs (in hours)?
    if results['Crawl delay']:
        print("Attempting to calculate crawl delay...")
        results['Est time to index'] = (int(results['Total URLs']) * int(results['Crawl delay'])) / 3600

    print("Sitemap scan for %s complete!" % fqd)
    return results


def seo_scan(fqd, results):
    """
    Scan pages for SEO items not covered by the sitemap scan above.
    1. Can we determine what platform it was built with?
    2. Can we find a Main tag?
    3. Can we find a search box?
    4. Do we find any duplicated titles or descriptions?
    """
    print("SEO scan function called for %s" % fqd)

    results = {
        'Platforms': 'Unknown',
        'Main tags found': False,
        'Search found': False,
        'Warnings': {},
    }

    # See if we can determine platforms used for the site
    print("Checking builtwith...")
    build_info = builtwith(fqd)
    if 'web-frameworks' in build_info:
        results['Platforms'] = build_info['web-frameworks']

    # We'll write to these empty lists for simple dupe checking later
    titles = []
    descriptions = []
    print("Checking pages...")
    for page in pages:
        try:
            r = requests.get(fqd + page, timeout=4)
            # if we didn't find the page, write minimal info and skip to next page
            if r.status_code != HTTPStatus.OK:
                results[page] = '404'
                continue
            htmlsoup = BeautifulSoup(r.text, 'lxml')
            # get title and put in dupe-checking list
            title = htmlsoup.find('title').get_text()
            titles.append(title)
            # and description
            description = htmlsoup.select_one("meta[name='description']")
            if description:
                descriptions.append(description['content'])
            # and can we find dc:date?
            dc_date = htmlsoup.select_one("meta[name='article:published_time']")
            if not dc_date:
                dc_date = htmlsoup.select_one("meta[name='article:modified_time']")
                if not dc_date:
                    dc_date = htmlsoup.select_one("meta[name='DC.Date']")
            # if we found one, grab the content
            if dc_date:
                dc_date = dc_date['content']

            # Find the main tag (or alternate), if we haven't found one already.
            # Potential TO-DO: check that there is only one. Necessary? ¯\_(ツ)_/¯
            if not results['Main tags found']:
                maintag = True if htmlsoup.find('main') else False
                # if we couldn't find `main` look for the corresponding role
                if not maintag:
                    maintag = True if htmlsoup.select('[role=main]') else False
                results['Main tags found'] = maintag

            # Look for a search form
            if not results['Search found']:
                searchtag = True if htmlsoup.find("input", {"type": "search"}) else False
                # if we couldn't find `a search input` look for classes
                if not searchtag:
                    searchtag = True if htmlsoup.select('[class*="search"]') else False
                results['Search found'] = searchtag

            # Now populate page info
            if r.status_code == HTTPStatus.OK:
                results[page] = {
                    'title': title,
                    'description': description,
                    'date': dc_date
                }
        except Exception as error:
            results[page] = "Could not get data from %s%s: %s" % (fqd, page, error)

    # now check for dupes
    print("Checking for duplicate meta tags...")
    if len(titles) != len(set(titles)):
        results['warnings']['Duplicate titles found'] = True
    if len(descriptions) != len(set(descriptions)):
        results['warnings']['Duplicate descriptions found'] = True

    print("SEO scan for %s Complete!" % fqd)

    return results


def scan(domain):
    """
    Pretty much just wraps the scans above to avoid some duplication
    and to pretty up the output.
    """
    # Fully qualified domain
    fqd = "https://%s" % domain  # note lack of trailing slash

    # First run the sitemap scanner
    sitemap_results = sitemap_scan(fqd, scan_data)
    # now run the seo scan, passing in the sitemap_results
    # so we're building the same dict
    full_results = seo_scan(fqd, sitemap_results)

    return full_results



if __name__ == "__main__":
    # execute only if run as a script
    domains = sys.argv[1].split(',')
    domain_data = []
    if domains:
        for domain in domains:
            scan_results = scan(domain)
            domain_data.append(scan_results)
        # now we're going to build out the CSV response
        with open('scan_output.csv', 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=scan_data.keys())
            writer.writeheader()
            # now populate the row from scan results to in the 
            # correct spot as defined by our headers
            writer.writerows(domain_data)
            print('Your scan output csv has been written.')
        
    else:
        print("No domains given. Domains should be a comma-separated list you provide to the scanner.")