#!/usr/bin/env python3

import os
import argparse
import fnmatch
import subprocess
import sys
import pyperclip

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
import tiktoken

MAIN_PROMPT = "Review the provided codebase and describe its key functionalities. Should you require any missing " \
              "files or further details for your analysis, kindly request:\n"

QUIET_PROMPT = "You've received a codebase. Acknowledge your understanding by responding with \"ACKNOWLEDGED\". " \
               "If you notice missing files critical to your comprehension, please request them. Do not elaborate on " \
               "the codebase's operation and skip explaining what it does:\n"

EXCLUDED_DIRS = ['.git']
EXCLUDED_FILES = ['.gitignore']

# Global token counts
total_tokens_gpt35 = 0
total_tokens_gpt4 = 0


def num_tokens_from_string(string: str) -> tuple[int, int]:
    """Returns the number of tokens in a text string."""
    num_tokens_gpt35 = len(tiktoken.encoding_for_model("gpt-3.5-turbo").encode(string))
    num_tokens_gp4 = len(tiktoken.encoding_for_model("gpt-4").encode(string))
    return num_tokens_gpt35, num_tokens_gp4


def generate_and_count_tokens(path):
    """Generates a string from the file and adds its token count to the global total."""
    global total_tokens_gpt35
    global total_tokens_gpt4

    file_preamble = f"----FILE: {'./' if not path.startswith('./') and not path.startswith('/') else ''}{path}"
    print(file_preamble)
    tokens_gpt35, tokens_gpt4 = num_tokens_from_string(file_preamble)
    total_tokens_gpt35 += tokens_gpt35
    total_tokens_gpt4 += tokens_gpt4
    file_contents = ""

    try:
        with open(path, 'r', encoding='utf-8') as file:
            file_contents = file.read()
            tokens_gpt35, tokens_gpt4 = num_tokens_from_string(file_contents)
            total_tokens_gpt35 += tokens_gpt35
            total_tokens_gpt4 += tokens_gpt4
        tokens_gpt35, tokens_gpt4 = num_tokens_from_string("\n")
        total_tokens_gpt35 += tokens_gpt35
        total_tokens_gpt4 += tokens_gpt4
    except PermissionError:
        error = f"PermissionError. Unable to read the file: {file.name}."
        print(error, file=sys.stderr)
        file_contents = error
    except UnicodeDecodeError:
        error = f"UnicodeDecodeError. Unable to read the file: {file.name}."
        print(error)
        file_contents = error

    return file_preamble + "\n" + file_contents + "\n"


def log(msg):
    if sys.stdout.isatty() or sys.stderr.isatty():
        print(msg, file=sys.stderr)
    else:
        print(msg)


def read_gitignore(path):
    gitignore_lines = []
    global_gitignore = os.path.expanduser('~/.gitignore')

    if os.path.isfile(global_gitignore):
        with open(global_gitignore, 'r') as file:
            gitignore_lines += file.readlines()

    # Find all .gitignore files in subdirs
    for root, _, files in os.walk(path):
        if '.gitignore' in files:
            with open(os.path.join(root, '.gitignore'), 'r') as gitignore_file:
                sub_dir = os.path.relpath(root, path)

                # If we are in the root directory, no need to prepend the subdirectory
                if sub_dir != ".":
                    for line in gitignore_file:
                        line = line.strip()
                        # Avoiding comments or empty lines
                        if line and not line.startswith("#"):
                            gitignore_lines.append(os.path.join(sub_dir, line))
                else:
                    gitignore_lines += gitignore_file.readlines()

    return PathSpec.from_lines(GitWildMatchPattern, gitignore_lines) if gitignore_lines else PathSpec([])


def find_files(path, extensions, include_patterns, exclude_patterns, skip_patterns, gitignore_spec, git_root):
    full_path = "(unknown)"
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not (any(fnmatch.fnmatch(d, pattern) for pattern in skip_patterns) or
                                           d in EXCLUDED_DIRS)]

        for file in files:
            try:
                if file in EXCLUDED_FILES:
                    continue

                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, git_root if git_root else path)

                if (not include_patterns or any(fnmatch.fnmatch(file, pattern) for pattern in include_patterns)) and \
                        (not extensions or file.endswith(tuple(extensions))) and \
                        not any(fnmatch.fnmatch(file, pattern) for pattern in exclude_patterns) and \
                        not gitignore_spec.match_file(relative_path):
                    yield full_path
            except PermissionError:
                log(f"Permission denied. Unable to access {full_path}")


