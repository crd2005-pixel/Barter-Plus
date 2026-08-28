import subprocess
print(subprocess.check_output(['git', 'diff', 'origin/main', 'jules_final', '--stat']).decode('utf-8'))
