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

__all__ = ['Autocomplete']

import string

from .hyper_parser import HyperParser
from .autocomplete_window import AutocompleteWindow, find_prefix_range
from .beep import beep

# This string includes all chars that may be in an identifier
ID_CHARS = string.ascii_letters + string.digits + "_"

class Autocomplete(object):
    def __init__(self, sourceview, complete_attributes, complete_filenames,
                 INDENT_WIDTH):
        self.sourceview = sourceview
        self.sourcebuffer = sourceview.get_buffer()
        self.complete_attributes = complete_attributes
        self.complete_filenames = complete_filenames
        self.INDENT_WIDTH = INDENT_WIDTH

        self.window = AutocompleteWindow(sourceview, self._on_complete)

    def show_completions(self, is_auto, complete):
        """
        If complete is False, just show the comopletion list.
        If complete is True, complete as far as possible. If there's only
        one completion, don't show the window.

        If is_auto is True, don't beep if can't find completions.
        """
        sb = self.sourcebuffer
        text = sb.get_slice(sb.get_start_iter(),
                            sb.get_end_iter()).decode('utf8')
        index = sb.get_iter_at_mark(sb.get_insert()).get_offset()
        hp = HyperParser(text, index, self.INDENT_WIDTH)

        if hp.is_in_code():
            res = self._complete_attributes(text, index, hp, is_auto)
        elif hp.is_in_string():
            res = self._complete_filenames(text, index, hp, is_auto)
        else:
            # Not in string and not in code
            res = None

        if res is not None:
            comp_prefix, public, private, is_case_insen = res
        else:
            if not is_auto:
                beep()
            return

        combined = public + private
        if is_case_insen:
            combined.sort(key = lambda s: s.lower())
            combined_keys = [s.lower() for s in combined]
        else:
            combined.sort()
            combined_keys = combined
        comp_prefix_key = comp_prefix.lower() if is_case_insen else comp_prefix
        start, end = find_prefix_range(combined_keys, comp_prefix_key)
        if start == end:
            # No completions
            if not is_auto:
                beep()
            return

        if complete:
            # Find maximum prefix
            first = combined_keys[start]
            last = combined_keys[end-1]
            i = 0
            while i < len(first) and i < len(last) and first[i] == last[i]:
                i += 1
            if i > len(comp_prefix):
                sb.insert_at_cursor(combined[start][len(comp_prefix):i])
                comp_prefix = first[:i]
            if end == start + 1:
                # Only one matchine completion - don't show the window
                return

        self.window.show(public, private, is_case_insen, len(comp_prefix))
        
    def _complete_attributes(self, text, index, hp, is_auto):
        """
        Return (comp_prefix, public, private) - a string and two lists.
        If shouldn't complete - return None.
        """
        # Check whether autocompletion is really appropriate
        if is_auto and text[index-1] != '.':
            return
        
        i = index
        while i and text[i-1] in ID_CHARS:
            i -= 1
        comp_prefix = text[i:index]
        if i and text[i-1] == '.':
            hp.set_index(i-1)
            comp_what = hp.get_expression()
            if not comp_what:
                return
            if is_auto and '(' in comp_what:
                # Don't evaluate expressions which may contain a function call.
                return
        else:
            comp_what = u''
        public_and_private = self.complete_attributes(comp_what)
        if public_and_private is None:
            return
        public, private = public_and_private
        is_case_insen = False
        return comp_prefix, public, private, is_case_insen

    def _complete_filenames(self, text, index, hp, is_auto):
        """
        Return (comp_prefix, public, private) - a string and two lists.
        If shouldn't complete - return None.
        """
        str_start = hp.bracketing[hp.indexbracket][0] + 1
        # Analyze string a bit
        pos = str_start - 1
        str_char = text[pos]
        assert str_char in ('"', "'")
        if text[pos+1:pos+3] == str_char + str_char:
            # triple-quoted string - not for us
            return
        is_raw = pos > 0 and text[pos-1].lower() == 'r'
        if is_raw:
            pos -= 1
        is_unicode = pos > 0 and text[pos-1].lower() == 'u'
        if is_unicode:
            pos -= 1
        str_prefix = text[pos:str_start]

        # Do not open a completion list if after a single backslash in a
        # non-raw string
        if is_auto and text[index-1] == '\\' \
           and not is_raw and not self._is_backslash_char(text, index-1):
            return

        # Find completion start - last '/' or real '\\'
        sep_ind = max(text.rfind('/', 0, index), text.rfind('\\', 0, index))
        if sep_ind == -1 or sep_ind < str_start:
            # not found - prefix is all the string.
            comp_prefix_index = str_start
        elif text[sep_ind] == '\\' and not is_raw and not self._is_backslash_char(text, sep_ind):
            # Do not complete if the completion prefix contains a backslash.
            return
        else:
            comp_prefix_index = sep_ind+1

        comp_prefix = text[comp_prefix_index:index]
        
        res = self.complete_filenames(
            str_prefix, text[str_start:comp_prefix_index], str_char)
        if res is None:
            return
        public, private, is_case_insen = res
        
        return comp_prefix, public, private, is_case_insen
    
    def _on_complete(self):
        # Called when the user completed. This is relevant if he completed
        # a dir name, so that another completion window will be opened.
        self.show_completions(is_auto=True, complete=False)
        
    @staticmethod
    def _is_backslash_char(string, index):
        """
        Assuming that string[index] is a backslash, check whether it's a
        real backslash char or just an escape - if it has an odd number of
        preceding backslashes it's a real backslash
        """
        assert string[index] == '\\'
        count = 0
        while index-count > 0 and string[index-count-1] == '\\':
            count += 1
        return (count % 2) == 1
