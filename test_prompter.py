import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, Mock, MagicMock, call
import proxy_gpt_prompter as script


class TestMyScript(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.subdir1 = os.path.join(self.test_dir, 'subdir1')
        os.mkdir(self.subdir1)
        self.subdir2 = os.path.join(self.test_dir, 'subdir2')
        os.mkdir(self.subdir2)

        # Create test files for all file related tests
        self.file1 = self.create_file('test1.py')
        self.gitignorefile1 = self.create_file('.gitignore')
        self.file2 = self.create_file('test2.txt')
        self.file3 = self.create_file('test3.py', self.subdir1)
        self.file4 = self.create_file('test4.py', self.subdir2)
        self.file5 = self.create_file('test5.py', self.subdir2)
        self.file6 = self.create_file('test6.py')
        self.gitignorefile2 = self.create_file('.gitignore', self.subdir2)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def create_file(self, filename, directory=None):
        directory = directory if directory else self.test_dir
        with open(os.path.join(directory, filename), 'w') as f:
            f.write("test data")
        return os.path.join(directory, filename)

    @staticmethod
    def write_to_file(file, lines):
        with open(file, 'w') as f:
            for line in lines:
                f.write(line + "\n")

    @patch('subprocess.run')
    def test_find_git_root(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout=self.test_dir)
        git_root = script.find_git_root(self.test_dir)
        self.assertEqual(git_root, self.test_dir)

    @patch('subprocess.run')
    def test_find_git_root_no_git(self, mock_run):
        mock_run.return_value = Mock(returncode=128)
        git_root = script.find_git_root(self.test_dir)
        self.assertIsNone(git_root)

    def test_find_files(self):
        files = list(script.find_files(self.test_dir, [], [], [], [], script.PathSpec([]), None))
        self.assertEqual(set(files), {self.file1, self.file2, self.file3, self.file4, self.file5, self.file6})

    def test_num_tokens_from_string(self):
        tokens_gpt35, tokens_gpt4 = script.num_tokens_from_string('Hello, world!')
        self.assertEqual(tokens_gpt35, 4)
        self.assertEqual(tokens_gpt4, 4)

    @patch('argparse.ArgumentParser.parse_args')
    def test_main_with_file(self, mock_args):
        # Mock command line arguments to simulate passing a file to the script
        mock_args.return_value = MagicMock(paths=[self.file1], extension=[], exclude=[], dry_run=True)

        # Run the main function of the script
        script.main()

    def test_find_files_exclude(self):
        # Testing exclusion with .gitignore
        self.write_to_file(self.gitignorefile1, ['test2.txt'])
        self.write_to_file(self.gitignorefile2, ['test5.py'])
        gitignore_spec = script.read_gitignore(self.test_dir)
        # main gitignore + skipping subdir2
        files = list(script.find_files(self.test_dir, ['.py', '.txt'], ['*test*'], [], ['*subdir2*'],
                                       gitignore_spec, self.test_dir))
        self.assertEqual(set(files), {self.file1, self.file3, self.file6})

        # nested gitignore should work
        files = list(script.find_files(self.test_dir, ['.py', '.txt'], ['*test*'], [], [],
                                       gitignore_spec, self.test_dir))
        self.assertEqual(set(files), {self.file1, self.file3, self.file4, self.file6})

        # Testing exclusion with pattern
        files = list(script.find_files(self.test_dir, ['.py', '.txt'], ['*test*'], ['*2.txt'], ['subdir2'],
                                       script.PathSpec([]), self.test_dir))
        self.assertEqual(set(files), {self.file1, self.file3, self.file6})

        # Testing exclusion with extension
        files = list(script.find_files(self.test_dir, ['.py'], ['*test*'], [], ['subdir2'],
                                       script.PathSpec([]), self.test_dir))
        self.assertEqual(set(files), {self.file1, self.file3, self.file6})

    @patch('proxy_gpt_prompter.num_tokens_from_string')
    @patch('proxy_gpt_prompter.log')
    @patch('pyperclip.copy')
    @unittest.skip("TODO: cannot mock via proxy, need to fix this")
    def test_log(self, mock_copy, mock_log, mock_tokens):
        mock_tokens.return_value = (1, 1)
        with patch.object(sys, 'argv',
                          ['gpt-prompter.py',
                           '-e', 'py',
                           '-x', 'foo',
                           '-f', 'test',
                           '-s', os.path.basename(self.subdir2),
                           self.test_dir,
                           self.file3,
                           'bar']):
            script.main()
        expected_calls = [
            call("Warning: '--extension' and '--exclude' flags are ignored for explicitly provided file(s)."),
            call("Warning: 'bar' is neither a valid file nor a directory. It is skipped."),
            call('Warning: Duplicates in your parameters were found:'),
            call(self.file3),
            call(''),
            call(f"Including for prompt: ['{self.test_dir}', '{self.file3}', 'bar']"),
            call("Including filename patterns: ['*test*']"),
            call("Excluding filename patterns: ['*foo*']"),
            call("Excluding dirname patterns: ['*subdir2*']"),
            call("Extensions to be used: ['py']"),
            call('Files found: 2'),
            call('---- PROMPT START ----'),
            call('---- PROMPT END ----'),
            call('Total tokens for GPT-3.5: ~7'),
            call('Total tokens for GPT-4: ~7')
        ]
        self.assertEqual(mock_log.call_args_list, expected_calls)

    @patch('pyperclip.copy')
    def test_print_main_prompt(self, mock_copy):
        with patch.object(sys, 'argv',
                          ['gpt-prompter.py',
                           '-e', 'py',
                           '-x', 'foo',
                           '-f', 'test',
                           '-s', os.path.basename(self.subdir2),
                           self.test_dir,
                           self.file3,
                           'bar']):
            script.main()
        expected_calls = [call(
            f"{script.MAIN_PROMPT}----FILE: {self.file3}\n"
            f"test data\n"
            f"----FILE: {self.file1}\n"
            f"test data\n"
            f"----FILE: {self.file6}\n"
            f"test data\n"
        )]
        self.assertEqual(mock_copy.call_args_list, expected_calls)

    @patch('pyperclip.copy')
    def test_print_quiet_prompt(self, mock_copy):
        with patch.object(sys, 'argv',
                          ['gpt-prompter.py',
                           '-q',
                           '-e', 'py',
                           '-x', 'foo',
                           '-f', 'test',
                           '-s', os.path.basename(self.subdir2),
                           self.test_dir,
                           self.file3,
                           'bar']):
            script.main()
        expected_calls = [call(
            f"{script.QUIET_PROMPT}----FILE: {self.file3}\n"
            f"test data\n"
            f"----FILE: {self.file1}\n"
            f"test data\n"
            f"----FILE: {self.file6}\n"
            f"test data\n"
        )]
        self.assertEqual(mock_copy.call_args_list, expected_calls)

    @patch('proxy_gpt_prompter.generate_and_count_tokens')
    @unittest.skip("TODO: cannot mock via proxy, need to fix this")
    def test_print_dry_run(self, mock_generate_and_count_tokens):
        with patch.object(sys, 'argv',
                          ['gpt-prompter.py',
                           '-d',
                           '-e', 'py',
                           '-x', 'foo',
                           '-f', 'test',
                           '-s', os.path.basename(self.subdir2),
                           self.test_dir,
                           self.file3,
                           'bar']):
            script.main()
        expected_calls = [
            call(self.file3),
            call(self.file1)
        ]
        self.assertEqual(mock_generate_and_count_tokens.call_args_list, expected_calls)


if __name__ == '__main__':
    unittest.main()
