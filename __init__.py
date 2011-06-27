#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2011, Hakan Tandogan <hakan@gurkensalat.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.metadata.sources.base import Source

class BeamEbooks(Source):

    name = 'Beam Ebooks'
    description = _('Downloads Metadata and covers from Beam Ebooks')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Hakan Tandogan'
    version = (1, 0, 0)
    minimum_calibre_version = (0, 8, 4)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['identifier:beam-ebooks'])
        #'title'
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
