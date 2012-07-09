import lldb
import os
import time
import tempfile
import unittest
import vim
import threading
import weakref
import itertools


def to_vim_string(string):
  return "'" + str(string).replace("\\", "\\\\").replace('"', '\\"') + "'"

def is_done_after(function, seconds):
  thread = threading.Thread(target = function)
  thread.start()
  #thread.join(seconds)
  return not thread.isAlive()

def existing_buffer_named(buffer_name):
  def first(predicate, iter):
    return next(itertools.ifilter(predicate, iter), None)
  return first(lambda buffer: buffer.name and os.path.basename(buffer.name) == buffer_name, vim.buffers)

def window_number_for_buffer_named(buffer_name):
  buffer = existing_buffer_named(buffer_name)
  if buffer:
    return int(vim.eval('bufwinnr("%s")' % buffer.name))
  else:
    return -1

def enter_window_for_buffer_named(buffer_name):
  vim.command("%swincmd w" % window_number_for_buffer_named(buffer_name))

def has_window_for_buffer_named(buffer_name):
  return 0 <= window_number_for_buffer_named(buffer_name)

class BreakpointWindow(object):
  def __init__(self, plugin):
    self.plugin = plugin
  def show(self):
    self.plugin.clear_and_edit_buffer_named('lldb_breakpoints')
    for breakpoint in self.plugin.breakpoint_list():
      vim.eval("append('$', %s)" % to_vim_string(breakpoint))
    vim.command("normal ggdd")

class LocalsWindow(object):
  def __init__(self, plugin):
    self.plugin = plugin
  def show(self):
    self.plugin.clear_and_edit_buffer_named('lldb_variables')
    variables = self.plugin.process().GetSelectedThread().GetFrameAtIndex(0).GetVariables(True, True, True, False)
    for variable in variables:
      vim.eval("append('$', %s)" % to_vim_string(str(variable).replace("\n", "")))
    vim.command("normal ggdd")

class CodeWindow(object):
  def __init__(self, plugin):
    self.plugin = plugin
  def show(self):
    self.plugin.clear_and_edit_buffer_named('lldb_code')
    for thread in self.plugin.process():
      frame = thread.GetFrameAtIndex(0)
      file_spec = frame.GetLineEntry().GetFileSpec()
      file_name = os.path.join(file_spec.GetDirectory(), file_spec.GetFilename())
      vim.command("r %s" % file_name)
      vim.command("normal ggdd")
    self.plugin.highlight_current_location()

class CommandLineWindow(object):
  def __init__(self, plugin):
    self.plugin = plugin

  def show(self):
    self.plugin.clear_and_edit_buffer_named('lldb_command_line')
    vim.eval("append('$', '(lldb) ')")
    vim.command("normal ggdd")
    object_registry.register_object(self)
    vim.command("imap <buffer> <CR> <ESC>:python object_registry.get_object(%s).entered_command()<CR>" % id(self))
    vim.command("normal A")

  def entered_command(self):
    command_line = vim.current.line[:].replace("(lldb)", "")
    result = lldb.SBCommandReturnObject()
    self.plugin.debugger.GetCommandInterpreter().HandleCommand(command_line, result)

    self.plugin.update_windows()
    enter_window_for_buffer_named("lldb_command_line")

    self._append_lines(result.GetOutput())
    self._append_lines(result.GetError())
    vim.eval("append('$', '(lldb) ')")
    vim.command("normal G")

  def _append_lines(self, string):
    for line in string.splitlines(False):
      vim.current.buffer.append(line)

class ObjectRegistry(object):
  def __init__(self):
    self.objects = weakref.WeakSet()

  def get_object(self, target_id):
    return [object for object in self.objects if id(object) == target_id][0]

  def register_object(self, object):
    self.objects.add(object)

object_registry = ObjectRegistry()

