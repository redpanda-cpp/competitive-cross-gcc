#include <cstdio>
#include <string>
#include <vector>

#include <sys/wait.h>
#include <unistd.h>

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

using std::string;
using std::vector;

string narrow(const wchar_t *wstr)
{
  string str;
  int len = WideCharToMultiByte(CP_UTF8, 0, wstr, -1, nullptr, 0, nullptr, nullptr);
  str.resize(len);
  WideCharToMultiByte(CP_UTF8, 0, wstr, -1, str.data(), len, nullptr, nullptr);
  return str;
}

extern "C"
int wmain(int argc, wchar_t *wargv[])
{
  char *unix_program = wine_get_unix_file_name(wargv[1]);

  vector<string> args;
  vector<char *> argv;

  for (int i = 1; i < argc; ++i) {
    args.push_back(narrow(wargv[i]));
    argv.push_back(args.back().data());
  }
  argv.push_back(nullptr);

  pid_t pid = fork();
  if (pid == 0) {
    execv(unix_program, argv.data());
    perror("[chimaera] execv");
    return 1;
  } else if (pid > 0) {
    HeapFree(GetProcessHeap(), 0, unix_program);
    int wstatus;
    waitpid(pid, &wstatus, 0);
    return WEXITSTATUS(wstatus);
  } else {
    perror("[chimaera] fork");
    return 1;
  }
}
