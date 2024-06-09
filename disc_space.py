import os
import shutil


def db_size():
	s = os.path.getsize("instance/bme280.db");
	for i in ['bytes', 'KB', 'MB', 'GB', 'TB']:
		if s < 1024:
			return "%.2f %s" % (s, i)
		s /= 1024
		

def free_space():
	total, used, free = shutil.disk_usage(__file__)
	for i in ['bytes', 'KB', 'MB', 'GB', 'TB']:
		if free < 1024:
			return "%.2f %s" % (free, i)
		free /= 1024