class LLDBPlugin(object):

  def _target(self):
    return self.debugger.GetSelectedTarget()

  def process(self):
    return self._target().GetProcess()

  def __init__(self):
    vim.command("highlight lldb_current_location ctermbg=6 gui=undercurl guisp=DarkCyan")
    self.debugger = lldb.SBDebugger.Create()
    self.debugger.SetAsync(False)
    self._windows = set()

  def create_target(self, target_filename):
    self.debugger.CreateTarget(target_filename)

  def breakpoint_list(self):
    for breakpoint in self._target().breakpoint_iter():
      for location in breakpoint:
        address = location.GetAddress()
        line_entry = address.GetLineEntry()
        line = line_entry.GetLine()
        column = line_entry.GetColumn()
        file_spec = line_entry.GetFileSpec()
        file_name = file_spec.GetFilename()
        yield file_name + ":" + str(line) + ":" + str(column)

  def add_breakpoint(self, name):
    self._target().BreakpointCreateByName(name)

  def clear_and_edit_buffer_named(self, buffer_name):
    if has_window_for_buffer_named(buffer_name):
      enter_window_for_buffer_named(buffer_name)
    else:
      buffer_number = vim.eval("bufnr('%s', 1)" % buffer_name)
      vim.command("buffer %s" % buffer_number)
    vim.command("setlocal nospell")
    vim.command("normal ggVGd")

  def _add_window(self, window):
    self._windows.add(window)
    window.show()

  def show_breakpoint_window(self):
    self._add_window(BreakpointWindow(self))

  def show_locals_window(self):
    self._add_window(LocalsWindow(self))

  def show_code_window(self):
    self._add_window(CodeWindow(self))

  def update_windows(self):
    for window in self._windows:
      window.show()

  def launch(self):
    self._target().LaunchSimple(None, None, os.getcwd())
    self.update_windows()

  def kill(self):
    self.process().Kill()

  def do_continue(self):
    self.process().Continue()

  def step_into(self):
    self.process().GetSelectedThread().StepInto()
    self.update_windows()

  def highlight_current_location(self):
    vim.command("syntax clear lldb_current_location")
    for thread in self.process():
      frame = thread.GetFrameAtIndex(0)
      line_entry = frame.GetLineEntry()
      line = line_entry.GetLine()
      column = line_entry.GetColumn()
      pattern = '\%' + str(line) + 'l' + '\%' \
          + str(column) + 'c' + '.*' # + '\%' + str(5) + 'c'
      vim.command("syntax match lldb_current_location /%s/" % pattern)

  def show_command_line(self):
    self._add_window(CommandLineWindow(self))

  def show_all_windows(self):
    self.show_command_line()
    vim.command("new")
    self.show_code_window()
    vim.command("new")
    self.show_locals_window()
    vim.command("vnew")
    self.show_breakpoint_window()


