#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2011, Hakan Tandogan <hakan@gurkensalat.com>'
__docformat__ = 'restructuredtext en'

import time
from urllib import quote

from calibre import as_unicode
from calibre.ebooks.metadata.sources.base import Source

class BeamEbooks(Source):

    name = 'Beam Ebooks'
    description = _('Downloads Metadata and covers from Beam Ebooks')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Hakan Tandogan'
    version = (1, 0, 0)
    minimum_calibre_version = (0, 8, 4)

    capabilities = frozenset(['identify'])
        # , 'cover'
    touched_fields = frozenset(['identifier:beam-ebooks'])
        # 'title'
        # 'authors', 
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
            query = self.create_query(log, title=title, authors=authors,
                    identifiers=identifiers)
            if query is None:
                log.error("    Insufficient metadata to construct query")
                return

            try:
                log.info("    Querying: %s" % query)
                response = br.open_novisit(query, timeout=timeout)
                location = response.geturl()
                log.info("    Redirected to: %r" % location)
                matches.append(location)
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
    

    def create_query(self, log, title=None, authors=None, identifiers={}):
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
                    index_of_dash = title.find(" - ")
                    if index_of_dash > -1:
                        # title = title[:index_of_dash]
                        index_of_dash = index_of_dash + 3
                        title = title[index_of_dash:]
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
