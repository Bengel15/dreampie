__all__ = ['AutocompleteWindow', 'find_prefix_range']

from logging import debug

import gobject
import gtk
from gtk import gdk
import pango

try:
    from glib import idle_add
except ImportError:
    from gobject import idle_add

N_ROWS = 10

# A decorator for managing sourceview key handlers
# This decorates some methods of DreamPie.
keyhandlers = {}
def keyhandler(keyval, state):
    def decorator(func):
        keyhandlers[keyval, state] = func
        return func
    return decorator

class AutocompleteWindow(object):
    def __init__(self, sourceview, on_complete):
        self.sourceview = sourceview
        self.sourcebuffer = sb = sourceview.get_buffer()
        self.on_complete = on_complete
        
        self.liststore = gtk.ListStore(gobject.TYPE_STRING)        
        self.cellrend = gtk.CellRendererText()
        self.cellrend.props.ypad = 0

        self.col = gtk.TreeViewColumn("col", self.cellrend, text=0)
        self.col.props.sizing = gtk.TREE_VIEW_COLUMN_FIXED

        self.treeview = gtk.TreeView(self.liststore)
        self.treeview.props.headers_visible = False
        self.treeview.append_column(self.col)
        self.treeview.props.fixed_height_mode = True

        # Calculate width and height of treeview
        self.cellrend.props.text = 'a_quite_lengthy_identifier'
        _, _, width, height = self.cellrend.get_size(self.treeview, None)
        self.treeview.set_size_request(width, (height+2)*N_ROWS)

        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.props.hscrollbar_policy = gtk.POLICY_NEVER
        self.scrolledwindow.props.vscrollbar_policy = gtk.POLICY_ALWAYS
        self.scrolledwindow.add(self.treeview)
        
        self.window = gtk.Window(gtk.WINDOW_POPUP)
        self.window.props.resizable = False
        self.window.add(self.scrolledwindow)
        self.window.show_all()
        self.window_height = self.window.get_size()[1]
        self.window.hide()

        self.mark = sb.create_mark(None, sb.get_start_iter(), True)

        # We define this handler here so that it will be defined before
        # the default key-press handler, and so will have higher priority.
        self.keypress_handler = self.sourceview.connect(
            'key-press-event', self.on_keypress)
        self.sourceview.handler_block(self.keypress_handler)
        self.keypress_handler_blocked = True

        self.is_shown = False
        self.cur_list = None
        self.private_list = None
        self.showing_private = None
        self.cur_prefix = None

        # A list with (widget, handler) pairs, to be filled with self.connect()
        self.signals = []

    def connect(self, widget, *args):
        handler = widget.connect(*args)
        self.signals.append((widget, handler))

    def disconnect_all(self):
        for widget, handler in self.signals:
            widget.disconnect(handler)
        self.signals[:] = []

    def show(self, public, private, start_len):
        sb = self.sourcebuffer

        if self.is_shown:
            self.hide()
        self.is_shown = True

        it = sb.get_iter_at_mark(sb.get_insert())
        it.backward_chars(start_len)
        sb.move_mark(self.mark, it)

        # Update list and check if is empty
        self.cur_list = public
        self.private_list = private
        self.showing_private = False
        self.cur_prefix = None
        
        isnt_empty = self.update_list()
        if not isnt_empty:
            return
        
        self.place_window()

        self.connect(sb, 'mark-set', self.on_mark_set)
        self.connect(sb, 'insert-text', self.on_insert_text)
        self.connect(sb, 'delete-range', self.on_delete_range)

        self.connect(self.treeview, 'button-press-event',
                     self.on_tv_button_press)
        self.connect(self.sourceview, 'focus-out-event', self.on_focus_out)

        self.sourceview.handler_unblock(self.keypress_handler)
        self.keypress_handler_blocked = False

        self.window.show_all()

    def update_list(self, return_false=False):
        # Update the ListStore.
        # Return True if something is shown.
        # Otherwise, calls hide(), and returns False.
        # if return_false is True, always return False.
        sb = self.sourcebuffer
        prefix = sb.get_text(
            sb.get_iter_at_mark(self.mark),
            sb.get_iter_at_mark(sb.get_insert())).decode('utf8')
        if prefix == self.cur_prefix:
            return True and not return_false
        self.cur_prefix = prefix

        start, end = find_prefix_range(self.cur_list, prefix)
        if start == end and not self.showing_private:
            self.showing_private = True
            self.cur_list.extend(self.private_list)
            self.cur_list.sort()
            start, end = find_prefix_range(self.cur_list, prefix)
        if start == end:
            self.hide()
            return False

        self.liststore.clear()
        for i in xrange(end-start):
            self.liststore.insert(i, [self.cur_list[start+i]])
        self.treeview.get_selection().select_path(0)
        self.treeview.scroll_to_cell((0,))
        return True and not return_false

    def place_window(self):
        sv = self.sourceview
        sb = self.sourcebuffer
        it = sb.get_iter_at_mark(self.mark)
        loc = sv.get_iter_location(it)
        x, y = loc.x, loc.y
        x, y = sv.buffer_to_window_coords(gtk.TEXT_WINDOW_WIDGET, x, y)
        sv_x, sv_y = sv.get_window(gtk.TEXT_WINDOW_WIDGET).get_origin()
        x += sv_x; y += sv_y
        self.window.move(x, y-self.window_height)

    def on_mark_set(self, sb, it, mark):
        if mark is sb.get_insert():
            if it.compare(sb.get_iter_at_mark(self.mark)) < 0:
                self.hide()
            else:
                idle_add(self.update_list, True)

    def on_insert_text(self, sb, it, text, length):
        if it.compare(sb.get_iter_at_mark(self.mark)) < 0:
            self.hide()
        else:
            idle_add(self.update_list, True)

    def on_delete_range(self, sb, start, end):
        if start.compare(sb.get_iter_at_mark(self.mark)) < 0:
            self.hide()
        else:
            idle_add(self.update_list, True)

    @keyhandler('Escape', 0)
    def on_esc(self):
        self.hide()
        # Don't return True - other things may be escaped too.

    def select_row(self, row):
        path = (row,)
        self.treeview.get_selection().select_path(path)
        self.treeview.scroll_to_cell(path)

    @keyhandler('Up', 0)
    def on_up(self):
        index = self.treeview.get_selection().get_selected_rows()[1][0][0]
        if index > 0:
            self.select_row(index - 1)
        else:
            gdk.beep()
        return True

    @keyhandler('Down', 0)
    def on_down(self):
        index = self.treeview.get_selection().get_selected_rows()[1][0][0]
        if index < len(self.liststore) - 1:
            self.select_row(index + 1)
        else:
            gdk.beep()
        return True

    @keyhandler('Home', 0)
    def on_home(self):
        self.select_row(0)
        return True

    @keyhandler('End', 0)
    def on_end(self):
        self.select_row(len(self.liststore)-1)
        return True

    @keyhandler('Page_Up', 0)
    def on_page_up(self):
        # Select the row displayed at top, or, if it is displayed, scroll one
        # page and then display the row.
        tv = self.treeview
        sel = tv.get_selection()
        row = tv.get_path_at_pos(0, 1)[0][0]
        if sel.path_is_selected((row,)):
            if row == 0:
                gdk.beep()
            row = max(row - N_ROWS, 0)
        self.select_row(row)
        return True
        
    @keyhandler('Page_Down', 0)
    def on_page_down(self):
        # Select the row displayed at bottom, or, if it is displayed, scroll one
        # page and then display the row.
        tv = self.treeview
        sel = tv.get_selection()
        last_row = len(self.liststore) - 1
        r = tv.get_path_at_pos(0, tv.get_size_request()[1])
        if r is not None:
            row = r[0][0]
        else:
            # nothing is displayed there, too short list
            row = last_row
        if sel.path_is_selected((row,)):
            if row == last_row:
                gdk.beep()
            row = min(row + N_ROWS, last_row)
        self.select_row(row)
        return True

    @keyhandler('Return', 0)
    @keyhandler('Tab', 0)
    def complete(self):
        sel_row = self.treeview.get_selection().get_selected_rows()[1][0][0]
        text = self.liststore[sel_row][0].decode('utf8')
        insert = text[len(self.cur_prefix):]
        self.hide()
        self.sourcebuffer.insert_at_cursor(insert)
        self.on_complete()
        return True

    def on_keypress(self, widget, event):
        keyval, group, level, consumed_mods = \
            gdk.keymap_get_default().translate_keyboard_state(
                event.hardware_keycode, event.state, event.group)
        state = event.state & ~consumed_mods
        keyval_name = gdk.keyval_name(keyval)
        try:
            func = keyhandlers[keyval_name, state]
        except KeyError:
            pass
        else:
            return func(self)

    def on_tv_button_press(self, widget, event):
        if event.type == gdk._2BUTTON_PRESS:
            self.complete()
            return True

    def on_focus_out(self, widget, event):
        self.hide()

    def hide(self):
        self.disconnect_all()
        if not self.keypress_handler_blocked:
            self.sourceview.handler_block(self.keypress_handler)
            self.keypress_handler_blocked = True

        self.window.hide()

        self.is_shown = False
        self.cur_list = None
        self.private_list = None
        self.showing_private = None
        self.cur_prefix = None

        
def find_prefix_range(L, prefix):
    # Find the range in the list L which begins with prefix, using binary
    # search.

    # start.
    l = 0
    r = len(L)
    while r > l:
        m = (l + r) // 2
        if L[m] == prefix:
            l = r = m
        elif L[m] < prefix:
            l = m + 1
        else:
            r = m
    start = l

    # end
    l = 0
    r = len(L)
    while r > l:
        m = (l + r) // 2
        if L[m][:len(prefix)] > prefix:
            r = m
        else:
            l = m + 1
    end = l

    return start, end

