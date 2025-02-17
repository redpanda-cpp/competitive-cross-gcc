function chimaera()
  if is_plat("linux") and is_host("windows") then
    on_test(chimaera_run)
  end
end

-- Wine process `xmake.exe` cannot wait normal Linux processes --
-- `CreateProcess` returns empty handle. `chimaera.exe.so` is a Winelib
-- executable, which would be both a Wine process, thus can be waited by
-- xmake, and a Linux process, thus can wait normal Linux processes.
function chimaera_run(target, opt)
  opt = opt or {}

  -- early out: results were computed during build
  if opt.build_should_fail or opt.build_should_pass then
    if opt.errors then
      vprint(opt.errors)
    end
    return opt.passed
  end

  -- run test
  local outdata
  local errors
  local rundir = opt.rundir or target:rundir()
  local targetfile = path.absolute(target:targetfile())
  local runargs = table.wrap(opt.runargs or target:get("runargs"))
  local autogendir = path.join(target:autogendir(), "tests")
  local logname = opt.name:gsub("[/\\>=<|%*]", "_")
  local outfile = path.absolute(path.join(autogendir, logname .. ".out"))
  local errfile = path.absolute(path.join(autogendir, logname .. ".err"))
  os.tryrm(outfile)
  os.tryrm(errfile)
  os.mkdir(autogendir)
  local run_timeout = opt.run_timeout

  -- use chimaera
  local newargs = table.pack(targetfile, table.unpack(runargs))
  local ok, syserrors = os.execv("chimaera.exe.so", newargs, {
    try = true, timeout = run_timeout, curdir = rundir,
    envs = envs, stdout = outfile, stderr = errfile})

  local outdata = os.isfile(outfile) and io.readfile(outfile) or ""
  local errdata = os.isfile(errfile) and io.readfile(errfile) or ""
  if outdata and #outdata > 0 then
    opt.stdout = outdata
  end
  if errdata and #errdata > 0 then
    opt.stderr = errdata
  end
  if opt.trim_output then
    outdata = outdata:trim()
  end
  if ok ~= 0 then
    if not errors or #errors == 0 then
      if ok ~= nil then
        if syserrors then
          errors = string.format("run %s failed, exit code: %d, exit error: %s", opt.name, ok, syserrors)
        else
          errors = string.format("run %s failed, exit code: %d", opt.name, ok)
        end
      else
        errors = string.format("run %s failed, exit error: %s", opt.name, syserrors and syserrors or "unknown reason")
      end
    end
  end
  os.tryrm(outfile)
  os.tryrm(errfile)

  if ok == 0 then
    local passed
    local pass_outputs = table.wrap(opt.pass_outputs)
    local fail_outputs = table.wrap(opt.fail_outputs)
    for _, pass_output in ipairs(pass_outputs) do
        if opt.plain then
            if pass_output == outdata then
                passed = true
                break
            end
        else
            if outdata:match("^" .. pass_output .. "$") then
                passed = true
                break
            end
        end
    end
    for _, fail_output in ipairs(fail_outputs) do
      if opt.plain then
        if fail_output == outdata then
          passed = false
          if not errors or #errors == 0 then
            errors = string.format("matched failed output: ${color.failure}%s${clear}", fail_output)
            local actual_output = outdata
            actual_output = outdata:sub(1, 64)
            if #outdata > #actual_output then
              actual_output = actual_output .. "..."
            end
            errors = errors .. ", actual output: ${color.failure}" .. actual_output
          end
          break
        end
      else
        if outdata:match("^" .. fail_output .. "$") then
          passed = false
          if not errors or #errors == 0 then
            errors = string.format("matched failed output: ${color.failure}%s${clear}", fail_output)
            local actual_output = outdata
            actual_output = outdata:sub(1, 64)
            if #outdata > #actual_output then
              actual_output = actual_output .. "..."
            end
            errors = errors .. ", actual output: ${color.failure}" .. actual_output
          end
          break
        end
      end
    end
    if passed == nil then
      if #pass_outputs == 0 then
        passed = true
      else
        passed = false
        if not errors or #errors == 0 then
          errors = string.format("not matched passed output: ${color.success}%s${clear}", table.concat(pass_outputs, ", "))
          local actual_output = outdata
          actual_output = outdata:sub(1, 64)
          if #outdata > #actual_output then
            actual_output = actual_output .. "..."
          end
          errors = errors .. ", actual output: ${color.failure}" .. actual_output
        end
      end
    end
    if errors and #errors > 0 then
      opt.errors = errors
    end
    return passed
  end
  if errors and #errors > 0 then
    opt.errors = errors
  end
  return false
end
