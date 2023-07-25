# ai-tools

## gpt-prompter

Handy tool for generating prompts based on codebase of your project.

### Usage (available via `--help`)

```
usage: gpt_codebase_prompter.py [-h] [-e EXTENSION] [-f FILTER] [-x EXCLUDE] [-d] [-s SKIP] [-q] [paths ...]

This script traverses a directory structure and generates a formatted prompt suitable for use with ChatGPT.
It includes both the path names and the contents of the files found within the specified directory.
Skips .gitignored files and counts token usage. By default it copies the prompt into your clipboard.

positional arguments:
  paths                 Specify the directories or files to traverse. If not specified, the current working
                        directory is used.

options:
  -h, --help            show this help message and exit
  -e EXTENSION, --extension EXTENSION
                        Optionally specify the file extensions to be included. Repeat the flag for multiple
                        extensions. For example, '-e py -e txt -e yaml' includes Python, Text, and YAML files.
  -f FILTER, --filter FILTER
                        Optionally specify a pattern to only include specific files. Repeat the flag for
                        multiple patterns. For instance, '-f test' includes only filenames containing 'test'.
  -x EXCLUDE, --exclude EXCLUDE
                        Optionally provide a pattern to exclude specific files. Repeat the flag for multiple
                        patterns. For instance, '-x test' excludes all files containing 'test'.
  -d, --dry-run         Enable dry run mode. When set, the script only traverses the directory structure and
                        prints file names, but does not copy prompt to clipboard.
  -s SKIP, --skip SKIP  Optionally provide a directory name to skip. Repeat the flag for multiple directories.
  -q, --quiet           Enable quiet mode. Changes the default prompt, so the model only acknowledges that it
                        consumed the codebase, without explaining it.
```

### Default prompt pre-ambles

```
MAIN_PROMPT = "Review the provided codebase and describe its key functionalities. Should you require any missing " \
              "files or further details for your analysis, kindly request:\n"

QUIET_PROMPT = "You've received a codebase. Acknowledge your understanding by responding with \"ACKNOWLEDGED\". " \
               "If you notice missing files critical to your comprehension, please request them. Do not elaborate on " \
               "the codebase's operation and skip explaining what it does:\n"
```

### Example usage

```
$ ./gpt-prompter.py -e py
Including for prompt: ['.']
Including filename patterns: []
Excluding filename patterns: []
Excluding dirname patterns: []
Extensions to be used: ['py']
Files found: 1
---- PROMPT START ----
Review the provided codebase and describe its key functionalities. Should you require any missing files or further details for your analysis, kindly request:

----FILE: ./gpt-prompter.py
---- PROMPT END ----
Total tokens for GPT-3.5: ~2158
Total tokens for GPT-4: ~2158
```
(the content of `gpt-prompter.py` is omitted in console output, but it's copied to clipboard)
