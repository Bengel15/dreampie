# Copyright 2010 Noam Yorav-Raphael
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
import re

from .hyper_parser import HyperParser
from .autocomplete_window import AutocompleteWindow, find_prefix_range
from .common import beep, get_text, TimeoutError

# This string includes all chars that may be in an identifier
ID_CHARS = string.ascii_letters + string.digits + "_"
ID_CHARS_DOT = ID_CHARS + '.'

class Autocomplete(object):
    def __init__(self, sourceview, window_main, get_is_executing,
                 complete_attributes, complete_firstlevels, get_func_args,
                 find_modules, get_module_members, complete_filenames,
                 complete_dict_keys,
                 INDENT_WIDTH):
        self.sourceview = sourceview
        self.sourcebuffer = sourceview.get_buffer()
        self.get_is_executing = get_is_executing
        self.complete_attributes = complete_attributes
        self.complete_firstlevels = complete_firstlevels
        self.get_func_args = get_func_args
        self.find_modules = find_modules
        self.get_module_members = get_module_members
        self.complete_filenames = complete_filenames
        self.complete_dict_keys = complete_dict_keys
        self.INDENT_WIDTH = INDENT_WIDTH

        self.window = AutocompleteWindow(sourceview, window_main,
                                         self._on_complete)

    def show_completions(self, is_auto, complete):
        """
        If complete is False, just show the completion list.
        If complete is True, complete as far as possible. If there's only
        one completion, don't show the window.

        If is_auto is True, don't beep if can't find completions.
        """
        if self.get_is_executing():
            if not is_auto:
                beep()
            return
        
        sb = self.sourcebuffer
        text = get_text(sb, sb.get_start_iter(), sb.get_end_iter())
        index = sb.get_iter_at_mark(sb.get_insert()).get_offset()
        hp = HyperParser(text[:index], index, self.INDENT_WIDTH)

        if hp.is_in_code():
            line = text[text.rfind('\n', 0, index)+1:index].lstrip()
            if line.startswith('import '):
                res = self._complete_modules(line, is_auto)
            elif line.startswith('from '):
                if len((line+'x').split()) == 3:
                    # The third word should be "import".
                    res = self._complete_import(line)
                elif ' import ' not in line:            
                    res = self._complete_modules(line, is_auto)
                else:
                    res = self._complete_module_members(line, is_auto)
            elif line.endswith('['):
                # We complete dict keys either after a '[' or in a string
                # after a '['.
                res = self._complete_dict_keys(text, index, hp, is_auto)
            else:
                res = self._complete_attributes(text, index, hp, is_auto)
        elif hp.is_in_string():
            if text[max(hp.bracketing[hp.indexbracket][0]-1,0)] == '[':
                res = self._complete_dict_keys(text, index, hp, is_auto)
            else:
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
                # Only one matching completion - don't show the window
                self._on_complete()
                return

        self.window.show(public, private, is_case_insen, len(comp_prefix))
        
    def _complete_dict_keys(self, text, index, hp, is_auto):
        """
        Return (comp_prefix, public, private, is_case_insen) 
        (string, list, list, bool).
        If shouldn't complete - return None.
        """
        # Check whether auto-completion is really appropriate,
        if is_auto and text[index-1] != '[':
            return
        
        opener, _closer = hp.get_surrounding_brackets('[')
        if not opener:
            return
        hp.set_index(opener)
        comp_what = hp.get_expression()
        if not comp_what:
            return
        if is_auto and '(' in comp_what:
            # Don't evaluate expressions which may contain a function call.
            return
        try:
            key_reprs = self.complete_dict_keys(comp_what)
        except TimeoutError:
            return
        if text[index:index+1] != ']':
            key_reprs = [x+']' for x in key_reprs]

        comp_prefix = text[opener+1:index]
        public = key_reprs
        private = []
        is_case_insen = False
        return (comp_prefix, public, private, is_case_insen)

    def _complete_attributes(self, text, index, hp, is_auto):
        """
        Return (comp_prefix, public, private, is_case_insen) 
        (string, list, list, bool).
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
            try:
                public, private = self.complete_attributes(comp_what)
            except TimeoutError:
                return
        else:
            try:
                public, private = self.complete_firstlevels()
            except TimeoutError:
                return
            
            # If we are inside a function call after a ',' or '(',
            # get argument names.
            if text[:i].rstrip()[-1:] in (',', '('):
                opener, _closer = hp.get_surrounding_brackets('(')
                if opener:
                    hp.set_index(opener)
                    expr = hp.get_expression()
                    if expr and '(' not in expr:
                        # Don't need to execute a function just to get arguments
                        try:
                            args = self.get_func_args(expr)
                        except TimeoutError:
                            pass
                        else:
                            public.extend(args)
                            public.sort()
        
        is_case_insen = False
        return comp_prefix, public, private, is_case_insen

    def _complete_import(self, line):
        """
        Complete the word "import"...
        """
        i = len(line)
        while i and line[i-1] in ID_CHARS:
            i -= 1
        comp_prefix = line[i:]
        public = ['import']
        private = []
        is_case_insen = False
        return comp_prefix, public, private, is_case_insen
        
    
    def _complete_modules(self, line, is_auto):
        """
        line - the stripped line from its beginning to the cursor.
        Return (comp_prefix, public, private, is_case_insen) 
        (string, list, list, bool).
        If shouldn't complete - return None.
        """
        # Check whether autocompletion is really appropriate
        if is_auto and line[-1] != '.':
            return
        
        i = len(line)
        while i and line[i-1] in ID_CHARS:
            i -= 1
        comp_prefix = line[i:]
        if i and line[i-1] == '.':
            i -= 1
            j = i
            while j and line[j-1] in ID_CHARS_DOT:
                j -= 1
            comp_what = line[j:i]
        else:
            comp_what = u''
        
        try:
            modules = self.find_modules(comp_what)
        except TimeoutError:
            return None
        
        public = [s for s in modules if s[0] != '_']
        private = [s for s in modules if s[0] == '_']
        is_case_insen = False
        return comp_prefix, public, private, is_case_insen
        
    def _complete_module_members(self, line, is_auto):
        """
        line - the stripped line from its beginning to the cursor.
        Return (comp_prefix, public, private, is_case_insen) 
        (string, list, list, bool).
        If shouldn't complete - return None.
        """
        # Check whether autocompletion is really appropriate
        if is_auto:
            return
        
        i = len(line)
        while i and line[i-1] in ID_CHARS:
            i -= 1
        comp_prefix = line[i:]
        
        m = re.match(r'from\s+([\w.]+)\s+import', line)
        if m is None:
            return
        comp_what = m.group(1)
        
        try:
            public, private = self.get_module_members(comp_what)
        except TimeoutError:
            return
        is_case_insen = False
        return comp_prefix, public, private, is_case_insen
        
    def _complete_filenames(self, text, index, hp, is_auto):
        """
        Return (comp_prefix, public, private, is_case_insen) 
        (string, list, list, bool).
        If shouldn't complete - return None.
        """
        # Check whether autocompletion is really appropriate
        if is_auto and text[index-1] not in '\\/':
            return
        
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
        
        add_quote = not (len(text) > index and text[index] == str_char)
        
        try:
            public, private, is_case_insen = self.complete_filenames(
                str_prefix, text[str_start:comp_prefix_index], str_char,
                add_quote)
        except TimeoutError:
            return
        
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
