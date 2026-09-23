import subprocess
print(subprocess.check_output(['git', 'log', '-1', '--stat']).decode('utf-8'))
