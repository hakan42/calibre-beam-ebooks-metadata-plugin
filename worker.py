#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2011, Hakan Tandogan <hakan@gurkensalat.com>'
__docformat__ = 'restructuredtext en'

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
            self.log.exception('get_details failed for url: %r'%self.url)

    def get_details(self):
        self.log.info("    Worker.get_details:")
        self.log.info("        self:     ", self)
        self.log.info("        self.url: ", self.url)

        try:
            self.beam_ebooks_id = self.parse_beam_ebooks_id(self.url)
        except:
            self.log.exception('Error parsing beam ebooks id for url: %r'%self.url)
            self.beam_ebooks_id = None

        title = "PR2600 - Das Thanatos-Programm"
        authors = ["Uwe Anton"]

        mi = Metadata(title, authors)
        mi.set_identifier('beam-ebooks', self.beam_ebooks_id)

        mi.source_relevance = self.relevance

        self.plugin.clean_downloaded_metadata(mi)

        self.result_queue.put(mi)

    def parse_beam_ebooks_id(self, url):
        return re.search('/ebook/(\d+)', url).groups(0)[0]

