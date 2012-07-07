import lldb
import os
import time
import tempfile
import unittest
import vim
import threading
import weakref


def to_vim_string(string):
  return "'" + str(string).replace("\\", "\\\\").replace('"', '\\"') + "'"

def is_done_after(function, seconds):
  thread = threading.Thread(target = function)
  thread.start()
  #thread.join(seconds)
  return not thread.isAlive()


class LLDBPlugin(object):

  all_instances = weakref.WeakSet()

  @classmethod
  def get_instance(cls, target_id):
    return [instance for instance in cls.all_instances if id(instance) == target_id][0]

  def __init__(self):
    LLDBPlugin.all_instances.add(self)
    self.target = None
    vim.command("highlight lldb_current_location ctermbg=6 gui=undercurl guisp=DarkCyan")
    self.debugger = lldb.SBDebugger.Create()
    self.debugger.SetAsync(False)

  def create_target(self, target_filename):
    self.target = self.debugger.CreateTarget(target_filename)
    if not self.target:
      raise "Failed to get a target"

  def breakpoint_list(self):
    for breakpoint in self.target.breakpoint_iter():
      for location in breakpoint:
        address = location.GetAddress()
        line_entry = address.GetLineEntry()
        line = line_entry.GetLine()
        column = line_entry.GetColumn()
        file_spec = line_entry.GetFileSpec()
        file_name = file_spec.GetFilename()
        yield file_name + ":" + str(line) + ":" + str(column)

  def add_breakpoint(self, name):
    self.target.BreakpointCreateByName(name)

  def _edit_buffer_named(self, buffer_name):
    buffer_number = vim.eval("bufnr('%s', 1)" % buffer_name)
    vim.command("buffer %s" % buffer_number)

  def show_breakpoint_window(self):
    self._edit_buffer_named('lldb_breakpoints')
    for breakpoint in self.breakpoint_list():
      vim.eval("append('$', %s)" % to_vim_string(breakpoint))#to_vim_string(breakpoint))
      #vim.eval("append('$', %s)" % "foo")#to_vim_string(breakpoint))
    vim.command("normal ggdd")


  def show_locals_window(self):
    self._edit_buffer_named('lldb_variables')
    variables = self.process.GetSelectedThread().GetFrameAtIndex(0).GetVariables(True, True, True, False)
    for variable in variables:
      vim.eval("append('$', %s)" % to_vim_string(str(variable).replace("\n", "")))
    vim.command("normal ggdd")

  def launch(self):
    self.process = self.target.LaunchSimple(None, None, os.getcwd())
    self.highlight_current_location()

  def kill(self):
    self.process.Kill()

  def do_continue(self):
    self.process.Continue()

  def step_into(self):
    self.process.GetSelectedThread().StepInto()
    self.highlight_current_location()

  def highlight_current_location(self):
    vim.command("syntax clear lldb_current_location")
    for thread in self.process:
      frame = thread.GetFrameAtIndex(0)
      line_entry = frame.GetLineEntry()
      line = line_entry.GetLine()
      column = line_entry.GetColumn()
      pattern = '\%' + str(line) + 'l' + '\%' \
          + str(column) + 'c' + '.*' # + '\%' + str(5) + 'c'
      vim.command("syntax match lldb_current_location /%s/" % pattern)

  def show_command_line(self):
    self._edit_buffer_named('lldb_command_line')
    vim.eval("append('$', '(lldb) ')")
    vim.command("normal ggdd")
    vim.command("imap <buffer> <CR> <ESC>:python LLDBPlugin.get_instance(%s).entered_command()<CR>" % id(self))
    vim.command("normal A")

  def entered_command(self):
    command_line = vim.current.line[:].replace("(lldb)", "")
    result = lldb.SBCommandReturnObject()
    self.debugger.GetCommandInterpreter().HandleCommand(command_line, result)
    vim.current.buffer.append(result.GetOutput())
    vim.eval("append('$', '(lldb) ')")


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

  def create_target_and_edit_source(self, source):

    temp_dir = tempfile.mkdtemp()
    source_filename = os.path.join(temp_dir, "main.c")
    with open(source_filename, "w") as f:
      f.write(source)

    target_filename = os.path.join(temp_dir, "binary")
    os.system("clang -g -x c %s -o %s" % (source_filename, target_filename))

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

def run_lldb_tests():
  suite = unittest.TestLoader().loadTestsFromTestCase(TestLLDBPlugin)
  with open("test_log.txt", "a") as f:
    unittest.TextTestRunner(stream=f, verbosity=2).run(suite)
