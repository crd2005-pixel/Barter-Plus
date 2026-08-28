import subprocess
print(subprocess.check_output(['git', 'log', '-2', '--oneline']).decode('utf-8'))
