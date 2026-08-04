import subprocess
print(subprocess.check_output(['git', 'diff', 'HEAD', 'main', '--stat']).decode('utf-8'))