class TestLLDBPlugin(unittest.TestCase):

  def default_source(self):
    return """int main()
{
  return 0;
}
"""

  def setUp(self):
    last_buffer = vim.eval("bufnr('$')")
    vim.command("0,%s bdelete!" % last_buffer)

  def create_source_and_target(self, source):
    temp_dir = tempfile.mkdtemp()
    source_filename = os.path.join(temp_dir, "main.c")
    with open(source_filename, "w") as f:
      f.write(source)

    target_filename = os.path.join(temp_dir, "binary")
    os.system("clang -g -x c %s -o %s" % (source_filename, target_filename))
    return source_filename, target_filename

  def create_target_and_edit_source(self, source):
    source_filename, target_filename = self.create_source_and_target(source)
    vim.command("e %s" % source_filename)
    return target_filename

  def test_can_run_target(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target_and_edit_source(self.default_source()))

  def test_breakpoint_list_is_initially_empty(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target_and_edit_source(self.default_source()))
    self.assertEquals(
      list(plugin.breakpoint_list()), [])

  def test_can_add_breakpoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target_and_edit_source(self.default_source()))
    plugin.add_breakpoint("main")

  def test_breakpoint_list_contains_added_breakoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target_and_edit_source(self.default_source()))
    plugin.add_breakpoint("main")
    self.assertNotEquals(
      list(plugin.breakpoint_list()), [])

  def test_breakpoint_window_shows_breakpoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target_and_edit_source(self.default_source()))
    plugin.add_breakpoint("main")
    plugin.show_breakpoint_window()
    self.assertEquals(
        vim.eval("getline(1, '$')"),
        ["main.c:3:3"])

  def test_highlight_current_location(self):
    plugin = LLDBPlugin()
    plugin.show_code_window()
    plugin.create_target(self.create_target_and_edit_source(self.default_source()))
    plugin.add_breakpoint("main")
    plugin.launch()
    self.assertEquals(
      vim.eval('synIDattr(synID(3, 3, 1),"name")'),
      "lldb_current_location")

  def test_step_into(self):
    source = """int f()
{
  return 0;
}

int main()
{
  return f();
}
"""

    plugin = LLDBPlugin()
    plugin.show_code_window()
    plugin.create_target(self.create_target_and_edit_source(source))
    plugin.add_breakpoint("main")
    plugin.launch()
    plugin.step_into()
    self.assertEquals(
      vim.eval('synIDattr(synID(3, 3, 1),"name")'),
      "lldb_current_location")

  def test_variables_window_shows_locals(self):
    source = """int main()
{
  int i = 42;
  return i;
}
"""

    plugin = LLDBPlugin()
    plugin.create_target(self.create_target_and_edit_source(source))
    plugin.add_breakpoint("main")
    plugin.launch()
    plugin.step_into()
    plugin.show_locals_window()
    self.assertEquals(
        vim.eval("getline(1, '$')"),
        ["(int) i = 42"])

  def test_show_command_line(self):
    plugin = LLDBPlugin()
    plugin.show_command_line()
    self.assertEquals(
        vim.eval("getline(1, '$')"),
        ["(lldb) "])

  def test_enter_command_in_command_line(self):
    plugin = LLDBPlugin()
    plugin.show_command_line()
    vim.command("normal Aprint 42\r")
    self.assertEquals(
        vim.eval("getline(1, '$')")[-2:],
        ["(int) $0 = 42", "(lldb) "])

  def test_allow_multiline_output(self):
    plugin = LLDBPlugin()
    plugin.show_command_line()
    vim.command("normal Ahelp\r")
    self.assertEquals(
        vim.eval("getline(1, '$')")[-2:],
        ["For more information on any particular command, try 'help <command-name>'.", "(lldb) "])

  def test_after_entering_command_cursor_is_on_last_line(self):
    plugin = LLDBPlugin()
    plugin.show_command_line()
    vim.command("normal Ahelp\r")
    self.assertEquals(
        len(vim.current.buffer),
        vim.current.window.cursor[0])

  def test_error_messages_are_shown(self):
    plugin = LLDBPlugin()
    plugin.show_command_line()
    vim.command("normal Afoo\r")
    self.assertEquals(
        ["error: 'foo' is not a valid command.", "(lldb) "],
        vim.eval("getline(1, '$')")[-2:])

  def test_showing_all_windows_works(self):
    plugin = LLDBPlugin()
    plugin.show_all_windows()
    self.assertEquals(
        set(["lldb_breakpoints", "lldb_command_line", "lldb_variables", "lldb_code"]),
        set([os.path.basename(window.buffer.name) for window in vim.windows]))

  def test_manually_setting_a_breakpoint_updates_breakpoint_window(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target_and_edit_source(self.default_source()))
    plugin.show_all_windows()

    enter_window_for_buffer_named("lldb_command_line")
    vim.command("normal Abreakpoint set --name main\r")

    self.assertEquals(
        ["main.c:3:3"],
        list(existing_buffer_named("lldb_breakpoints")))

  def test_windows_have_no_spell_checking(self):
    plugin = LLDBPlugin()
    plugin.show_all_windows()
    for window in vim.windows:
      enter_window_for_buffer_named(window.buffer.name)
      self.assertEquals("0", vim.eval("&l:spell"))

  def test_source_window_shows_current_file(self):
    plugin = LLDBPlugin()
    plugin.show_code_window()
    source_filename, target_filename = self.create_source_and_target(self.default_source())
    plugin.create_target(target_filename)
    plugin.add_breakpoint("main")
    plugin.launch()
    self.assertEquals(
      self.default_source().splitlines(False),
      list(existing_buffer_named("lldb_code")))

def run_lldb_tests():
  suite = unittest.TestLoader().loadTestsFromTestCase(TestLLDBPlugin)
  with open("test_log.txt", "a") as f:
    unittest.TextTestRunner(stream=f, verbosity=2).run(suite)

def run_single_test(test_name):
  loader = unittest.TestLoader()
  loader.testMethodPrefix = test_name
  suite = loader.loadTestsFromTestCase(TestLLDBPlugin)
  with open("test_log.txt", "a") as f:
    unittest.TextTestRunner(stream=f, verbosity=2).run(suite)
