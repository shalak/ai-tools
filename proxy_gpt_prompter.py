# I really want the file to contain dash, so lets this proxy, so we can import and patch the script in unittest
tmp = __import__('gpt-prompter')
globals().update(vars(tmp))
