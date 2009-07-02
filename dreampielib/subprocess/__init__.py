import sys
import os
import time
import socket
from select import select
import codeop
from StringIO import StringIO
import linecache
import traceback
import types
import keyword
import __builtin__

from ..common.objectstream import send_object, recv_object
from .split_to_singles import split_to_singles

# import rpdb2; rpdb2.start_embedded_debugger('a')

import logging
from logging import debug
logging.basicConfig(filename='/tmp/dreampie_subp_log', level=logging.DEBUG)

# time interval to process GUI events
GUI_SLEEP_SEC = 0.1
GUI_SLEEP_MS = 100

rpc_funcs = set()
# A decorator which adds the function name to rpc_funcs
def rpc_func(func):
    rpc_funcs.add(func.func_name)
    return func

class Subprocess(object):
    def __init__(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', port))

        # Trick things like pdb into thinking that the namespace we create is
        # the main module
        mainmodule = types.ModuleType('__name__')
        sys.modules['__main__'] = mainmodule
        self.locs = mainmodule.__dict__

        self.compile = codeop.CommandCompiler()
        self.gid = 0

        while True:
            self.handle_gui_events(sock)
            funcname, args = recv_object(sock)
            if funcname in rpc_funcs:
                func = getattr(self, funcname)
                r = func(*args)
                if isinstance(r, types.GeneratorType):
                    for obj in r:
                        send_object(sock, obj)
                else:
                    send_object(sock, r)
            else:
                raise ValueError("Unknown command: %s" % funcname)

    def handle_gui_events(self, sock):
        """
        Handle GUI events until there's something to read from sock.
        If there's no graphic toolkit, just return.
        """
        has_gtk = 'gtk' in sys.modules
        has_qt4 = 'PyQt4' in sys.modules
        has_tk = 'Tkinter' in sys.modules

        if not has_gtk and not has_qt4 and not has_tk:
            return

        while not select([sock], [], [], 0)[0]:
            if has_gtk:
                handle_gtk_events()
            if has_qt4:
                handle_qt4_events()
            if has_tk:
                handle_tk_events()

    @rpc_func
    def execute(self, source):
        split_source = split_to_singles(source)
        # This added newline is because sometimes the CommandCompiler wants
        # more if there isn't a newline at the end
        split_source[-1] += '\n'
        line_count = 0
        # Compile to check for syntax errors
        for src in split_source:
            try:
                c = compile(src, '<pyshell>', 'single')
            except SyntaxError, e:
                yield False, (e.msg, e.lineno-1+line_count, e.offset-1)
                return
            else:
                if c is None:
                    yield False, None
                    return
                else:
                    line_count += src.count('\n')

        # If compilation was successfull...
        yield True, None
        is_success = True
        exception_string = None
        for src in split_source:
            # We compile again, so as not to put into linecache code
            # which had no effect
            filename = '<pyshell#%d>' % self.gid
            self.gid += 1
            lines = src.split("\n")
            linecache.cache[filename] = len(src)+1, None, lines, filename
            c = compile(src, filename, 'single')
            try:
                exec c in self.locs
            except (Exception, KeyboardInterrupt), e:
                sys.stdout.flush()
                linecache.checkcache()
                efile = StringIO()
                typ, val, tb = excinfo = sys.exc_info()
                sys.last_type, sys.last_value, sys.last_traceback = excinfo
                tbe = traceback.extract_tb(tb)
                my_filename = sys._getframe().f_code.co_filename
                if tbe[-1][0] != my_filename:
                    # If the last entry is from this file, don't remove
                    # anything. Otherwise, remove lines before the current
                    # frame.
                    for i in xrange(len(tbe)-2, -1, -1):
                        if tbe[i][0] == my_filename:
                            tbe = tbe[i+1:]
                            break
                print>>efile, 'Traceback (most recent call last):'
                traceback.print_list(tbe, file=efile)
                lines = traceback.format_exception_only(typ, val)
                for line in lines:
                    print>>efile, line,
                is_success = False
                exception_string = efile.getvalue()
                break
            
        # Send back any data left on stdin.
        rem_stdin = []
        while select([sys.stdin], [], [], 0)[0]:
            rem_stdin.append(os.read(sys.stdin.fileno(), 8192))
        rem_stdin = ''.join(rem_stdin)

        yield is_success, exception_string, rem_stdin


    @staticmethod
    def split_list(L, public_set):
        """
        split L into two lists: public and private, according to public_set,
        which should be a set of names or None. If it's None, split according
        to whether the first char is '_'.
        """
        public = []
        private = []
        if public_set is not None:
            for x in L:
                if x in public_set:
                    public.append(x)
                else:
                    private.append(x)
        else:
            for x in L:
                if not x.startswith('_'):
                    public.append(x)
                else:
                    private.append(x)
        return public, private

    @rpc_func
    def complete_attributes(self, expr):
        """
        Evaluate expr in the namespace, and return its attributes as two
        sorted lists - public and private.
        public - completions that are thought to be relevant.
        private - completions that are not so.
        If expr == '', return first-level completions.
        """
        if expr == '':
            try:
                namespace = self.locs.copy()
                namespace.update(__builtin__.__dict__)
                ids = eval("dir()", namespace) + keyword.kwlist
                ids.sort()
                if '__all__' in namespace:
                    all_set = set(namespace['__all__'])
                else:
                    all_set = None
                public, private = self.split_list(ids, all_set)
            except Exception, e:
                public = private = []
                import traceback
                traceback.print_exc()
        else:
            try:
                entity = eval(expr, self.locs)
                ids = dir(entity)
                ids.sort()
                if hasattr(entity, '__all__'):
                    all_set = set(entity.__all__)
                else:
                    all_set = None
                public, private = self.split_list(ids, all_set)
            except Exception, e:
                public = private = []

        return public, private

# Handle GUI events

def handle_gtk_events():
    import gtk, glib
    glib.timeout_add(GUI_SLEEP_MS, gtk_main_quit)
    gtk.main()

def gtk_main_quit():
    import gtk
    gtk.main_quit()
    return False

def handle_qt4_events():
    from PyQt4 import QtCore
    app = QtCore.QCoreApplication.instance()
    if not app:
        time.sleep(GUI_SLEEP_SEC)
        return

    timer = QtCore.QTimer()
    QtCore.QObject.connect(timer, QtCore.SIGNAL('timeout()'),
                           qt4_quit_if_no_modal)
    timer.start(GUI_SLEEP_MS)
    app.exec_()
    timer.stop()
    QtCore.QObject.disconnect(timer, QtCore.SIGNAL('timeout()'),
                              qt4_quit_if_no_modal)

def qt4_quit_if_no_modal():
    from PyQt4 import QtCore
    app = QtCore.QCoreApplication.instance()
    if app.__class__.__name__ != 'QApplication' or \
       app.activeModalWidget() is None:
        app.quit()

def handle_tk_events():
    # TODO: It's pretty silly to handle all events and then just wait.
    # But I haven't found a better way - if you find one, tell me!
    import Tkinter
    # Handling Tk events is done only if there is an active tkapp object.
    # It is created by Tkinter.Tk.__init__, which sets
    # Tkinter._default_root to itself, when Tkinter._support_default_root
    # is True (the default). Here we check whether Tkinter._default_root
    # is something before we handle Tk events.
    if Tkinter._default_root:
        _tkinter = Tkinter._tkinter
        while _tkinter.dooneevent(_tkinter.DONT_WAIT):
            pass
    time.sleep(GUI_SLEEP_SEC)

def main(port):
    subp = Subprocess(port)
