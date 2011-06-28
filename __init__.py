#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2011, Hakan Tandogan <hakan@gurkensalat.com>'
__docformat__ = 'restructuredtext en'

import time
from urllib import quote

from lxml.html import fromstring, tostring

from calibre import as_unicode
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.cleantext import clean_ascii_chars

class BeamEbooks(Source):

    name = 'Beam Ebooks'
    description = _('Downloads Metadata and covers from Beam Ebooks')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Hakan Tandogan'
    version = (1, 0, 0)
    minimum_calibre_version = (0, 8, 4)

    capabilities = frozenset(['identify'])
        # , 'cover'
    touched_fields = frozenset(['identifier:beam-ebooks',
                                'title',
                                'authors'])
        # 'identifier:isbn',
        # 'rating',
        # 'comments',
        # 'publisher',
        # 'pubdate',
        # 'tags',
        # 'series'

    supports_gzip_transfer_encoding = True

    BASE_URL = 'http://www.beam-ebooks.de'

    def get_book_url(self, identifiers):
        beam_ebooks_id = identifiers.get('beam-ebooks', None)
        if beam_ebooks_id:
            return ('beam_ebooks', beam_ebooks_id,
                    '%s/ebook/%s' % (BeamEbooks.BASE_URL, beam_ebooks_id))


    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        '''
        Note this method will retry without identifiers automatically if no
        match is found with identifiers.
        '''
        print("identify")
        print("    Title: ", title)
        print("    Authors: ", authors)
        print("    Identifiers are: ", identifiers)

        matches = []
        # Unlike the other metadata sources, and like the Goodreads source,
        # if we have a beam ebooks id then we do not need to fire a "search"
        # at beam-ebooks.de. Instead we will be able to go straight to the
        # URL for that book.
        br = self.browser
        beam_ebooks_id = identifiers.get('beam-ebooks', None)
        if beam_ebooks_id:
            print("    Found Beam ID %s" % (beam_ebooks_id))
            matches.append('%s/ebook/%s' % (BeamEbooks.BASE_URL, beam_ebooks_id))
        else:
            query = self._create_query(log, title=title, authors=authors, identifiers=identifiers)
            if query is None:
                log.error("    Insufficient metadata to construct query")
                return

            try:
                log.info("    Querying: %s" % query)
                print("    Querying: %s" % query)
                response = br.open_novisit(query, timeout=timeout)
                location = response.geturl()
                log.info("    Redirected to: %r" % location)
                matches.append(location)

                try:
                    raw = response.read().strip()
                    # open('D:\\work\\calibre-dump.html', 'wb').write(raw)
                    raw = raw.decode('utf-8', errors='replace')
                    if not raw:
                        log.error("    Failed to get raw result for query: %r" % query)
                        return
                    root = fromstring(clean_ascii_chars(raw))
                except:
                    msg = "    Failed to parse beam ebooks page for query: %r" % query
                    log.exception(msg)
                    print(msg)
                    return msg

                # Now grab the first value from the search results, provided the
                # title and authors appear to be for the same book
                self._parse_search_results(log, title, authors, root, matches, timeout)

            except Exception as e:
                err = "    Failed to make identify query: %r" % query
                log.exception(err)
                return as_unicode(e)

        if abort.is_set():
            return

        print("    Matches are: ", matches)
        log.info("    Matches are: ", matches)

        from calibre_plugins.beam_ebooks_metadata.worker import Worker
        workers = [Worker(url, result_queue, br, log, i, self) for i, url in enumerate(matches)]

        for w in workers:
            w.start()
            # Don't send all requests at the same time
            time.sleep(0.1)

        while not abort.is_set():
            a_worker_is_alive = False
            for w in workers:
                w.join(0.2)
                if abort.is_set():
                    break
                if w.is_alive():
                    a_worker_is_alive = True
            if not a_worker_is_alive:
                break

        return None
    

    def _create_query(self, log, title=None, authors=None, identifiers={}):
        log("create_query")
        log("Title: ", title)
        log("Authors: ", authors)
        log("Identifiers: ", identifiers)

        q = None
        
        # http://www.beam-ebooks.de/suchergebnis.php?Type=Title&sw=Thanatos&x=0&y=0
        if q == None:
            if title != None:
                # Special handling for Perry Rhodan files
                if title.startswith("PR"):
                    title = title.encode('utf-8') if isinstance(title, unicode) else title
                    index_of_dash = title.find(" - ")
                    if index_of_dash > -1:
                        # title = title[:index_of_dash]
                        index_of_dash = index_of_dash + 3
                        title = title[index_of_dash:]
                    else:
                        # Try without spaces, for the old convention
                        if len(title) > 6:
                            if title[6] == '-':
                                title = title[7:]

                    msg = "    Perry Rhodan, modified title: %s" % (title)
                    log.info(msg)
                    print(msg)

                title = title.encode('utf-8') if isinstance(title, unicode) else title
                q = '%s/suchergebnis.php?Type=Title&sw=%s&x=0&y=0' % (BeamEbooks.BASE_URL, quote(title))

        # Not sure if searching for authors is a good idea here...
        # http://www.beam-ebooks.de/suchergebnis.php?Type=Author&sw=Uwe+Anton&x=0&y=0
        if q == None:
            if authors != None:
                q = None

        # http://www.beam-ebooks.de/suchergebnis.php?Type=&sw=Thanatos&x=1&y=10

        return q

    def _parse_search_results(self, log, orig_title, orig_authors, root, matches, timeout):

        # result_url = BeamEbooks.BASE_URL + first_result_url_node[0]
        # <div CLASS='stil2'> <b>Leo Lukas</b><br><a href='/ebook/19938'><b>PERRY RHODAN-Heftroman 2601: Galaxis in Aufruhr</b></a><br><i>Die ersten Tage in Chanda - Landung auf der Mysteriösen Glutwelt</i></DIV>
        first_result = root.xpath('//div[@class="stil2"]/a')
        if not first_result:
            print("First pattern, no ebook line found")

        # Try with an p tag in between
        first_result = root.xpath('//div[@class="stil2"]/p/a')
        if not first_result:
            print("Second pattern, no ebook line found")

        # print("First result: ", first_result)
        url = first_result[0].get('href').strip()
        # print("Extracted URL ", url)

        if url.find("/ebook/") > -1:
            result_url = "%s/%s" % (BeamEbooks.BASE_URL, url)
            matches.append(result_url)

if __name__ == '__main__': # tests
    # To run these test use:
    # calibre-debug -e __init__.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin, title_test, authors_test)
    test_identify_plugin(BeamEbooks.name,
        [
            (
                # A book with a beam ebooks id
                {'identifiers':{'beam-ebooks': '12748'}, 'title':'Invasion aus dem All', 'authors':['Clark Darlton']},
                [
                    title_test('PR0007 - Invasion aus dem All', exact=True),
                    authors_test(['Clark Darlton']),
                ]
            ),
        ])

