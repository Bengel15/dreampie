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

__all__ = ['Config']

import os
from ConfigParser import RawConfigParser
from StringIO import StringIO

from .odict import OrderedDict

default_config = """
[DreamPie]
show-getting-started = True
font=Courier New 10
current-theme = dark
pprint = False
cache-size = 0
init-code = ''

recall-1-char-commands = False
hide-defs = False
leave-code = False

[dark-theme]
text-fg = white
text-bg = black

stdin-fg = white
stdin-bg = black
stdout-fg = #bcffff
stdout-bg = black
stderr-fg = #ff8080
stderr-bg = black
cache-ind-fg = blue
cache-ind-bg = black
expr-res-fg = #bcffff
expr-res-bg = black
exception-fg = #ff8080
exception-bg = black
prompt-fg = #e400b6
prompt-bg = black
command-fg = white
command-bg = black
message-fg = yellow
message-bg = black

keyword-fg = #ff7700
keyword-bg = black
builtin-fg = #efcfcf
builtin-bg = black
string-fg = #00e400
string-bg = black
number-fg = #aeacff
number-bg = black
comment-fg = #c9a3a0
comment-bg = black

bracket-match-fg = white
bracket-match-bg = darkblue

stdin-fg-set = False
stdin-bg-set = False
stdout-fg-set = True
stdout-bg-set = False
stderr-fg-set = True
stderr-bg-set = False
cache-ind-fg-set = True
cache-ind-bg-set = False
expr-res-fg-set = True
expr-res-bg-set = False
exception-fg-set = True
exception-bg-set = False
prompt-fg-set = True
prompt-bg-set = False
command-fg-set = True
command-bg-set = False
message-fg-set = True
message-bg-set = False

keyword-fg-set = True
keyword-bg-set = False
builtin-fg-set = True
builtin-bg-set = False
string-fg-set = True
string-bg-set = False
number-fg-set = True
number-bg-set = False
comment-fg-set = True
comment-bg-set = False

bracket-match-fg-set = False
bracket-match-bg-set = True
"""

class Config(object):
    """
    Manage configuration.
    config.get(key) - gets a value from the loaded file.
    config.set(key, value) - stores a value, and saves.
    """
    def __init__(self):
        self.filename = os.path.join(os.path.expanduser('~'), '.dreampie')
        try:
            self.parser = RawConfigParser(dict_type=OrderedDict)
        except TypeError:
            # Python versions < 2.6 don't support dict_type
            self.parser = RawConfigParser()
        f = StringIO(default_config)
        self.parser.readfp(f)
        self.parser.read(self.filename)
        f = open(self.filename, 'w')
        self.parser.write(f)
        f.close()
    
    def get(self, key, section='DreamPie'):
        return self.parser.get(section, key)
    
    def get_bool(self, key, section='DreamPie'):
        s = self.get(key, section)
        s = s.lower()
        if s in ('1', 'true'):
            return True
        elif s in ('0', 'false'):
            return False
        else:
            raise ValueError("Expecting boolean value for key %s in section %s, "
                             "found %r." % (key, section, s))
    
    def set(self, key, value, section='DreamPie'):
        self.parser.set(section, key, value)
        f = open(self.filename, 'w')
        self.parser.write(f)
        f.close()
    
    def set_bool(self, key, value, section='DreamPie'):
        key = 'True' if value else 'False'
        self.set(key, value, section)

