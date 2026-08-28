import subprocess
print(subprocess.check_output(['git', 'branch']).decode('utf-8'))
