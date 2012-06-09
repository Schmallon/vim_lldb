import lldb
import os
import time

def log(message):
  with open("lldb_log.txt", "a") as f:
    f.write(str(time.time()) + " - ")
    f.write(str(message) + "\n")

def run_target(target_filename):
  debugger = lldb.SBDebugger.Create()
  debugger.SetAsync(False)
  target = debugger.CreateTarget(target_filename)
  if not target:
    log("Failed to get a target")

  target.LaunchSimple (None, None, os.getcwd())
