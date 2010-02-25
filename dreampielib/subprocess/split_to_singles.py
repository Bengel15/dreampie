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

__all__ = ['split_to_singles']

import tokenize

class ReadLiner(object):
    """
    Perform readline over a string.
    After finishing, line_offsets contains the offset in the string for each
    line. Each line, except for the last one, ends with a '\n'. The last line
    doesn't end with a '\n'. So the number of lines is the number of '\n' chars
    in the string plus 1.
    """
    def __init__(self, s):
        self.s = s
        self.line_offsets = [0]
        self.finished = False

    def __call__(self):
        if self.finished:
            return ''
        s = self.s
        line_offsets = self.line_offsets
        next_offset = s.find('\n', line_offsets[-1])
        if next_offset == -1:
            self.finished = True
            return s[line_offsets[-1]:]
        else:
            line_offsets.append(next_offset+1)
            return s[line_offsets[-2]:line_offsets[-1]]

def split_to_singles(source):
    """Get a source string, and split it into several strings,
    each one a "single block" which can be compiled in the "single" mode.
    Every string which is not the last one ends with a '\n', so to convert
    a line number of a sub-string to a line number of the big string, add
    the number of '\n' chars in the preceding strings.
    """
    readline = ReadLiner(source)
    first_lines = [0] # Indices, 0-based, of the rows which start a new single.
    cur_indent_level = 0
    last_was_newline = False
    
    # What this does is pretty simple: We split on every NEWLINE token which
    # is on indentation level 0 and is not followed by "except" or "finally"
    # (in that case it should be kept with the previous "single").
    # Since we get the tokens one by one, and INDENT and DEDENT tokens come
    # *after* the NEWLINE token, we need a bit of care, so we wait for tokens
    # after the NEWLINE token to decide what to do.
    
    tokens_iter = tokenize.generate_tokens(readline)
    try:
        for typ, s, (srow, _scol), (_erow, _rcol), line in tokens_iter:
            if typ == tokenize.COMMENT or typ == tokenize.NL:
                continue
            
            if last_was_newline:
                if cur_indent_level == 0 and typ != tokenize.INDENT:
                    first_lines.append(srow-1)
                elif cur_indent_level == 1 and typ == tokenize.DEDENT:
                    first_lines.append(srow-1)
                    last_was_newline = False
                    
            # Don't start a new block on else, except and finally.
            if (typ == tokenize.NAME
                and s in ('else', 'except', 'finally')
                and first_lines[-1] == srow-1):
                first_lines.pop()
            
            if typ == tokenize.INDENT:
                cur_indent_level += 1
            elif typ == tokenize.DEDENT:
                cur_indent_level -= 1
            else:
                last_was_newline = (typ == tokenize.NEWLINE)
    except tokenize.TokenError:
        # EOF in the middle, it's a syntax error anyway.
        pass
        
    line_offsets = readline.line_offsets
    r = []
    for i, line in enumerate(first_lines):
        if i != len(first_lines)-1:
            r.append(source[line_offsets[line]:line_offsets[first_lines[i+1]]])
        else:
            r.append(source[line_offsets[line]:])
    return r
