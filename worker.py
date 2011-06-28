#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2011, Hakan Tandogan <hakan@gurkensalat.com>'
__docformat__ = 'restructuredtext en'

import socket
import re

from threading import Thread

from lxml.html import fromstring, tostring

from calibre.ebooks.metadata.book.base import Metadata
from calibre.library.comments import sanitize_comments_html
from calibre.utils.cleantext import clean_ascii_chars

class Worker(Thread): # Get details

    '''
    Get book details from Beam Ebooks book page in a separate thread
    '''

    def __init__(self, url, result_queue, browser, log, relevance, plugin, timeout=20):
        Thread.__init__(self)
        self.daemon = True
        self.url = url
        self.result_queue = result_queue
        self.log = log
        self.timeout = timeout
        self.relevance = relevance
        self.plugin = plugin
        self.browser = browser.clone_browser()
        self.cover_url = None
        self.beam_ebooks_id = None

    def run(self):
        self.log.info("    Worker.run: self: ", self)
        try:
            self.get_details()
        except:
            self.log.exception('get_details failed for url: %r' % self.url)

    def get_details(self):
        self.log.info("    Worker.get_details:")
        self.log.info("        self:     ", self)
        self.log.info("        self.url: ", self.url)
        
        # We should not even be here if we are not processing an ebook hit
        if self.url.find("/ebook/") == -1:
            return

        try:
            raw = self.browser.open_novisit(self.url, timeout=self.timeout).read().strip()
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and e.getcode() == 404:
                self.log.error('URL malformed: %r' % self.url)
                return
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                msg = 'Beam Ebooks timed out. Try again later.'
                self.log.error(msg)
            else:
                msg = 'Failed to make details query: %r' % self.url
                self.log.exception(msg)
            return

        raw = raw.decode('utf-8', errors='replace')
        open('D:\\work\\calibre-dump-book-details.html', 'wb').write(raw)

        if '<title>404 - ' in raw:
            self.log.error('URL malformed: %r' % self.url)
            return

        try:
            root = fromstring(clean_ascii_chars(raw))
        except:
            msg = 'Failed to parse beam ebooks details page: %r' % self.url
            self.log.exception(msg)
            return

        try:
            self.beam_ebooks_id = self.parse_beam_ebooks_id(self.url)
        except:
            self.log.exception('Error parsing beam ebooks id for url: %r' % self.url)
            self.beam_ebooks_id = None

        try:
            self.title = self.parse_title(root)
        except:
            self.log.exception('Error parsing title for url: %r' % self.url)
            self.title = None

        try:
            self.authors = self.parse_authors(root)
        except:
            self.log.exception('Error parsing authors for url: %r' % self.url)
            self.authors = None

        mi = Metadata(self.title, self.authors)
        mi.set_identifier('beam-ebooks', self.beam_ebooks_id)

        mi.source_relevance = self.relevance

        self.plugin.clean_downloaded_metadata(mi)

        self.result_queue.put(mi)


    def parse_beam_ebooks_id(self, url):
        return re.search('/ebook/(\d+)', url).groups(0)[0]


    def parse_title(self, root):
        title = None

        first_result = root.xpath('//table/tbody/tr/td/div/h1/strong')
        if not first_result:
            print("First pattern, no title line found")
        else:
            print("First pattern content ", first_result[0].text_content().strip())

        title = "PR0007 - Invasion aus dem All"

        return title


    def parse_authors(self, root):
        author = None

        author = "Clark Darlton"

        return [author]
