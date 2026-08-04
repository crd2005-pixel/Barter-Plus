import subprocess
print(subprocess.check_output(['git', 'log', '-3', '--oneline']).decode('utf-8'))
