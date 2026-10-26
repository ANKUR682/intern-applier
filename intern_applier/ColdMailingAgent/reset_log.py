import shutil
import os
from datetime import datetime
from pathlib import Path

base = Path(__file__).parent
log_file = base / 'logs' / 'email_log.csv'
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
archive_file = base / 'logs' / f'email_log_archive_{timestamp}.csv'

# Archive the old log
shutil.copy(str(log_file), str(archive_file))
print(f'Archived old log to: {archive_file.name}')

# Reset the log — header only
with open(str(log_file), 'w', newline='', encoding='utf-8') as f:
    f.write('timestamp,name,email,company,status,matched_project,resume_path,error\n')

print('email_log.csv reset successfully!')
print('All contacts are now marked as unsent and ready for fresh outreach.')
