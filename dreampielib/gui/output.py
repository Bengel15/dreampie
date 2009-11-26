# Copyright 2009 Noam Yorav-Raphael
#
# This file is part of DreamPie.
# 
# DreamPie is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# DreamPie is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with DreamPie.  If not, see <http://www.gnu.org/licenses/>.

__all__ = ['Output']

import sys
import re
from StringIO import StringIO

from .tags import STDOUT, STDERR

remove_cr_re = re.compile(r'\n[^\n]*\r')
# Match ANSI escapes. See http://en.wikipedia.org/wiki/ANSI_escape_code
ansi_escape_re = re.compile(r'\x1b\[[^@-~]*?[@-~]')

# Length after which to break a line with a '\r' - a character which we
# ignore when copying.
BREAK_LEN = 1600

class Output(object):
    """
    Manage writing output (stdout and stderr) to the text view.
    """
    def __init__(self, textview):
        self.textview = textview
        self.textbuffer = tb = textview.get_buffer()

        self.mark = tb.create_mark(None, tb.get_end_iter(), left_gravity=True)
        self.is_cr = False

    def set_mark(self, it):
        self.textbuffer.move_mark(self.mark, it)
        self.is_cr = False

    def write(self, data, tag_name):
        tb = self.textbuffer

        # Keep lines if after the cr there was no data before the lf.
        # Since that's the normal Windows newline, it's very important.
        data = data.replace('\r\n', '\n')
        # But remove chars before cr if something follows.
        data = ansi_escape_re.sub('', data)
        
        has_trailing_cr = data.endswith('\r')
        if has_trailing_cr:
            data = data[:-1]
            
        data = remove_cr_re.sub('\n', data)

        cr_pos = data.rfind('\r')
        if self.is_cr or cr_pos != -1:
            # Delete last written line
            it = tb.get_iter_at_mark(self.mark)
            it2 = it.copy()
            it2.set_line_offset(0)
            tb.delete(it2, it)

            # Remove data up to \r.
            if cr_pos != -1:
                data = data[cr_pos+1:]

        # We DO use \r characters as linebreaks after BREAK_LEN chars, which
        # are not copied.
        f = StringIO()

        pos = 0
        copied_pos = 0
        col = tb.get_iter_at_mark(self.mark).get_line_offset()
        next_newline = data.find('\n', pos)
        if next_newline == -1:
            next_newline = len(data)
        while pos < len(data):
            if next_newline - pos + col > BREAK_LEN:
                pos = pos + BREAK_LEN - col
                f.write(data[copied_pos:pos])
                f.write('\r')
                copied_pos = pos
                col = 0
            else:
                pos = next_newline + 1
                col = 0
                next_newline = data.find('\n', pos)
                if next_newline == -1:
                    next_newline = len(data)
        f.write(data[copied_pos:])

        it = tb.get_iter_at_mark(self.mark)
        tb.insert_with_tags_by_name(it, f.getvalue(), tag_name)
        # Move mark to after the written text
        tb.move_mark(self.mark, it)

        self.is_cr = has_trailing_cr

