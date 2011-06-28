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

        # raw = raw.decode('utf-8', errors='replace')
        raw = raw.decode('iso-8859-1', errors='replace')
        # open('D:\\work\\calibre-dump-book-details.html', 'wb').write(raw)

        if '<title>404 - ' in raw:
            self.log.error('URL malformed: %r' % self.url)
            return

        try:
            # root = fromstring(clean_ascii_chars(raw))
            root = fromstring(raw)
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
            (self.title, self.series_index) = self.parse_title(root)
        except:
            self.log.exception('Error parsing title for url: %r' % self.url)
            self.title = None
            self.series_index = None

        try:
            self.authors = self.parse_authors(root)
        except:
            self.log.exception('Error parsing authors for url: %r' % self.url)
            self.authors = None

        mi = Metadata(self.title, self.authors)
        mi.set_identifier('beam-ebooks', self.beam_ebooks_id)

        if self.series_index:
            mi.series_index = float(self.series_index)
        
        self._determine_perry_rhodan_cycle_name(mi)

        mi.source_relevance = self.relevance

        self.plugin.clean_downloaded_metadata(mi)

        print(mi)
        self.result_queue.put(mi)        


    def parse_beam_ebooks_id(self, url):
        return re.search('/ebook/(\d+)', url).groups(0)[0]


    def parse_title(self, root):
        title = None
        series_index = None

        nodes = root.xpath('//tr/td/div/h1/strong')
        if not nodes:
            print("Title pattern, no title line found")
        else:
            for i, node in enumerate(nodes):
                # print("Title pattern %s content %s " % (i, node.text_content().strip()))
                title = node.text_content().strip()

        # TODO: title munging should be configurable
        pr_series_title = " - Perry Rhodan "
        index_of_pr = title.find(pr_series_title)
        if index_of_pr > -1:
            prefix = title[:index_of_pr]
            print("    Prefix: '%s'" % (prefix))
            index_of_pr = index_of_pr + len(pr_series_title)
            series_index = title[index_of_pr:]
            while len(series_index) < 4:
                series_index = "0" + series_index
            print("    Series Index: '%s'" % (series_index))
            title = "PR" + series_index + " - " + prefix

        pr_series_title = "PERRY RHODAN-Heftroman "
        index_of_pr = title.find(pr_series_title)
        if index_of_pr > -1:
            index_of_pr = index_of_pr + len(pr_series_title)
            # TODO: Test this again with a three-digit issue number
            index_of_pr = index_of_pr + 6
            postfix = title[index_of_pr:]
            print("    Postfix: '%s'" % (postfix))
            series_index = title[:index_of_pr]
            print("    Series-Index-1: '%s'" % (series_index))
            series_index = series_index[len(series_index) - 6 : len(series_index) - 2]
            print("    Series-Index-2: '%s'" % (series_index))
            title = "PR" + series_index + " - " + postfix

        if title != None:
            # print("Plain '%s'" % title)
            # print("UTF-8 '%s'" % title.encode('utf-8'))
            # title = title.encode('utf-8')
            title = title.decode('utf-8')
            # title = title.decode('iso-8859-1')
            # title = title.encode('iso-8859-1')

        return (title, series_index)


    def parse_authors(self, root):
        authors = []

        nodes = root.xpath('//tr/td/p/a')
        if not nodes:
            print("Authors pattern 1, no authors line found")
        else:
            for i, node in enumerate(nodes):
                url = node.get('href').strip()
                # print("Authors pattern %s content %s, %s " % (i, node.text_content().strip(), url))
                if url.find('/autoreninfo.php') > -1:
                    author = node.text_content().strip()
                    authors.append(author)

        nodes = root.xpath('//tr/td/a')
        if not nodes:
            print("Authors pattern 2, no authors line found")
        else:
            for i, node in enumerate(nodes):
                url = node.get('href').strip()
                # print("Authors pattern %s content %s, %s " % (i, node.text_content().strip(), url))
                if url.find('/autoreninfo.php') > -1:
                    author = node.text_content().strip()
                    authors.append(author)

        return authors

    def _determine_perry_rhodan_cycle_name(self, mi):
        if self.title.find("PR") == 0 and self.series_index > 0:
            mi.series = "Perry Rhodan"
            if mi.series_index >= 1 and mi.series_index <= 49:
                mi.series = "Perry Rhodan, Die dritte Macht"
            if mi.series_index >= 50 and mi.series_index <= 99:
                mi.series = "Perry Rhodan, Atlan und Arkon"
            if mi.series_index >= 100 and mi.series_index <= 149:
                mi.series = "Perry Rhodan, Die Posbis"
            if mi.series_index >= 150 and mi.series_index <= 199:
                mi.series = "Perry Rhodan, Das zweite Imperium"
            if mi.series_index >= 200 and mi.series_index <= 299:
                mi.series = "Perry Rhodan, Die Meister der Insel"
            if mi.series_index >= 300 and mi.series_index <= 399:
                mi.series = "Perry Rhodan, M 87"
            if mi.series_index >= 400 and mi.series_index <= 499:
                mi.series = "Perry Rhodan, Die Cappins"
            if mi.series_index >= 500 and mi.series_index <= 569:
                mi.series = "Perry Rhodan, Der Schwarm"
            if mi.series_index >= 570 and mi.series_index <= 599:
                mi.series = "Perry Rhodan, Die Altmutanten"
            if mi.series_index >= 600 and mi.series_index <= 649:
                mi.series = "Perry Rhodan, Das kosmische Schachspiel"
            if mi.series_index >= 650 and mi.series_index <= 699:
                mi.series = "Perry Rhodan, Das Konzil"
            if mi.series_index >= 700 and mi.series_index <= 799:
                mi.series = "Perry Rhodan, Die Aphilie"
            if mi.series_index >= 800 and mi.series_index <= 867:
                mi.series = "Perry Rhodan, Bardioc"
            if mi.series_index >= 868 and mi.series_index <= 899:
                mi.series = "Perry Rhodan, PAN-THAU-RA"
            if mi.series_index >= 900 and mi.series_index <= 999:
                mi.series = "Perry Rhodan, Die Kosmischen Burgen"
            if mi.series_index >= 1000 and mi.series_index <= 1099:
                mi.series = "Perry Rhodan, Die Kosmische Hanse"
            if mi.series_index >= 1100 and mi.series_index <= 1199:
                mi.series = "Perry Rhodan, Die Endlose Armada"
            if mi.series_index >= 1200 and mi.series_index <= 1299:
                mi.series = "Perry Rhodan, Chronofossilien"
            if mi.series_index >= 1300 and mi.series_index <= 1349:
                mi.series = "Perry Rhodan, Die Gänger des Netzes"
            if mi.series_index >= 1400 and mi.series_index <= 1499:
                mi.series = "Perry Rhodan, Die Cantaro"
            if mi.series_index >= 1500 and mi.series_index <= 1599:
                mi.series = "Perry Rhodan, Die Linguiden"
            if mi.series_index >= 1600 and mi.series_index <= 1649:
                mi.series = "Perry Rhodan, Die Ennox"
            if mi.series_index >= 1650 and mi.series_index <= 1699:
                mi.series = "Perry Rhodan, Die Große Leere"
            if mi.series_index >= 1700 and mi.series_index <= 1749:
                mi.series = "Perry Rhodan, Die Ayindi"
            if mi.series_index >= 1800 and mi.series_index <= 1875:
                mi.series = "Perry Rhodan, Die Tolkander"
            if mi.series_index >= 1876 and mi.series_index <= 1899:
                mi.series = "Perry Rhodan, Die Heliotischen Bollwerke"
            if mi.series_index >= 1900 and mi.series_index <= 1949:
                mi.series = "Perry Rhodan, Der Sechste Bote"
            if mi.series_index >= 1950 and mi.series_index <= 1999:
                mi.series = "Perry Rhodan, MATERIA"
            if mi.series_index >= 2000 and mi.series_index <= 2099:
                mi.series = "Perry Rhodan, Die Solare Residenz"
            if mi.series_index >= 2100 and mi.series_index <= 2199:
                mi.series = "Perry Rhodan, Das Reich Tradom"
            if mi.series_index >= 2200 and mi.series_index <= 2299:
                mi.series = "Perry Rhodan, Der Sternenozean"
            if mi.series_index >= 2300 and mi.series_index <= 2399:
                mi.series = "Perry Rhodan, TERRANOVA"
            if mi.series_index >= 2400 and mi.series_index <= 2499:
                mi.series = "Perry Rhodan, Negaspähre"
            if mi.series_index >= 2500 and mi.series_index <= 2599:
                mi.series = "Perry Rhodan, Stardust"
            elif mi.series_index >= 2600 and mi.series_index < 2699:
                mi.series = "Perry Rhodan, Neuroversum"

