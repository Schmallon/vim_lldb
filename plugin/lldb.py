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
    vim.command("highlight lldb_current_location ctermbg=6 gui=undercurl guisp=DarkCyan")

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

  def launch(self):
    self.process = self.target.LaunchSimple(None, None, os.getcwd())
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




class TestLLDBPlugin(unittest.TestCase):

  def setUp(self):
    c_source = """int main()
{
  return 0;
}
"""

    temp_dir = tempfile.mkdtemp()
    self.source_filename = os.path.join(temp_dir, "main.c")
    with open(self.source_filename, "w") as f:
      f.write(c_source)

    self.target_filename = os.path.join(temp_dir, "binary")
    os.system("clang -g -x c %s -o %s" % (self.source_filename, self.target_filename))

    vim.command("bufdo! bdelete!")
    vim.command("e %s" % self.source_filename)



  def test_can_run_target(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.target_filename)

  def test_breakpoint_list_is_initially_empty(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.target_filename)
    self.assertEquals(
      list(plugin.breakpoint_list()), [])

  def test_can_add_breakpoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.target_filename)
    plugin.add_breakpoint("main")

  def test_breakpoint_list_contains_added_breakoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.target_filename)
    plugin.add_breakpoint("main")
    self.assertNotEquals(
      list(plugin.breakpoint_list()), [])

  def test_breakpoint_window_shows_breakpoint(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.target_filename)
    plugin.add_breakpoint("main")
    plugin.show_breakpoint_window()
    self.assertEquals(
        vim.eval("getline(1, '$')"),
        ["main.c:3:3"])

  def test_add_breakpoint_on_current_line(self):
    pass


  def test_highlight_current_location(self):
    plugin = LLDBPlugin()
    plugin.create_target(self.target_filename)
    plugin.add_breakpoint("main")
    plugin.launch()
    vim.command("normal 3G2l")
    self.assertEquals(
      vim.eval('synIDattr(synID(3, 3, 1),"name")'),
      "lldb_current_location")



def run_lldb_tests():
  suite = unittest.TestLoader().loadTestsFromTestCase(TestLLDBPlugin)
  with open("test_log.txt", "a") as f:
    unittest.TextTestRunner(stream=f, verbosity=2).run(suite)