def find_git_root(path):
    git_root = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=path, capture_output=True, text=True)
    if git_root.returncode == 0:
        return git_root.stdout.strip()
    return None


def check_git_installed():
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    parser = argparse.ArgumentParser(description="This script traverses a directory structure and generates a "
                                                 "formatted prompt suitable for use with ChatGPT. It includes both the "
                                                 "path names and the contents of the files found within the specified "
                                                 "directory. It's recommended to pipe the output of this script to "
                                                 "your clipboard using `| pbcopy` for easy pasting into the ChatGPT "
                                                 "user interface.")
    parser.add_argument("-e", "--extension", action="append",
                        help="Optionally specify the file extensions to be included. Repeat the flag for multiple "
                             "extensions. For example, '-e py -e txt -e yaml' includes Python, Text, and YAML files.")
    parser.add_argument("-f", "--filter", action="append", default=[],
                        help="Optionally specify a pattern to only include specific files. Repeat the flag for "
                             "multiple patterns. For instance, '-f test' includes only filenames containing 'test'.")
    parser.add_argument("-x", "--exclude", action="append", default=[],
                        help="Optionally provide a pattern to exclude specific files. Repeat the flag for multiple "
                             "patterns. For instance, '-x test' excludes all files containing 'test'.")
    parser.add_argument("-d", "--dry-run", action="store_true",
                        help="Enable dry run mode. When set, the script only traverses the directory structure and "
                             "prints file names, but does not copy prompt to clipboard.")
    parser.add_argument("-s", "--skip", action="append", default=[],
                        help="Optionally provide a directory name to skip. Repeat the flag for multiple directories.")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Enable quiet mode. Changes the default prompt, so the model only acknowledges that it "
                             "understands the codebase, without explaining it.")
    parser.add_argument("paths", nargs='*', default=['.'],
                        help="Specify the directories or files to traverse. If not specified, the current working "
                             "directory is used.")
    args = parser.parse_args()

    # Modify the exclude and skip patterns by adding wildcard (*) to both ends
    args.exclude = [f"*{pattern}*" for pattern in args.exclude]
    args.filter = [f"*{pattern}*" for pattern in args.filter]
    args.skip = [f"*{pattern}*" for pattern in args.skip]

    if not check_git_installed():
        log("Warning: Git is not installed. .gitignore files will be ignored.")

    files_to_print = []
    for path in args.paths:
        if os.path.isfile(path):
            if args.extension or args.exclude != []:
                log("Warning: '--extension' and '--exclude' flags are ignored for explicitly provided file(s).")
            files_to_print.append(path)
        elif os.path.isdir(path):
            git_root = find_git_root(path) if check_git_installed() else None
            gitignore_spec = read_gitignore(git_root if git_root else path)
            files = list(find_files(path, args.extension, args.filter, args.exclude,
                                    args.skip, gitignore_spec, git_root))
            for file in files:
                files_to_print.append(file)
        else:
            log(f"Warning: '{path}' is neither a valid file nor a directory. It is skipped.")

    unique_files = list(set(files_to_print))
    unique_files.sort()
    if len(files_to_print) != len(unique_files):
        duplicates = [file for file in files_to_print if files_to_print.count(file) > 1]
        duplicates = list(set(duplicates))

        log("Warning: Duplicates in your parameters were found:")
        for duplicate in duplicates:
            log(duplicate)
        log("")
    log(f"Including for prompt: {args.paths}")
    log(f"Including filename patterns: {args.filter}")
    log(f"Excluding filename patterns: {args.exclude}")
    log(f"Excluding dirname patterns: {args.skip}")
    log(f"Extensions to be used: {args.extension}")
    log(f"Files found: {len(unique_files)}")

    log("---- PROMPT START ----")

    output = QUIET_PROMPT if args.quiet else MAIN_PROMPT
    tokens_gpt35, tokens_gpt4 = num_tokens_from_string(output)
    print(output)
    global total_tokens_gpt35
    global total_tokens_gpt4
    total_tokens_gpt35 += tokens_gpt35

    total_tokens_gpt4 += tokens_gpt4

    for file in unique_files:
        output += generate_and_count_tokens(file)

    if not args.dry_run:
        pyperclip.copy(output)  # Copy output to clipboard when not in dry-run mode

    log("---- PROMPT END ----")
    log(f"Total tokens for GPT-3.5: ~{total_tokens_gpt35}")
    log(f"Total tokens for GPT-4: ~{total_tokens_gpt4}")


if __name__ == "__main__":
    main()
