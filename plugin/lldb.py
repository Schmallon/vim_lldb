import lldb
import os
import time
import tempfile
import unittest
import vim


def to_vim_string(string):
  return "'" + str(string).replace("\\", "\\\\").replace('"', '\\"') + "'"

class LLDBPlugin(object):

  def __init__(self):
    self.target = None

  def create_target(self, target_filename):
    debugger = lldb.SBDebugger.Create()
    debugger.SetAsync(False)
    self.target = debugger.CreateTarget(target_filename)
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

  def show_breakpoint_window(self):
    buffer_number = vim.eval("bufnr('lldb_breakoints', 1)")
    vim.command("buffer %s" % buffer_number)
    for breakpoint in self.breakpoint_list():
      vim.eval("append('$', %s)" % to_vim_string(breakpoint))#to_vim_string(breakpoint))
      #vim.eval("append('$', %s)" % "foo")#to_vim_string(breakpoint))
    vim.command("normal ggdd")



class TestLLDBPlugin(unittest.TestCase):

  def create_target(self):
    c_source = """int main()
{
  return 0;
}
"""

    temp_dir = tempfile.mkdtemp()
    source_filename = os.path.join(temp_dir, "main.c")
    with open(source_filename, "w") as f:
      f.write(c_source)

    out_name = os.path.join(temp_dir, "binary")
    os.system("clang -g -x c %s -o %s" % (source_filename, out_name))

    return out_name


  def test_can_run_target(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target())

  def test_breakpoint_list_is_initially_empty(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target())
    self.assertEquals(
      list(plugin.breakpoint_list()), [])

  def test_can_add_breakpoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target())
    plugin.add_breakpoint("main")

  def test_breakpoint_list_contains_added_breakoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target())
    plugin.add_breakpoint("main")
    self.assertNotEquals(
      list(plugin.breakpoint_list()), [])

  def test_breakpoint_window_shows_breakpoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.create_target())
    plugin.add_breakpoint("main")
    plugin.show_breakpoint_window()
    self.assertEquals(
        vim.eval("getline(1, '$')"),
        ["main.c:3:3"])

  def test_add_breakpoint_on_current_line(self):
    pass


def run_lldb_tests():
  suite = unittest.TestLoader().loadTestsFromTestCase(TestLLDBPlugin)
  with open("test_log.txt", "a") as f:
    unittest.TextTestRunner(stream=f, verbosity=2).run(suite)
