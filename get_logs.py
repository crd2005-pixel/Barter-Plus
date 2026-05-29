import subprocess
print(subprocess.check_output(['git', 'log', '-n', '10', '--oneline']).decode('utf-8'))
