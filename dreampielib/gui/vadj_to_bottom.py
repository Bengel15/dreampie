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
# along with Foobar.  If not, see <http://www.gnu.org/licenses/>.

__all__ = ['VAdjToBottom']

class VAdjToBottom(object):
    """
    Scroll automatically to the bottom of the VAdj if the height changes
    and it was at bottom
    """
    def __init__(self, vadj):
        self.vadj = vadj
        vadj.connect('changed', self.on_changed)
        vadj.connect('value-changed', self.on_value_changed)
        self.vadj_was_at_bottom = self.is_at_bottom()
        self.scroll_to_bottom()

    def is_at_bottom(self):
        return self.vadj.value == self.vadj.upper - self.vadj.page_size

    def scroll_to_bottom(self):
        self.vadj.set_value(self.vadj.upper - self.vadj.page_size)

    def on_changed(self, widget):
        if self.vadj_was_at_bottom and not self.is_at_bottom():
            self.scroll_to_bottom()
        self.vadj_was_at_bottom = self.is_at_bottom()

    def on_value_changed(self, widget):
        self.vadj_was_at_bottom = self.is_at_bottom()
